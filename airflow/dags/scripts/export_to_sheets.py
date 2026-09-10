"""
Export a dbt mart from ClickHouse into a Google Sheet so Looker Studio
(Google Data Studio) can read it.

Why a Google Sheet? A local ClickHouse container is not reachable from
Looker Studio's cloud servers. Pushing the small, already-aggregated mart to
a Sheet is the simplest robust bridge and keeps the warehouse private.
(See docs/looker_studio_setup.md for the alternative ngrok + MySQL route.)

This task is OPTIONAL and is skipped unless ENABLE_SHEETS_EXPORT=true and a
service-account json is mounted at GOOGLE_APPLICATION_CREDENTIALS.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

# marts we publish → each becomes a worksheet/tab in the Google Sheet
MARTS = ["agg_daily_activity", "fct_stories", "dim_authors"]


def _ch_client():
    import clickhouse_connect
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_HTTP_PORT", "8123")),
        username=os.environ["CLICKHOUSE_USER"],
        password=os.environ["CLICKHOUSE_PASSWORD"],
    )


def export_marts_to_sheets(**_) -> str:
    if os.environ.get("ENABLE_SHEETS_EXPORT", "false").lower() != "true":
        log.info("ENABLE_SHEETS_EXPORT is not true ― skipping export.")
        return "skipped"

    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"], scopes=scopes
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(os.environ["GSHEET_ID"])

    ch = _ch_client()
    # dbt appends the custom schema to the profile schema, so models configured
    # with `+schema: marts` land in `<CLICKHOUSE_DB>_marts`, not `<CLICKHOUSE_DB>`.
    marts_db = f"{os.environ.get('CLICKHOUSE_DB', 'hackernews')}_marts"

    for mart in MARTS:
        df = ch.query_df(f"SELECT * FROM {marts_db}.{mart}")
        # Looker/Sheets don't like NaN or datetimes ― stringify safely
        df = df.astype(object).where(df.notna(), "").astype(str)
        try:
            ws = sh.worksheet(mart)
            ws.clear()
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=mart, rows=1000, cols=40)
        ws.update([df.columns.tolist()] + df.values.tolist())
        log.info("Exported %s (%d rows) to sheet tab '%s'", mart, len(df), mart)

    return "exported"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(export_marts_to_sheets())
