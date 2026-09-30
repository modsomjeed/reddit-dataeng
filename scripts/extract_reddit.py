"""Pull subreddit posts or comments from the Arctic Shift archive into the S3 raw bucket, one file per day."""

import argparse
import json
import logging
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, timedelta

import boto3
from botocore.exceptions import ClientError

from settings import read_env, setup_logging

log = logging.getLogger("extract")

API_URL = "https://arctic-shift.photon-reddit.com/api/{kind}/search"
KINDS = ("posts", "comments")
PAGE_SIZE = 100
# Arctic Shift rate-limits by answering 422 "Timeout. Maybe slow down a bit", mostly on the
# heavier comment searches: pace every request and back off for up to ~10 minutes.
REQUEST_PAUSE_SECONDS = 2
QUERY_WINDOW_DAYS = 7
MAX_ATTEMPTS = 8


def fetch_page(kind: str, subreddit: str, after: int, before: int) -> list[dict]:
    params = {
        "subreddit": subreddit,
        "after": after,
        "before": before,
        "limit": PAGE_SIZE,
        "sort": "asc",
    }
    url = f"{API_URL.format(kind=kind)}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "reddit-dataeng/0.1"})

    for attempt in range(MAX_ATTEMPTS):
        time.sleep(REQUEST_PAUSE_SECONDS)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)["data"]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            if attempt == MAX_ATTEMPTS - 1:
                raise
            wait = 5 * 2**attempt + random.random()
            log.warning("%s, retrying in %.1fs", error, wait)
            time.sleep(wait)


def fetch_day(kind: str, subreddit: str, day: date) -> list[dict]:
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    after = int(start.timestamp())
    day_end = int((start + timedelta(days=1)).timestamp())
    # A narrow time window (a few hours) makes the archive's comment search time out,
    # so query a week-wide window and cut the results at the end of the day.
    before = day_end + QUERY_WINDOW_DAYS * 86400

    items: list[dict] = []
    while True:
        page = fetch_page(kind, subreddit, after, before)
        items.extend(item for item in page if item["created_utc"] < day_end)
        if len(page) < PAGE_SIZE or page[-1]["created_utc"] >= day_end:
            return items
        # Step back one second so items sharing the last timestamp aren't skipped;
        # the duplicates this re-fetches are dropped in extract_day(). If a whole
        # page shares one second, step past it rather than loop forever.
        after = max(page[-1]["created_utc"] - 1, after + 1)


def s3_client(env: dict[str, str]):
    return boto3.client(
        "s3",
        endpoint_url=env["S3_ENDPOINT"],
        aws_access_key_id=env["RUSTFS_ACCESS_KEY"],
        aws_secret_access_key=env["RUSTFS_SECRET_KEY"],
        region_name="us-east-1",
    )


def ensure_bucket(s3, bucket: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError:
        s3.create_bucket(Bucket=bucket)


def object_exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


def extract_day(s3, bucket: str, kind: str, subreddit: str, day: date, force: bool) -> None:
    key = f"{kind}/{day.isoformat()}.json"
    if not force and object_exists(s3, bucket, key):
        log.info("%s %s already extracted, skipping", day, kind)
        return

    items = fetch_day(kind, subreddit, day)
    # A page boundary can land inside one second, so drop any item seen twice.
    items = list({item["id"]: item for item in items}.values())

    body = json.dumps(items, ensure_ascii=False).encode()
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    log.info("%s: %d %s → s3://%s/%s", day, len(items), kind, bucket, key)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=KINDS, default="posts")
    parser.add_argument("--subreddit", default="dataengineering")
    parser.add_argument("--start", type=date.fromisoformat, required=True, help="YYYY-MM-DD (UTC)")
    parser.add_argument("--end", type=date.fromisoformat, help="YYYY-MM-DD (UTC), inclusive; defaults to --start")
    parser.add_argument("--force", action="store_true", help="re-extract days that already have a file")
    args = parser.parse_args()

    setup_logging()
    env = read_env()
    s3 = s3_client(env)
    ensure_bucket(s3, env["S3_BUCKET"])

    day = args.start
    while day <= (args.end or args.start):
        extract_day(s3, env["S3_BUCKET"], args.kind, args.subreddit, day, args.force)
        day += timedelta(days=1)


if __name__ == "__main__":
    main()
