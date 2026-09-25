"""Pull one day of subreddit posts from the Arctic Shift archive into data/raw."""

import argparse
import json
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

API_URL = "https://arctic-shift.photon-reddit.com/api/posts/search"
PAGE_SIZE = 100
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "posts"


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
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["data"]


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subreddit", default="dataengineering")
    parser.add_argument("--date", type=date.fromisoformat, required=True, help="YYYY-MM-DD (UTC)")
    args = parser.parse_args()

    posts = fetch_day(args.subreddit, args.date)
    # A page boundary can land inside one second, so drop any post seen twice.
    posts = list({post["id"]: post for post in posts}.values())

    out_path = RAW_DIR / f"{args.date.isoformat()}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(posts, ensure_ascii=False, indent=2))
    print(f"{len(posts)} posts → {out_path}")


if __name__ == "__main__":
    main()
