"""
Extract posts from a subreddit with PRAW and land them as newline-delimited
JSON (NDJSON) into MinIO.

Layer: BRONZE / raw  ―  we store the data *as extracted*, no transformation.
Partition layout in the bucket:
    reddit-raw/subreddit=<name>/ingest_date=YYYY-MM-DD/posts_<run_id>.ndjson

This is the "E" and the landing part of the "L" in ELT.
"""
from __future__ import annotations

import io
import json
import logging
import os
from datetime import datetime, timezone

import boto3
import praw

log = logging.getLogger(__name__)


def _reddit_client() -> praw.Reddit:
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ["REDDIT_USER_AGENT"],
        check_for_async=False,
    )


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_ENDPOINT"],
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1",
    )


def _post_to_record(post, ingested_at: datetime) -> dict:
    """Flatten a PRAW submission into a plain dict matching raw_posts."""
    return {
        "post_id": post.id,
        "subreddit": str(post.subreddit),
        "title": post.title or "",
        "selftext": post.selftext or "",
        "author": str(post.author) if post.author else "[deleted]",
        "score": int(post.score),
        "upvote_ratio": float(post.upvote_ratio),
        "num_comments": int(post.num_comments),
        "permalink": f"https://reddit.com{post.permalink}",
        "url": post.url or "",
        "flair": post.link_flair_text or "",
        "over_18": 1 if post.over_18 else 0,
        "is_self": 1 if post.is_self else 0,
        # ClickHouse DateTime wants 'YYYY-MM-DD HH:MM:SS'
        "created_utc": datetime.fromtimestamp(
            post.created_utc, tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S"),
        "ingested_at": ingested_at.strftime("%Y-%m-%d %H:%M:%S"),
        "ingest_date": ingested_at.strftime("%Y-%m-%d"),
    }


def extract_reddit_to_minio(ds: str, run_id: str, **_) -> str:
    """
    Airflow entrypoint. `ds` (execution date) and `run_id` are passed via op_kwargs.
    Returns the S3 key that was written (pushed to XCom for the next task).
    """
    subreddit_name = os.environ.get("REDDIT_SUBREDDIT", "dataengineering")
    limit = int(os.environ.get("REDDIT_POST_LIMIT", "200"))
    bucket = os.environ["MINIO_BUCKET"]

    reddit = _reddit_client()
    subreddit = reddit.subreddit(subreddit_name)
    ingested_at = datetime.now(tz=timezone.utc)

    # Merge hot + new + top(week) and de-duplicate by id so we get both
    # trending and fresh posts in one pull.
    seen: dict[str, dict] = {}
    for listing in (
        subreddit.hot(limit=limit),
        subreddit.new(limit=limit),
        subreddit.top(time_filter="week", limit=limit),
    ):
        for post in listing:
            if post.id not in seen:
                seen[post.id] = _post_to_record(post, ingested_at)

    records = list(seen.values())
    if not records:
        raise ValueError("No posts extracted ― check Reddit credentials / subreddit")

    ndjson = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
    safe_run = run_id.replace(":", "-").replace("+", "_")
    key = (
        f"subreddit={subreddit_name}/ingest_date={ds}/posts_{safe_run}.ndjson"
    )

    _s3_client().upload_fileobj(
        io.BytesIO(ndjson.encode("utf-8")), bucket, key
    )
    log.info("Wrote %d posts to s3://%s/%s", len(records), bucket, key)
    return key


if __name__ == "__main__":  # local smoke test
    logging.basicConfig(level=logging.INFO)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(extract_reddit_to_minio(ds=today, run_id="manual_test"))
