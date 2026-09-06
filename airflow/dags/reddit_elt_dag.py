"""
reddit_elt_dag ― end-to-end ELT for the r/dataengineering project.

    extract_reddit           (E)  PRAW → NDJSON → MinIO (bronze)
        │
    load_clickhouse_raw      (L)  MinIO → ClickHouse raw_posts
        │
    dbt_run                  (T)  staging (silver) + marts (gold)
        │
    dbt_test                 (Governance) schema + data-quality tests
        │
    export_to_sheets         (Data product) mart → Google Sheet → Looker Studio

Runs daily. Idempotent: raw_posts keeps every snapshot, dbt de-duplicates to
the latest state per post_id.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

from scripts.reddit_extract import extract_reddit_to_minio
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

with DAG(
    dag_id="reddit_elt",
    description="Reddit r/dataengineering ELT: PRAW→MinIO→ClickHouse→dbt→Looker",
    start_date=datetime(2026, 1, 1),
    schedule="0 6 * * *",          # every day at 06:00
    catchup=False,
    default_args=default_args,
    tags=["reddit", "elt", "clickhouse", "dbt", "bootcamp"],
) as dag:

    extract_reddit = PythonOperator(
        task_id="extract_reddit",
        python_callable=extract_reddit_to_minio,
        op_kwargs={"ds": "{{ ds }}", "run_id": "{{ run_id }}"},
    )

    load_clickhouse_raw = PythonOperator(
        task_id="load_clickhouse_raw",
        python_callable=load_minio_to_clickhouse,
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {DBT_DIR} && {DBT_ENV} dbt run --profiles-dir {DBT_DIR}",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_DIR} && {DBT_ENV} dbt test --profiles-dir {DBT_DIR}",
    )

    export_sheets = PythonOperator(
        task_id="export_to_sheets",
        python_callable=export_marts_to_sheets,
    )

    extract_reddit >> load_clickhouse_raw >> dbt_run >> dbt_test >> export_sheets
