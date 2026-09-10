# Architecture

## Overview

This project is an end-to-end **ELT** pipeline for stories from
[Hacker News](https://news.ycombinator.com), read through the public
[HN Algolia API](https://hn.algolia.com/api). Every layer runs locally in
Docker; the only cloud dependency is Looker Studio (Google Data Studio) for the
dashboard, fed through a Google Sheet.

The project originally targeted r/dataengineering. Reddit closed self-service
API access in November 2025 and now requires a login even for the public JSON
listings, so the source moved to Hacker News while the architecture stayed the
same — see [`questions.md`](./questions.md) for the full reasoning.

```
                          ┌─────────────────────────────────────────────┐
                          │                 Airflow                     │
                          │            (LocalExecutor)                  │
                          │                                             │
  HN Algolia API ──HTTP─▶ │  extract_stories ─▶ load_clickhouse_raw ─▶  │
  (one UTC day per run)   │        │                    │              │
                          │        ▼                    ▼              │
                          │   ┌─────────┐   s3()   ┌────────────┐      │
                          │   │  MinIO  │◀────────▶│ ClickHouse │      │
                          │   │ (bronze)│          │ raw_stories│      │
                          │   └─────────┘          └─────┬──────┘      │
                          │                              │ dbt_run     │
                          │                     ┌────────▼────────┐    │
                          │                     │ staging (silver)│    │
                          │                     │  + marts (gold) │    │
                          │                     └────────┬────────┘    │
                          │      dbt_test ◀──────────────┘             │
                          │           │                                │
                          │  dbt_source_freshness                      │
                          │           │  export_to_sheets              │
                          └───────────┼────────────────────────────────┘
                                      ▼
                                Google Sheet
                                      │
                                      ▼
                          Looker Studio dashboard
```

## Layers (medallion)

| Layer  | Where | What |
|--------|-------|------|
| Bronze | MinIO `hn-raw` | Raw NDJSON exactly as pulled from the Algolia API. |
| Bronze | ClickHouse `hackernews.raw_stories` | Every ingest snapshot, partitioned by `ingest_date`. |
| Silver | dbt `stg_hn__stories` | De-duplicated to latest snapshot per story, HTML decoded. |
| Gold   | dbt `fct_stories`, `dim_authors`, `agg_daily_activity` | Business-ready marts. |

dbt appends the custom schema to the profile schema, so staging lands in
`hackernews_staging` and marts in `hackernews_marts`.

## Why these tools

- **Airflow** ― orchestration, scheduling, retries, XCom hand-off between tasks.
- **MinIO** ― S3-compatible data lake so raw data is durable and replayable
  (you can re-load into ClickHouse without re-hitting the API).
- **ClickHouse** ― columnar OLAP warehouse; the `s3()` table function reads
  straight from MinIO, and aggregations over stories are extremely fast.
- **dbt** ― analytics engineering: modular SQL, lineage, tests, docs.
- **Looker Studio** ― the data product (dashboard) the end user actually sees.

## Data flow detail

1. `extract_stories` asks Algolia for every story created during the logical
   date's UTC day and writes NDJSON to
   `s3://hn-raw/source=hackernews/ingest_date=YYYY-MM-DD/`.
2. `load_clickhouse_raw` runs `INSERT INTO raw_stories SELECT ... FROM s3(...)`.
3. `dbt_run` builds silver + gold; `dbt_test` enforces quality (governance).
4. `dbt_source_freshness` fails the run if the bronze layer has gone stale.
5. `export_to_sheets` publishes marts to a Google Sheet for Looker Studio.

### Why the extract walks backwards in time

Algolia returns at most 1000 hits for any single query, however you page it,
while a busy HN day produces around 1200 stories. Paging would therefore drop
the oldest couple of hundred stories every day without any error. Instead each
batch's oldest timestamp becomes the upper bound of the next request, and the
task compares the number of stories collected against the `nbHits` the API
reports, logging a warning when the day comes back incomplete.

## Idempotency & incrementality

Each run asks for one specific UTC day, so re-running or backfilling a date
fetches exactly the same window. `raw_stories` is append-only (keeps history),
and `stg_hn__stories` de-duplicates with
`row_number() over (partition by story_id order by ingested_at desc)`, so a
re-run refreshes scores rather than duplicating rows. A natural next step is to
make the raw load incremental by `ingest_date` and convert marts to dbt
incremental models.
