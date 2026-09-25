"""Load the raw post files in data/raw into the reddit.posts table in ClickHouse."""

import argparse
import base64
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "posts"
COLUMNS = [
    "id", "subreddit", "author", "title", "selftext", "url", "permalink",
    "link_flair_text", "is_self", "over_18", "score", "num_comments",
    "upvote_ratio", "removed_by_category", "created_utc", "retrieved_on",
]


def read_env() -> dict[str, str]:
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return {**env, **os.environ}


def insert(env: dict[str, str], rows: list[dict]) -> None:
    query = "INSERT INTO reddit.posts FORMAT JSONEachRow"
    url = f"http://localhost:{env['CLICKHOUSE_HTTP_PORT']}/?{urllib.parse.urlencode({'query': query})}"
    body = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows).encode()
    token = base64.b64encode(f"{env['CLICKHOUSE_USER']}:{env['CLICKHOUSE_PASSWORD']}".encode()).decode()
    request = urllib.request.Request(url, data=body, headers={"Authorization": f"Basic {token}"})
    with urllib.request.urlopen(request, timeout=60):
        pass


def to_row(post: dict) -> dict:
    row = {column: post[column] for column in COLUMNS}
    row["raw"] = json.dumps(post, ensure_ascii=False)
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", help="YYYY-MM-DD; defaults to the first file")
    parser.add_argument("--end", help="YYYY-MM-DD, inclusive; defaults to the last file")
    args = parser.parse_args()

    env = read_env()
    for path in sorted(RAW_DIR.glob("*.json")):
        day = path.stem
        if (args.start and day < args.start) or (args.end and day > args.end):
            continue
        posts = json.loads(path.read_text())
        if posts:
            insert(env, [to_row(post) for post in posts])
        print(f"{day}: {len(posts)} posts loaded", flush=True)


if __name__ == "__main__":
    main()
