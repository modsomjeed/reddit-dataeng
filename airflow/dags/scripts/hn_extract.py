"""
Extract Hacker News stories for one calendar day and land them as
newline-delimited JSON (NDJSON) into MinIO.

Layer: BRONZE / raw  ―  we store the data *as extracted*, no transformation.
Partition layout in the bucket:
    hn-raw/source=hackernews/ingest_date=YYYY-MM-DD/stories_<run_id>.ndjson

Source: the HN Algolia search API (https://hn.algolia.com/api). It needs no
credentials and lets us filter by `created_at_i`, so every DAG run asks for
exactly one day. Re-running a day fetches the same window again, which is what
makes the extract idempotent.

Field names follow the warehouse, not the API: Algolia's `points` lands as
`score` and `objectID` as `story_id`, so the marts keep a stable vocabulary.
"""
from __future__ import annotations

import io
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import boto3
import requests

log = logging.getLogger(__name__)

SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
ITEM_URL = "https://news.ycombinator.com/item?id="
# Algolia never returns more than 1000 hits for one query, however you page it,
# and a busy HN day has ~1200 stories. So instead of paging we walk backwards in
# time: each batch ends where the previous one stopped.
HITS_PER_BATCH = 1000
MAX_BATCHES = 20  # guard against a window that refuses to shrink
REQUEST_PAUSE_SEC = 0.5
MAX_RETRIES = 4


def _day_bounds(ds: str) -> tuple[int, int]:
    """Return [start, end) unix timestamps for the UTC day `ds` (YYYY-MM-DD)."""
    start = datetime.strptime(ds, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(start.timestamp()), int((start + timedelta(days=1)).timestamp())


def _get_json(session: requests.Session, params: dict) -> dict:
    """GET with backoff, so a throttle or a blip does not fail the whole run."""
    for attempt in range(MAX_RETRIES):
        response = session.get(SEARCH_URL, params=params, timeout=30)
        if response.status_code in (429, 500, 502, 503, 504):
            wait = REQUEST_PAUSE_SEC * (2 ** attempt)
            log.warning("HTTP %s from Algolia ― retrying in %.1fs",
                        response.status_code, wait)
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError(f"Algolia kept failing after {MAX_RETRIES} attempts")


def _fetch_day(session: requests.Session, ds: str) -> list[dict]:
    """
    Fetch every story created during the UTC day `ds`.

    `search_by_date` returns newest first, so each batch's oldest timestamp
    becomes the upper bound of the next one. The bound is exclusive and moves
    to `oldest + 1` so stories sharing that second are not skipped; duplicates
    from the overlap are dropped by the caller.
    """
    start, end = _day_bounds(ds)
    hits: list[dict] = []
    seen_ids: set[str] = set()
    cursor = end
    expected: int | None = None

    for _ in range(MAX_BATCHES):
        payload = _get_json(session, {
            "tags": "story",
            "numericFilters": f"created_at_i>={start},created_at_i<{cursor}",
            "hitsPerPage": HITS_PER_BATCH,
            "page": 0,
        })
        if expected is None:
            expected = payload.get("nbHits")

        batch = payload.get("hits", [])
        if not batch:
            break
        hits.extend(batch)
        seen_ids.update(str(hit["objectID"]) for hit in batch)
        if expected is not None and len(seen_ids) >= expected:
            break

        oldest = min(hit["created_at_i"] for hit in batch)
        next_cursor = oldest + 1
        if oldest <= start or next_cursor >= cursor:
            break
        cursor = next_cursor
        time.sleep(REQUEST_PAUSE_SEC)
    else:
        log.warning("Hit the %d batch guard for %s ― the day may be truncated",
                    MAX_BATCHES, ds)

    log.info("Fetched %d stories (%d unique) for %s; Algolia reported %s",
             len(hits), len(seen_ids), ds, expected)
    if expected and len(seen_ids) < expected:
        log.warning("Only %d of %d stories retrieved for %s ― day is incomplete",
                    len(seen_ids), expected, ds)
    return hits


def _post_type(title: str) -> str:
    """HN has no flair; the title prefix is the community's own category."""
    lowered = title.lower()
    if lowered.startswith("ask hn"):
        return "ask_hn"
    if lowered.startswith("show hn"):
        return "show_hn"
    return "story"


def _hit_to_record(hit: dict, ingested_at: datetime) -> dict:
    """Flatten an Algolia hit into a plain dict matching raw_stories."""
    title = (hit.get("title") or "").strip()
    url = hit.get("url") or ""
    return {
        "story_id": str(hit["objectID"]),
        "title": title,
        "story_text": hit.get("story_text") or "",
        "author": hit.get("author") or "[deleted]",
        "score": int(hit.get("points") or 0),
        "num_comments": int(hit.get("num_comments") or 0),
        "permalink": f"{ITEM_URL}{hit['objectID']}",
        "url": url,
        "post_type": _post_type(title),
        # a story with no outbound link is HN's equivalent of a self post
        "is_self": 0 if url else 1,
        # ClickHouse DateTime wants 'YYYY-MM-DD HH:MM:SS'
        "created_utc": datetime.fromtimestamp(
            hit["created_at_i"], tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S"),
        "ingested_at": ingested_at.strftime("%Y-%m-%d %H:%M:%S"),
        "ingest_date": ingested_at.strftime("%Y-%m-%d"),
    }


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_ENDPOINT"],
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1",
    )


def extract_hn_to_minio(ds: str, run_id: str, **_) -> str:
    """
    Airflow entrypoint. `ds` (the logical date) and `run_id` come from op_kwargs.
    Returns the S3 key that was written (pushed to XCom for the next task).
    """
    bucket = os.environ["MINIO_BUCKET"]
    session = requests.Session()
    session.headers.update({"User-Agent": os.environ.get(
        "HN_USER_AGENT", "hn-dataeng-pipeline/0.1")})
    ingested_at = datetime.now(tz=timezone.utc)

    # de-duplicate by id: Algolia can repeat a hit across page boundaries when
    # a story is edited mid-scan
    seen: dict[str, dict] = {}
    for hit in _fetch_day(session, ds):
        seen.setdefault(str(hit["objectID"]), _hit_to_record(hit, ingested_at))

    records = list(seen.values())
    if not records:
        raise ValueError(f"No stories found for {ds} ― check the date window")

    ndjson = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
    safe_run = run_id.replace(":", "-").replace("+", "_")
    key = f"source=hackernews/ingest_date={ds}/stories_{safe_run}.ndjson"

    _s3_client().upload_fileobj(io.BytesIO(ndjson.encode("utf-8")), bucket, key)
    log.info("Wrote %d stories to s3://%s/%s", len(records), bucket, key)
    return key


if __name__ == "__main__":  # local smoke test
    logging.basicConfig(level=logging.INFO)
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    print(extract_hn_to_minio(ds=yesterday, run_id="manual_test"))
