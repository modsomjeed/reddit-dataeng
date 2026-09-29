"""Daily ingestion: extract a day of r/dataengineering posts and comments into RustFS and load them into ClickHouse."""

from datetime import datetime

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag
from airflow.timetables.interval import CronDataIntervalTimetable

from reddit_assets import DEFAULT_ARGS, PROJECT, RAW_TABLES


@dag(
    # Airflow 3's plain cron schedule sets {{ ds }} to the run's own date, so the 02:00
    # run would extract a day that has only just started. The data-interval timetable
    # makes {{ ds }} the previous, complete day. 02:00 UTC also gives the archive time
    # to pick up that day's last posts.
    schedule=CronDataIntervalTimetable("0 2 * * *", timezone="UTC"),
    start_date=datetime(2026, 9, 22),
    catchup=True,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["reddit", "ingest"],
)
def reddit_ingest():
    # {{ ds }} is the start of the data interval, i.e. the day this run is responsible for.
    # --force re-extracts the day, so rerunning a date refreshes it instead of skipping it.
    # The raw tables are ReplacingMergeTrees keyed on id, so reloading a day adds no duplicates.
    for kind, asset in RAW_TABLES.items():
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
            # tells reddit_dbt this raw table has new data
            outlets=[asset],
        )
        extract >> load


reddit_ingest()
