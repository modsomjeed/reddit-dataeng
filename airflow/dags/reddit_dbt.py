"""Transform: once both raw tables have new data, check source freshness and rebuild the dbt models."""

from datetime import datetime

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag

from reddit_assets import DBT, DEFAULT_ARGS, PROJECT, RAW_TABLES

DBT_FLAGS = "--profiles-dir . --target-path /tmp/dbt/target --log-path /tmp/dbt/logs"


@dag(
    # Asset-based: runs when reddit_ingest has updated both raw tables, not on a clock.
    # During a long backfill, pause this DAG and unpause it afterwards to build once.
    schedule=list(RAW_TABLES.values()),
    start_date=datetime(2026, 9, 22),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["reddit", "dbt"],
)
def reddit_dbt():
    # a gate: if the archive has stopped returning new posts or comments, fail here
    # instead of rebuilding the marts (and the dashboard) on stale data
    dbt_source_freshness = BashOperator(
        task_id="dbt_source_freshness",
        bash_command=f"cd {PROJECT}/dbt/reddit && {DBT} source freshness {DBT_FLAGS}",
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"cd {PROJECT}/dbt/reddit && {DBT} build {DBT_FLAGS}",
    )

    dbt_source_freshness >> dbt_build


reddit_dbt()
