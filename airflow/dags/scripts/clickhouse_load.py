"""
Load the NDJSON that lives in MinIO into ClickHouse raw_stories.

We use ClickHouse's native `s3()` table function so ClickHouse reads the file
straight from MinIO ― no data round-trips through the Airflow worker. This is
the "L" (load) step of ELT and a very ClickHouse-idiomatic pattern.

    INSERT INTO hackernews.raw_stories
    SELECT ... FROM s3('http://minio:9000/<bucket>/<key>', key, secret, 'JSONEachRow')
"""
from __future__ import annotations

import logging
import os

import clickhouse_connect

log = logging.getLogger(__name__)

# column -> how to read it out of the NDJSON. Must match both the extractor's
# record keys and clickhouse/init/01_init.sql. The three timestamps arrive as
# strings and are cast on the way in.
COLUMNS: dict[str, str] = {
    "story_id": "story_id",
    "title": "title",
    "story_text": "story_text",
    "author": "author",
    "score": "score",
    "num_comments": "num_comments",
    "permalink": "permalink",
    "url": "url",
    "post_type": "post_type",
    "is_self": "is_self",
    "created_utc": "toDateTime(created_utc)",
    "ingested_at": "toDateTime(ingested_at)",
    "ingest_date": "toDate(ingest_date)",
}

# JSONEachRow needs an explicit structure for the s3() function
S3_STRUCTURE = (
    "story_id String, title String, story_text String, author String, "
    "score Int32, num_comments Int32, permalink String, url String, "
    "post_type String, is_self UInt8, created_utc String, "
    "ingested_at String, ingest_date String"
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
    Airflow entrypoint. Reads the object key from XCom (task `extract_stories`)
    unless one is passed explicitly. Returns rows loaded.
    """
    if s3_key is None and ti is not None:
        s3_key = ti.xcom_pull(task_ids="extract_stories")
    if not s3_key:
        raise ValueError("No s3_key provided / found in XCom")

    database = os.environ.get("CLICKHOUSE_DB", "hackernews")
    bucket = os.environ["MINIO_BUCKET"]
    # inside the docker network ClickHouse reaches MinIO at http://minio:9000
    endpoint = os.environ["MINIO_ENDPOINT"].rstrip("/")
    s3_url = f"{endpoint}/{bucket}/{s3_key}"
    access = os.environ["MINIO_ROOT_USER"]
    secret = os.environ["MINIO_ROOT_PASSWORD"]

    target_cols = ", ".join(COLUMNS)
    select_cols = ", ".join(
        f"{expr} AS {name}" for name, expr in COLUMNS.items()
    )

    query = f"""
        INSERT INTO {database}.raw_stories ({target_cols})
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
        f"SELECT count() FROM {database}.raw_stories "
        "WHERE ingested_at >= now() - INTERVAL 1 HOUR"
    )
    log.info("Loaded from %s ; raw_stories (last hour) = %s", s3_url, rows)
    return int(rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    load_minio_to_clickhouse(s3_key=sys.argv[1])
