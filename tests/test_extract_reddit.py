import json
import urllib.error
from datetime import UTC, date, datetime

import pytest

import extract_reddit

DAY = date(2025, 5, 31)
DAY_START = int(datetime(2025, 5, 31, tzinfo=UTC).timestamp())
DAY_END = DAY_START + 86400


def item(item_id: str, created_utc: int) -> dict:
    return {"id": item_id, "created_utc": created_utc}


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(extract_reddit.time, "sleep", lambda seconds: None)


def test_fetch_day_queries_a_week_wide_window(monkeypatch):
    calls = []

    def fake_fetch_page(kind, subreddit, after, before):
        calls.append((after, before))
        return [item("a", DAY_START + 10)]

    monkeypatch.setattr(extract_reddit, "fetch_page", fake_fetch_page)
    extract_reddit.fetch_day("comments", "dataengineering", DAY)

    # narrow windows make the archive time out, so `before` must reach a week past the day
    assert calls == [(DAY_START, DAY_END + 7 * 86400)]


def test_fetch_day_pages_until_it_passes_the_end_of_the_day(monkeypatch):
    first_page = [item(f"p1-{i}", DAY_START + i) for i in range(100)]
    second_page = [item(f"p2-{i}", DAY_START + 200 + i) for i in range(99)] + [item("next-day", DAY_END + 5)]
    pages = iter([first_page, second_page])
    afters = []

    def fake_fetch_page(kind, subreddit, after, before):
        afters.append(after)
        return next(pages)

    monkeypatch.setattr(extract_reddit, "fetch_page", fake_fetch_page)
    items = extract_reddit.fetch_day("comments", "dataengineering", DAY)

    assert len(items) == 199
    assert all(i["created_utc"] < DAY_END for i in items)
    # the second page starts one second before the last item seen, so ties aren't skipped
    assert afters == [DAY_START, DAY_START + 99 - 1]


def test_fetch_day_steps_forward_when_a_whole_page_shares_one_second(monkeypatch):
    same_second = [item(f"s{i}", DAY_START) for i in range(100)]
    pages = iter([same_second, []])
    afters = []

    def fake_fetch_page(kind, subreddit, after, before):
        afters.append(after)
        return next(pages)

    monkeypatch.setattr(extract_reddit, "fetch_page", fake_fetch_page)
    extract_reddit.fetch_day("comments", "dataengineering", DAY)

    assert afters == [DAY_START, DAY_START + 1]


def test_fetch_page_retries_when_the_archive_rejects_a_request(monkeypatch, caplog):
    responses = [
        urllib.error.HTTPError("url", 422, "Unprocessable Entity", {}, None),
        urllib.error.HTTPError("url", 422, "Unprocessable Entity", {}, None),
        json.dumps({"data": [item("ok", DAY_START)]}).encode(),
    ]

    class Response:
        def __init__(self, body):
            self.body = body

        def read(self):
            return self.body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout):
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return Response(response)

    monkeypatch.setattr(extract_reddit.urllib.request, "urlopen", fake_urlopen)
    assert extract_reddit.fetch_page("posts", "dataengineering", DAY_START, DAY_END) == [item("ok", DAY_START)]
    # each retry is logged as a warning, so it stands out in the Airflow task log
    assert [r.levelname for r in caplog.records] == ["WARNING", "WARNING"]


def test_fetch_page_gives_up_after_the_last_attempt(monkeypatch):
    def always_422(request, timeout):
        raise urllib.error.HTTPError("url", 422, "Unprocessable Entity", {}, None)

    monkeypatch.setattr(extract_reddit.urllib.request, "urlopen", always_422)
    with pytest.raises(urllib.error.HTTPError):
        extract_reddit.fetch_page("posts", "dataengineering", DAY_START, DAY_END)


def test_extract_day_writes_one_deduplicated_file_per_kind_and_day(monkeypatch, fake_s3):
    monkeypatch.setattr(
        extract_reddit, "fetch_day", lambda kind, subreddit, day: [item("a", 1), item("b", 2), item("a", 1)]
    )
    extract_reddit.extract_day(fake_s3, "reddit-raw", "comments", "dataengineering", DAY, force=False)

    stored = json.loads(fake_s3.objects["comments/2025-05-31.json"])
    assert [i["id"] for i in stored] == ["a", "b"]


def test_extract_day_skips_a_day_already_in_the_bucket_unless_forced(monkeypatch, fake_s3):
    fake_s3.objects["posts/2025-05-31.json"] = b"[]"
    fetched = []
    monkeypatch.setattr(extract_reddit, "fetch_day", lambda kind, subreddit, day: fetched.append(day) or [])

    extract_reddit.extract_day(fake_s3, "reddit-raw", "posts", "dataengineering", DAY, force=False)
    assert fetched == []

    extract_reddit.extract_day(fake_s3, "reddit-raw", "posts", "dataengineering", DAY, force=True)
    assert fetched == [DAY]
