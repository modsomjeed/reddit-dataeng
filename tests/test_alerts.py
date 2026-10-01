from types import SimpleNamespace

import alerts


def failed_context():
    ti = SimpleNamespace(dag_id="reddit_ingest", task_id="load_posts", try_number=4, log_url="http://airflow/log")
    return {"ti": ti, "logical_date": "2026-09-30T02:00:00+00:00", "exception": RuntimeError("ClickHouse is down")}


class FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout):
        self.address = (host, port)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def send_message(self, msg):
        FakeSMTP.sent.append((self.address, msg))


def test_failure_message_names_the_task_and_the_error(monkeypatch):
    monkeypatch.setenv("ALERT_EMAIL_TO", "lead@example.com")
    msg = alerts.failure_message(failed_context())

    assert msg["Subject"] == "[Airflow] reddit_ingest.load_posts failed"
    assert msg["To"] == "lead@example.com"
    body = msg.get_content()
    assert "2026-09-30T02:00:00+00:00" in body
    assert "Attempts:     4" in body
    assert "ClickHouse is down" in body
    assert "http://airflow/log" in body


def test_notify_failure_sends_through_the_configured_server(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "2525")
    monkeypatch.setattr(alerts.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent.clear()

    alerts.notify_failure(failed_context())

    [(address, msg)] = FakeSMTP.sent
    assert address == ("smtp.test", 2525)
    assert msg["Subject"] == "[Airflow] reddit_ingest.load_posts failed"


def test_notify_failure_does_not_raise_when_the_mail_server_is_down(monkeypatch):
    def refuse(*args, **kwargs):
        raise ConnectionRefusedError

    monkeypatch.setattr(alerts.smtplib, "SMTP", refuse)
    alerts.notify_failure(failed_context())
