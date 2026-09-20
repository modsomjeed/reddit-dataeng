"""
hn_elt_dag ― end-to-end ELT for the Hacker News project.

    extract_stories          (E)  Algolia API → NDJSON → MinIO (bronze)
        │
    load_clickhouse_raw      (L)  MinIO → ClickHouse raw_stories
        │
    dbt_run                  (T)  staging (silver) + marts (gold)
        │
    dbt_test                 (Governance) schema + data-quality tests
        │
    dbt_source_freshness     (Governance) is the bronze layer still current?
        │
    export_to_sheets         (Data product) mart → Google Sheet → Looker Studio

Runs daily and asks the API for the logical date's UTC day, so a backfill or a
re-run fetches exactly the same window. Idempotent: raw_stories keeps every
snapshot, dbt de-duplicates to the latest state per story_id.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

from scripts.hn_extract import extract_hn_to_minio
from scripts.clickhouse_load import load_minio_to_clickhouse
from scripts.export_to_sheets import export_marts_to_sheets

DBT_DIR = "/opt/dbt"
# dbt reads connection settings from env (see dbt/profiles.yml)
DBT_ENV = (
    "DBT_CLICKHOUSE_HOST=$CLICKHOUSE_HOST "
    "DBT_CLICKHOUSE_PORT=$CLICKHOUSE_HTTP_PORT "
    "DBT_CLICKHOUSE_USER=$CLICKHOUSE_USER "
    "DBT_CLICKHOUSE_PASSWORD=$CLICKHOUSE_PASSWORD "
    "DBT_CLICKHOUSE_SCHEMA=$CLICKHOUSE_DB"
)

default_args = {
    "owner": "data-eng",
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
    "depends_on_past": False,
}


def _dbt(command: str) -> str:
    return f"cd {DBT_DIR} && {DBT_ENV} dbt {command} --profiles-dir {DBT_DIR}"


with DAG(
    dag_id="hn_elt",
    description="Hacker News ELT: Algolia→MinIO→ClickHouse→dbt→Looker",
    start_date=datetime(2026, 1, 1),
    schedule="0 6 * * *",          # every day at 06:00
    catchup=False,
    # dbt_run / dbt_test rebuild the same models in the same schema, so two
    # dag runs at once would race. Backfilling a date range must stay serial.
    max_active_runs=1,
    default_args=default_args,
    tags=["hackernews", "elt", "clickhouse", "dbt", "bootcamp"],
) as dag:

    extract_stories = PythonOperator(
        task_id="extract_stories",
        python_callable=extract_hn_to_minio,
        op_kwargs={"ds": "{{ ds }}", "run_id": "{{ run_id }}"},
    )

    load_clickhouse_raw = PythonOperator(
        task_id="load_clickhouse_raw",
        python_callable=load_minio_to_clickhouse,
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=_dbt("run"),
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=_dbt("test"),
    )

    # `dbt test` does not evaluate source freshness ― it needs its own command.
    dbt_source_freshness = BashOperator(
        task_id="dbt_source_freshness",
        bash_command=_dbt("source freshness"),
    )

    export_sheets = PythonOperator(
        task_id="export_to_sheets",
        python_callable=export_marts_to_sheets,
    )

    (
        extract_stories
        >> load_clickhouse_raw
        >> dbt_run
        >> dbt_test
        >> dbt_source_freshness
        >> export_sheets
    )
