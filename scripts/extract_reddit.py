"""Pull subreddit posts from the Arctic Shift archive into the S3 raw bucket, one file per day."""

import argparse
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError

from settings import read_env

API_URL = "https://arctic-shift.photon-reddit.com/api/posts/search"
PAGE_SIZE = 100
MAX_ATTEMPTS = 5
RAW_PREFIX = "posts"


def fetch_page(subreddit: str, after: int, before: int) -> list[dict]:
    params = {
        "subreddit": subreddit,
        "after": after,
        "before": before,
        "limit": PAGE_SIZE,
        "sort": "asc",
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "reddit-dataeng/0.1"})

    # Arctic Shift sometimes answers a valid query with 422 or 5xx; the same
    # request usually succeeds a few seconds later.
    for attempt in range(MAX_ATTEMPTS):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)["data"]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            if attempt == MAX_ATTEMPTS - 1:
                raise
            wait = 2**attempt + random.random()
            print(f"  {error}, retrying in {wait:.1f}s", flush=True)
            time.sleep(wait)


def fetch_day(subreddit: str, day: date) -> list[dict]:
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    after = int(start.timestamp())
    before = int((start + timedelta(days=1)).timestamp())

    posts: list[dict] = []
    while True:
        page = fetch_page(subreddit, after, before)
        posts.extend(page)
        if len(page) < PAGE_SIZE:
            return posts
        # Step back one second so posts sharing the last timestamp aren't skipped;
        # the duplicates this re-fetches are dropped in main().
        after = page[-1]["created_utc"] - 1
        time.sleep(1)


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


def extract_day(s3, bucket: str, subreddit: str, day: date, force: bool) -> None:
    key = f"{RAW_PREFIX}/{day.isoformat()}.json"
    if not force and object_exists(s3, bucket, key):
        print(f"{day} already extracted, skipping", flush=True)
        return

    posts = fetch_day(subreddit, day)
    # A page boundary can land inside one second, so drop any post seen twice.
    posts = list({post["id"]: post for post in posts}.values())

    body = json.dumps(posts, ensure_ascii=False).encode()
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    print(f"{day}: {len(posts)} posts → s3://{bucket}/{key}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subreddit", default="dataengineering")
    parser.add_argument("--start", type=date.fromisoformat, required=True, help="YYYY-MM-DD (UTC)")
    parser.add_argument("--end", type=date.fromisoformat, help="YYYY-MM-DD (UTC), inclusive; defaults to --start")
    parser.add_argument("--force", action="store_true", help="re-extract days that already have a file")
    args = parser.parse_args()

    env = read_env()
    s3 = s3_client(env)
    ensure_bucket(s3, env["S3_BUCKET"])

    day = args.start
    while day <= (args.end or args.start):
        extract_day(s3, env["S3_BUCKET"], args.subreddit, day, args.force)
        day += timedelta(days=1)


if __name__ == "__main__":
    main()
