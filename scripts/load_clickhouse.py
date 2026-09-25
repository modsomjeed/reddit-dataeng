"""Load raw post files from the S3 raw bucket into reddit.posts; ClickHouse reads the bucket itself."""

import argparse
import base64
import urllib.parse
import urllib.request
from datetime import date, timedelta

from settings import read_env

# ClickHouse reaches the bucket over the compose network, whichever machine runs this script
CLICKHOUSE_S3_ENDPOINT = "http://rustfs:9000"

INSERT_SQL = """
INSERT INTO reddit.posts (
    id, subreddit, author, title, selftext, url, permalink,
    link_flair_text, is_self, over_18, score, num_comments,
    upvote_ratio, removed_by_category, created_utc, retrieved_on, raw
)
SELECT
    JSONExtractString(json, 'id'),
    JSONExtractString(json, 'subreddit'),
    JSONExtractString(json, 'author'),
    JSONExtractString(json, 'title'),
    JSONExtractString(json, 'selftext'),
    JSONExtractString(json, 'url'),
    JSONExtractString(json, 'permalink'),
    JSONExtract(json, 'link_flair_text', 'Nullable(String)'),
    JSONExtractBool(json, 'is_self'),
    JSONExtractBool(json, 'over_18'),
    JSONExtractInt(json, 'score'),
    JSONExtractInt(json, 'num_comments'),
    JSONExtractFloat(json, 'upvote_ratio'),
    JSONExtract(json, 'removed_by_category', 'Nullable(String)'),
    toDateTime(JSONExtractInt(json, 'created_utc'), 'UTC'),
    toDateTime(JSONExtractInt(json, 'retrieved_on'), 'UTC'),
    json
FROM s3({url}, {access_key}, {secret_key}, 'JSONAsString')
"""


def quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def run_query(env: dict[str, str], query: str) -> None:
    url = f"http://{env['CLICKHOUSE_HOST']}:{env['CLICKHOUSE_HTTP_PORT']}/"
    token = base64.b64encode(f"{env['CLICKHOUSE_USER']}:{env['CLICKHOUSE_PASSWORD']}".encode()).decode()
    request = urllib.request.Request(url, data=query.encode(), headers={"Authorization": f"Basic {token}"})
    with urllib.request.urlopen(request, timeout=300):
        pass


def load(env: dict[str, str], key_pattern: str) -> None:
    url = f"{CLICKHOUSE_S3_ENDPOINT}/{env['S3_BUCKET']}/{key_pattern}"
    run_query(env, INSERT_SQL.format(
        url=quote(url),
        access_key=quote(env["RUSTFS_ACCESS_KEY"]),
        secret_key=quote(env["RUSTFS_SECRET_KEY"]),
    ))
    print(f"loaded {url}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, help="YYYY-MM-DD; omit to load every file")
    parser.add_argument("--end", type=date.fromisoformat, help="YYYY-MM-DD, inclusive; defaults to --start")
    args = parser.parse_args()

    env = read_env()
    if args.start is None:
        load(env, "posts/*.json")
        return

    day = args.start
    while day <= (args.end or args.start):
        load(env, f"posts/{day.isoformat()}.json")
        day += timedelta(days=1)


if __name__ == "__main__":
    main()
