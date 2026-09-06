"""
Load the NDJSON that lives in MinIO into ClickHouse raw_posts.

We use ClickHouse's native `s3()` table function so ClickHouse reads the file
straight from MinIO ― no data round-trips through the Airflow worker. This is
the "L" (load) step of ELT and a very ClickHouse-idiomatic pattern.

    INSERT INTO reddit.raw_posts
    SELECT ... FROM s3('http://minio:9000/<bucket>/<key>', key, secret, 'JSONEachRow')
"""
from __future__ import annotations

import logging
import os

import clickhouse_connect

log = logging.getLogger(__name__)

# column list must match clickhouse/init/01_init.sql
COLUMNS = [
    "post_id", "subreddit", "title", "selftext", "author", "score",
    "upvote_ratio", "num_comments", "permalink", "url", "flair",
    "over_18", "is_self", "created_utc", "ingested_at", "ingest_date",
]

# JSONEachRow needs an explicit structure for the s3() function
S3_STRUCTURE = (
    "post_id String, subreddit String, title String, selftext String, "
    "author String, score Int32, upvote_ratio Float32, num_comments Int32, "
    "permalink String, url String, flair String, over_18 UInt8, is_self UInt8, "
    "created_utc String, ingested_at String, ingest_date String"
)


def _client():
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_HTTP_PORT", "8123")),
        username=os.environ["CLICKHOUSE_USER"],
        password=os.environ["CLICKHOUSE_PASSWORD"],
    )


def load_minio_to_clickhouse(ti=None, s3_key: str | None = None, **_) -> int:
    """
    Airflow entrypoint. Reads the object key from XCom (task `extract_reddit`)
    unless one is passed explicitly. Returns rows loaded.
    """
    if s3_key is None and ti is not None:
        s3_key = ti.xcom_pull(task_ids="extract_reddit")
    if not s3_key:
        raise ValueError("No s3_key provided / found in XCom")

    bucket = os.environ["MINIO_BUCKET"]
    # inside the docker network ClickHouse reaches MinIO at http://minio:9000
    endpoint = os.environ["MINIO_ENDPOINT"].rstrip("/")
    s3_url = f"{endpoint}/{bucket}/{s3_key}"
    access = os.environ["MINIO_ROOT_USER"]
    secret = os.environ["MINIO_ROOT_PASSWORD"]

    col_csv = ", ".join(COLUMNS)
    # cast the two string timestamps to DateTime / Date on the way in
    select_cols = col_csv.replace(
        "created_utc", "toDateTime(created_utc) AS created_utc"
    ).replace(
        "ingested_at", "toDateTime(ingested_at) AS ingested_at"
    ).replace(
        "ingest_date", "toDate(ingest_date) AS ingest_date"
    )

    query = f"""
        INSERT INTO reddit.raw_posts ({col_csv})
        SELECT {select_cols}
        FROM s3(
            '{s3_url}',
            '{access}',
            '{secret}',
            'JSONEachRow',
            '{S3_STRUCTURE}'
        )
    """

    client = _client()
    client.command(query)
    rows = client.command(
        "SELECT count() FROM reddit.raw_posts WHERE ingested_at >= now() - INTERVAL 1 HOUR"
    )
    log.info("Loaded from %s ; raw_posts (last hour) = %s", s3_url, rows)
    return int(rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    load_minio_to_clickhouse(s3_key=sys.argv[1])
