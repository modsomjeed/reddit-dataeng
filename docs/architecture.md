# Architecture

## Overview

This project is an end-to-end **ELT** pipeline for posts from
[r/dataengineering](https://reddit.com/r/dataengineering). Every layer runs
locally in Docker; the only cloud dependency is Looker Studio (Google Data
Studio) for the dashboard, fed through a Google Sheet.

```
                          ┌─────────────────────────────────────────────┐
                          │                 Airflow                     │
                          │            (LocalExecutor)                  │
                          │                                             │
  Reddit API  ──PRAW──▶   │  extract_reddit ─▶ load_clickhouse_raw ─▶   │
  (r/dataengineering)     │        │                    │              │
                          │        ▼                    ▼              │
                          │   ┌─────────┐   s3()   ┌───────────┐       │
                          │   │  MinIO  │◀────────▶│ ClickHouse│       │
                          │   │ (bronze)│          │  raw_posts│       │
                          │   └─────────┘          └─────┬─────┘       │
                          │                              │ dbt_run     │
                          │                     ┌────────▼────────┐    │
                          │                     │ staging (silver)│    │
                          │                     │  + marts (gold) │    │
                          │                     └────────┬────────┘    │
                          │              dbt_test ◀───────┘            │
                          │                     │ export_to_sheets     │
                          └─────────────────────┼──────────────────────┘
                                                ▼
                                        Google Sheet
                                                │
                                                ▼
                                   Looker Studio dashboard
```

## Layers (medallion)

| Layer  | Where              | What                                                        |
|--------|--------------------|-------------------------------------------------------------|
| Bronze | MinIO `reddit-raw` | Raw NDJSON exactly as pulled from the Reddit API.           |
| Bronze | ClickHouse `raw_posts` | Every ingest snapshot, partitioned by `ingest_date`.    |
| Silver | dbt `stg_reddit__posts` | Cleaned + de-duplicated to latest snapshot per post.   |
| Gold   | dbt `fct_posts`, `dim_authors`, `agg_daily_subreddit` | Business-ready marts. |

## Why these tools

- **Airflow** ― orchestration, scheduling, retries, XCom hand-off between tasks.
- **MinIO** ― S3-compatible data lake so raw data is durable and replayable
  (you can re-load into ClickHouse without re-hitting the Reddit API).
- **ClickHouse** ― columnar OLAP warehouse; the `s3()` table function reads
  straight from MinIO, and aggregations over posts are extremely fast.
- **dbt** ― analytics engineering: modular SQL, lineage, tests, docs.
- **Looker Studio** ― the data product (dashboard) the end user actually sees.

## Data flow detail

1. `extract_reddit` merges `hot + new + top(week)`, de-dupes by post id, writes
   NDJSON to `s3://reddit-raw/subreddit=dataengineering/ingest_date=YYYY-MM-DD/`.
2. `load_clickhouse_raw` runs `INSERT INTO raw_posts SELECT ... FROM s3(...)`.
3. `dbt_run` builds silver + gold; `dbt_test` enforces quality (governance).
4. `export_to_sheets` publishes marts to a Google Sheet for Looker Studio.

## Idempotency & incrementality

`raw_posts` is append-only (keeps history), and `stg_reddit__posts` de-duplicates
with `row_number() over (partition by post_id order by ingested_at desc)`. Re-running
a day is safe. A natural next step is to make `raw_posts` load incremental by
`ingest_date` and convert marts to dbt incremental models.
