"""Reverse ETL: email the DE lead a weekly digest built from the marts (run by the reddit_digest DAG).

Reads only mart tables, as the read-only `dashboard` user, so the digest can never show more
than the dashboard does.
"""

import argparse
import base64
import json
import logging
import smtplib
import urllib.request
from datetime import date
from email.message import EmailMessage

from settings import read_env, setup_logging

log = logging.getLogger("digest")

TOP_N = 3


def fetch(env: dict[str, str], query: str) -> list[dict]:
    url = f"http://{env['CLICKHOUSE_HOST']}:{env['CLICKHOUSE_HTTP_PORT']}/"
    token = base64.b64encode(f"dashboard:{env['CLICKHOUSE_DASHBOARD_PASSWORD']}".encode()).decode()
    request = urllib.request.Request(
        url, data=f"{query} FORMAT JSONEachRow".encode(), headers={"Authorization": f"Basic {token}"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return [json.loads(line) for line in response.read().decode().splitlines()]


def month_label(month: str, today: date) -> str:
    first = date.fromisoformat(month)
    label = first.strftime("%b %Y")
    return f"{label} (so far)" if (first.year, first.month) == (today.year, today.month) else label


def window_label(months: list[str]) -> str:
    return f"{date.fromisoformat(min(months)):%b %Y} – {date.fromisoformat(max(months)):%b %Y}"


def build_digest(data: dict[str, list[dict]], today: date, dashboard_url: str) -> str:
    periods = {p: [w["month"] for w in data["windows"] if w["period"] == p] for p in ("first", "last")}
    lines = [
        f"AI share of the conversation, {window_label(periods['last'])} vs {window_label(periods['first'])}",
    ]
    for row in sorted(data["ai_change"], key=lambda r: r["measure"], reverse=True):
        lines.append(
            f"  {row['measure']:<12} {row['first_share_pct']:.1f}% → {row['last_share_pct']:.1f}%"
            f"  ({row['change_pts']:+.1f} pts, ×{row['growth_ratio']:.1f})"
        )

    latest = sorted({r["month"] for r in data["by_month"]})[-2:]
    lines += ["", f"Latest months: {', '.join(month_label(m, today) for m in latest)}"]
    for measure in ("Post titles", "Comments"):
        shares = {r["month"]: r["share_pct"] for r in data["by_month"] if r["measure"] == measure}
        lines.append(f"  {measure:<12} " + " → ".join(f"{shares.get(m, 0):.1f}%" for m in latest))

    titles = [r for r in data["tools"] if r["measure"] == "Post titles"]
    other = sorted((r for r in titles if not r["is_ai"]), key=lambda r: r["change_pts"])
    ai = sorted((r for r in titles if r["is_ai"]), key=lambda r: r["change_pts"], reverse=True)
    sections = [
        ("AI tools rising fastest", ai[:TOP_N]),
        ("Other tools rising most", list(reversed(other[-TOP_N:]))),
        ("Other tools falling most", other[:TOP_N]),
    ]
    for title, rows in sections:
        lines += ["", f"{title} (share of post titles, pts)"]
        lines += [f"  {r['tool']:<16} {r['change_pts']:+.1f}" for r in rows]

    lines += ["", f"Dashboard: {dashboard_url}"]
    return "\n".join(lines)


def digest_message(env: dict[str, str], body: str, today: date) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"[r/dataengineering] Weekly AI vs stack digest, {today.isoformat()}"
    msg["From"] = env.get("DIGEST_EMAIL_FROM", "airflow@reddit-dataeng.local")
    msg["To"] = env.get("DIGEST_EMAIL_TO", "de-lead@reddit-dataeng.local")
    msg.set_content(body)
    return msg


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat, default=date.today(), help="run date, YYYY-MM-DD")
    args = parser.parse_args()

    setup_logging()
    env = read_env()
    data = {
        "windows": fetch(env, "select toString(month) as month, period from reddit_analytics.dim_comparison_windows"),
        "ai_change": fetch(env, "select * from reddit_analytics.mart_ai_share_change"),
        "by_month": fetch(env, "select toString(month) as month, measure, share_pct "
                               "from reddit_analytics.mart_ai_share_by_month"),
        "tools": fetch(env, "select tool, is_ai, measure, change_pts from reddit_analytics.mart_tool_share_change"),
    }
    body = build_digest(data, args.date, env.get("DASHBOARD_URL", "http://localhost:8501"))
    msg = digest_message(env, body, args.date)

    host, port = env.get("SMTP_HOST", "localhost"), int(env.get("SMTP_PORT", "1025"))
    with smtplib.SMTP(host, port, timeout=10) as smtp:
        smtp.send_message(msg)
    log.info("sent digest to %s", msg["To"])


if __name__ == "__main__":
    main()
