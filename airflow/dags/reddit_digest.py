"""Reverse ETL: every Monday, email the DE lead a digest of the latest marts."""

from datetime import datetime

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag
from airflow.timetables.trigger import CronTriggerTimetable

from reddit_assets import DEFAULT_ARGS, PROJECT


@dag(
    # Monday 06:00 UTC: after that day's 02:00 ingest and the dbt run it triggers.
    # Weekly because the AI share moves slowly; a daily email would just be noise.
    schedule=CronTriggerTimetable("0 6 * * 1", timezone="UTC"),
    start_date=datetime(2026, 9, 28),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["reddit", "reverse-etl"],
)
def reddit_digest():
    BashOperator(
        task_id="send_digest",
        bash_command=f"python {PROJECT}/scripts/send_digest.py --date {{{{ ds }}}}",
    )


reddit_digest()
