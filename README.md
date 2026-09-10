# Hacker News Data Engineering Pipeline

End-to-end **ELT** on stories from [Hacker News](https://news.ycombinator.com),
built with the stack from the bootcamp:

**HN Algolia API → MinIO → ClickHouse → dbt → Looker Studio**, orchestrated by **Airflow**.

> Project brief: pick one project from the Data Engineer Cafe list (Reddit ETL),
> use only that project's data, and rebuild it on your own stack
> (Airflow + dbt + ClickHouse + Google Data Studio) in your own repo.
>
> **Why not Reddit?** Reddit closed self-service API registration in November
> 2025 under its Responsible Builder Policy, and public `.json` listings now
> redirect to a login. Every new OAuth token needs manual approval. The source
> moved to Hacker News; the architecture, layers and orchestration are unchanged.
> Full reasoning and the alternatives considered: [`docs/questions.md`](docs/questions.md).

---

## Stack

| Concern              | Tool                          |
|----------------------|-------------------------------|
| Orchestration        | Apache Airflow (LocalExecutor)|
| Ingestion            | Python + HN Algolia API       |
| Data lake (bronze)   | MinIO (S3-compatible)         |
| Warehouse            | ClickHouse                    |
| Transformation       | dbt (`dbt-clickhouse`)        |
| Data governance      | dbt tests + source freshness  |
| Dashboard            | Looker Studio (Google Data Studio) |

Architecture diagram and layer details: [`docs/architecture.md`](docs/architecture.md).

---

## Quick start

### 1. Prerequisites
- Docker + Docker Compose

No API credentials are required — the HN Algolia API is public.

### 2. Configure
```bash
cp .env.example .env
# generate a Fernet key and paste into AIRFLOW_FERNET_KEY:
python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

### 3. Run
```bash
make build      # build Airflow image (dbt baked in)
make init       # start the stack, wait for Airflow, install dbt packages
```
`make init` must finish before the first DAG run — the marts' tests use
`dbt_utils`, so `dbt run` fails if the packages are missing.

- Airflow → http://localhost:8080 (admin / admin)
- MinIO console → http://localhost:9001 (minio / minio12345)
- ClickHouse HTTP → http://localhost:8123

### 4. Trigger the pipeline
Enable + run the `hn_elt` DAG in the UI, or:
```bash
make trigger
```
Then inspect ClickHouse:
```bash
docker compose exec clickhouse clickhouse-client -q \
  "SELECT activity_date, story_count, avg_score FROM hackernews_marts.agg_daily_activity ORDER BY activity_date DESC LIMIT 10"
```

### 5. Data quality & lineage
```bash
make dbt-test       # not_null / unique / accepted_values / accepted_range
make dbt-freshness  # warns when raw_stories is older than 26h
make dbt-docs       # lineage graph into dbt/target/
```
`dbt test` does not run source freshness — `make dbt-freshness` is a separate gate.

### 6. Dashboard
Follow [`docs/looker_studio_setup.md`](docs/looker_studio_setup.md) to publish the
marts to a Google Sheet and build the Looker Studio report.

---

## Pipeline (DAG)

```
extract_stories → load_clickhouse_raw → dbt_run → dbt_test → dbt_source_freshness → export_to_sheets
```

| Task | Layer | What it does |
|------|-------|--------------|
| `extract_stories` | E / bronze | Algolia returns one UTC day of stories → NDJSON → MinIO |
| `load_clickhouse_raw` | L | ClickHouse `s3()` reads MinIO → `raw_stories` |
| `dbt_run` | T | builds `stg_hn__stories`, marts |
| `dbt_test` | Governance | not_null / unique / accepted_values / accepted_range |
| `dbt_source_freshness` | Governance | fails when the bronze layer goes stale |
| `export_to_sheets` | Product | marts → Google Sheet → Looker Studio |

## Data models

Every mart exists to answer a question written down before any of them was built —
see [`docs/questions.md`](docs/questions.md) for the question-to-mart-to-chart map
and the known limits of the dataset.

- `stg_hn__stories` — de-duplicated to the latest snapshot per story, HTML decoded.
- `fct_stories` — one row per story (dashboard detail).
- `dim_authors` — per-author aggregates (top contributors).
- `agg_daily_activity` — daily activity time-series (primary chart source).

---

## Project reflection

### 1. What did you learn from this project?

I learned how the pieces of a modern ELT stack actually fit together rather than
in isolation. Concretely:

- **Orchestration as the backbone.** Airflow turned six separate scripts into
  one dependency-aware pipeline with retries and XCom hand-off. I saw why the
  *order* and *idempotency* of tasks matter as much as the code inside them.
- **Lake + warehouse separation.** Landing raw JSON in MinIO first (bronze) means
  I can re-load ClickHouse without re-hitting the API — extraction and loading
  are decoupled and replayable.
- **ClickHouse `s3()`.** Reading files directly from object storage into a
  MergeTree table was a genuinely new pattern for me and avoids shuttling data
  through the worker.
- **Analytics engineering with dbt.** Splitting logic into staging → marts,
  and expressing data quality as `not_null` / `unique` / `accepted_values` /
  `accepted_range` tests, made "data governance" concrete instead of abstract.
- **A source can disappear mid-project.** Reddit closed its API while I was
  building. The valuable part was that only the extract task had to change:
  because the pipeline was already split into layers, swapping the source did
  not touch the loader, the warehouse pattern, or the dashboard design.
- **APIs lie about completeness.** Algolia caps a query at 1000 results but a
  busy HN day has ~1200 stories, so the obvious paging loop drops ~200 rows a
  day and reports success. I only caught it because I compared the row count
  against the `nbHits` the API itself returned. Silent truncation is worse than
  an error.
- **The last-mile problem.** A local warehouse can't be reached by a cloud BI
  tool, so I learned to design a deliberate serving layer (export to Sheets) —
  the dashboard is a product decision, not an afterthought.

### 2. How would you improve it?

- Make the raw load and the marts **incremental** (dbt incremental models keyed
  on `ingest_date`) so daily runs stay cheap as history grows.
- Add **comments** as a second source (`tags=comment`) and model story↔comment
  relationships, which would finally answer "how much discussion per day".
- Replace the Sheets bridge with a proper serving path (ClickHouse behind a
  small API, or ClickHouse Cloud) so Looker reads the warehouse directly.
- Add **alerting** on top of the freshness task (Slack on failure) and capture
  run metadata for observability.
- Add a lightweight **ML** model (predict score from title/post_type/hour) and
  an **RAG** search over story text — both map to later bootcamp modules.
- CI: run `dbt build` against a throwaway ClickHouse in GitHub Actions on each PR.

### 3. If you had to do it all over again, what would you do differently?

- **Validate the source on day one.** I designed the whole extraction around
  PRAW before discovering Reddit no longer issues credentials. A ten-minute
  spike against the real API would have saved rebuilding the extract layer.
- **Model the questions first.** I would write the dashboard's questions and the
  target marts *before* writing extraction, then work backwards. It would have
  kept the raw schema leaner and avoided columns I never used.
- **Design idempotency from day one.** Asking the API for one explicit day is
  what makes re-runs and backfills safe; I'd bake `partition by ingest_date` +
  latest-snapshot logic in from the start instead of bolting it on.
- **Pick the serving layer earlier.** Discovering the local-ClickHouse ↔ Looker
  gap late forced rework; I'd choose the BI connection strategy up front.
- **Smaller, testable commits.** Stand up each layer end-to-end with a tiny
  sample (one day of data) before scaling up — faster feedback loops.

---

## Repo layout

```
hn-dataeng-pipeline/
├── docker-compose.yml          # Airflow + MinIO + ClickHouse + Postgres
├── Makefile                    # make init / trigger / dbt-run / dbt-test
├── .env.example
├── airflow/
│   ├── Dockerfile              # Airflow image with dbt-clickhouse
│   └── dags/
│       ├── hn_elt_dag.py
│       └── scripts/            # extract / load / export
├── dbt/
│   ├── dbt_project.yml · profiles.yml · packages.yml
│   └── models/
│       ├── staging/            # stg_hn__stories + tests
│       └── marts/              # fct_stories · dim_authors · agg_daily_activity
├── clickhouse/init/01_init.sql # raw_stories DDL
└── docs/                       # questions · architecture · looker_studio_setup · roadmap
```

## Data source & credits

Data comes from the public [HN Algolia API](https://hn.algolia.com/api)
(Hacker News, operated by Y Combinator). Project idea adapted from the
"Reddit ETL Pipeline" entry in the Data Engineer Cafe project list; the
implementation here is an independent rebuild on Airflow + dbt + ClickHouse +
Looker Studio, with the source changed after Reddit closed public API access.
