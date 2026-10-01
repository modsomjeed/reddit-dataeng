"""Email alert for a task that has failed for good (after its retries)."""

import logging
import os
import smtplib
from email.message import EmailMessage

log = logging.getLogger(__name__)


def failure_message(context: dict) -> EmailMessage:
    ti = context["ti"]
    msg = EmailMessage()
    msg["Subject"] = f"[Airflow] {ti.dag_id}.{ti.task_id} failed"
    msg["From"] = os.environ.get("ALERT_EMAIL_FROM", "airflow@reddit-dataeng.local")
    msg["To"] = os.environ.get("ALERT_EMAIL_TO", "data-team@reddit-dataeng.local")
    msg.set_content(
        "\n".join(
            [
                f"DAG:          {ti.dag_id}",
                f"Task:         {ti.task_id}",
                f"Logical date: {context.get('logical_date')}",
                f"Attempts:     {ti.try_number}",
                f"Error:        {context.get('exception')}",
                f"Log:          {getattr(ti, 'log_url', None) or 'see the task log in the Airflow UI'}",
            ]
        )
    )
    return msg


def notify_failure(context: dict) -> None:
    # on_failure_callback runs only after the last retry, so each failure sends one email
    msg = failure_message(context)
    host = os.environ.get("SMTP_HOST", "mailpit")
    port = int(os.environ.get("SMTP_PORT", "1025"))
    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.send_message(msg)
        log.info("sent failure alert to %s", msg["To"])
    except OSError:
        # an alert that can't be sent must not hide the original failure
        log.exception("could not send failure alert through %s:%d", host, port)
