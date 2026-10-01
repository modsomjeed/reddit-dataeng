"""Check the alert path: a manual-only DAG whose one task always fails, so a failure email should arrive."""

from datetime import datetime

from airflow.sdk import dag, task

from alerts import notify_failure


@dag(
    schedule=None,
    start_date=datetime(2026, 9, 22),
    catchup=False,
    # no retries, so the alert is sent straight away
    default_args={"retries": 0, "on_failure_callback": notify_failure},
    tags=["alerts"],
)
def alert_check():
    @task
    def always_fails():
        raise RuntimeError("alert_check: this task fails on purpose to test failure alerts")

    always_fails()


alert_check()
