"""Daily r/dataengineering pipeline: extract a day of posts and comments, load them into ClickHouse, rebuild dbt."""

from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag
from airflow.timetables.interval import CronDataIntervalTimetable

PROJECT = "/opt/project"
DBT = "/opt/airflow/dbt-venv/bin/dbt"

default_args = {
    "retries": 3,
    "retry_delay": timedelta(minutes=1),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=10),
}


@dag(
    # Airflow 3's plain cron schedule sets {{ ds }} to the run's own date, so the 02:00
    # run would extract a day that has only just started. The data-interval timetable
    # makes {{ ds }} the previous, complete day. 02:00 UTC also gives the archive time
    # to pick up that day's last posts.
    schedule=CronDataIntervalTimetable("0 2 * * *", timezone="UTC"),
    start_date=datetime(2026, 9, 22),
    catchup=True,
    # one run at a time, so a backfill can't race itself in dbt
    max_active_runs=1,
    default_args=default_args,
    tags=["reddit"],
)
def reddit_daily():
    # {{ ds }} is the start of the data interval, i.e. the day this run is responsible for.
    # --force re-extracts the day, so rerunning a date refreshes it instead of skipping it.
    # The raw tables are ReplacingMergeTrees keyed on id, so reloading a day adds no duplicates.
    loads = []
    for kind in ("posts", "comments"):
        extract = BashOperator(
            task_id=f"extract_{kind}",
            bash_command=f"python {PROJECT}/scripts/extract_reddit.py --kind {kind} --start {{{{ ds }}}} --force",
        )
        load = BashOperator(
            task_id=f"load_{kind}",
            bash_command=(
                f"python {PROJECT}/scripts/load_clickhouse.py --kind {kind} "
                "--start {{ ds }} --end {{ ds }}"
            ),
        )
        extract >> load
        loads.append(load)

    # fail loudly if the archive has stopped returning new posts, before rebuilding on stale data
    dbt_source_freshness = BashOperator(
        task_id="dbt_source_freshness",
        bash_command=(
            f"cd {PROJECT}/dbt/reddit && {DBT} source freshness --profiles-dir . "
            "--target-path /tmp/dbt/target --log-path /tmp/dbt/logs"
        ),
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=(
            f"cd {PROJECT}/dbt/reddit && {DBT} build --profiles-dir . "
            "--target-path /tmp/dbt/target --log-path /tmp/dbt/logs"
        ),
    )

    loads >> dbt_source_freshness >> dbt_build


reddit_daily()
