"""Shared paths and the Assets that connect the ingest DAG to the dbt DAG."""

from datetime import timedelta

from airflow.sdk import Asset

PROJECT = "/opt/project"
DBT = "/opt/airflow/dbt-venv/bin/dbt"

# One Asset per raw table. reddit_ingest marks them updated after each load;
# reddit_dbt runs once both have been updated.
RAW_TABLES = {
    "posts": Asset(name="reddit.posts", uri="clickhouse://clickhouse:8123/reddit/posts"),
    "comments": Asset(name="reddit.comments", uri="clickhouse://clickhouse:8123/reddit/comments"),
}

DEFAULT_ARGS = {
    "retries": 3,
    "retry_delay": timedelta(minutes=1),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=10),
}
