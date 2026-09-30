"""End-to-end checks on the models dbt builds from tests/fixtures (run by CI after `dbt build`)."""

import base64
import json
import os
import urllib.error
import urllib.request

import pytest

pytestmark = pytest.mark.e2e


def query(sql: str, user: str | None = None, password: str | None = None) -> list[dict]:
    user = user or os.environ["CLICKHOUSE_USER"]
    password = password if password is not None else os.environ["CLICKHOUSE_PASSWORD"]
    url = f"http://{os.environ.get('CLICKHOUSE_HOST', 'localhost')}:{os.environ.get('CLICKHOUSE_HTTP_PORT', '8123')}/"
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    request = urllib.request.Request(
        url, data=f"{sql} FORMAT JSON".encode(), headers={"Authorization": f"Basic {token}"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["data"]


def scalar(sql: str):
    return next(iter(query(sql)[0].values()))


def test_every_fixture_row_reaches_staging():
    assert int(scalar("select count() from reddit_analytics.stg_reddit__posts")) == 12
    assert int(scalar("select count() from reddit_analytics.stg_reddit__comments")) == 14


def test_multi_word_tools_are_found():
    rows = query(
        "select distinct tool from reddit_analytics.fct_post_tool_mentions "
        "where tool in ('Power BI', 'SQL Server', 'Delta Lake')"
    )
    assert {r["tool"] for r in rows} == {"Power BI", "SQL Server", "Delta Lake"}


def test_sql_server_agent_is_not_counted_as_an_ai_agent():
    assert int(scalar(
        "select count() from reddit_analytics.fct_comment_tool_mentions "
        "where comment_id = 'cc001' and tool = 'AI Agent'"
    )) == 0


def test_automoderator_and_removed_comments_stay_out_of_the_fact():
    assert int(scalar(
        "select count() from reddit_analytics.fct_comment_tool_mentions where comment_id in ('cc007', 'cc009')"
    )) == 0


def test_removal_flags():
    rows = {r["post_id"]: r for r in query(
        "select post_id, is_removed_at_capture, is_removed_later from reddit_analytics.stg_reddit__posts "
        "where post_id in ('ci005', 'ci010')"
    )}
    assert rows["ci005"]["is_removed_at_capture"] and not rows["ci005"]["is_removed_later"]
    assert rows["ci010"]["is_removed_later"] and not rows["ci010"]["is_removed_at_capture"]


def test_deleted_accounts_have_no_author_id():
    assert scalar("select author_id from reddit_analytics.stg_reddit__comments where comment_id = 'cc006'") is None


def test_dashboard_user_reads_marts_but_not_staging():
    password = os.environ["CLICKHOUSE_DASHBOARD_PASSWORD"]
    rows = query("select count() as n from reddit_analytics.mart_tool_mentions_by_month", "dashboard", password)
    assert int(rows[0]["n"]) > 0
    with pytest.raises(urllib.error.HTTPError):
        query("select count() from reddit_analytics.stg_reddit__posts", "dashboard", password)
