# Reddit Data Engineering Pipeline — r/dataengineering

End-to-end **ELT** on posts from [r/dataengineering](https://reddit.com/r/dataengineering),
built with the stack from the bootcamp:

**Reddit API (PRAW) → MinIO → ClickHouse → dbt → Looker Studio**, orchestrated by **Airflow**.

> Project brief: pick one project from the Data Engineer Cafe list (Reddit ETL),
> use only that project's data, and rebuild it on your own stack
> (Airflow + dbt + ClickHouse + Google Data Studio) in your own repo.

---

## Stack

| Concern              | Tool                          |
|----------------------|-------------------------------|
| Orchestration        | Apache Airflow (LocalExecutor)|
| Ingestion            | Python + PRAW                 |
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
- A Reddit "script" app → <https://www.reddit.com/prefs/apps>

### 2. Configure
```bash
cp .env.example .env
# generate a Fernet key and paste into AIRFLOW_FERNET_KEY:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# fill in REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT
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
Enable + run the `reddit_elt` DAG in the UI, or:
```bash
make trigger
```
Then inspect ClickHouse:
```bash
docker compose exec clickhouse clickhouse-client -q \
  "SELECT post_date, post_count, avg_score FROM reddit.agg_daily_subreddit ORDER BY post_date DESC LIMIT 10"
```

### 5. Data quality & lineage
```bash
make dbt-test       # not_null / unique / accepted_range
make dbt-freshness  # warns when raw_posts is older than 26h
make dbt-docs       # lineage graph into dbt/target/
```
`dbt test` does not run source freshness — `make dbt-freshness` is a separate gate.

### 6. Dashboard
Follow [`docs/looker_studio_setup.md`](docs/looker_studio_setup.md) to publish the
marts to a Google Sheet and build the Looker Studio report.

---

## Pipeline (DAG)

```
extract_reddit → load_clickhouse_raw → dbt_run → dbt_test → export_to_sheets
```

| Task                 | Layer      | What it does                                         |
|----------------------|------------|------------------------------------------------------|
| `extract_reddit`     | E / bronze | PRAW pulls posts → NDJSON → MinIO                     |
| `load_clickhouse_raw`| L          | ClickHouse `s3()` reads MinIO → `raw_posts`          |
| `dbt_run`            | T          | builds `stg_reddit__posts`, marts                    |
| `dbt_test`           | Governance | not_null / unique / accepted_range + freshness       |
| `export_to_sheets`   | Product    | marts → Google Sheet → Looker Studio                 |

## Data models

Every mart exists to answer a question written down before any of them was built —
see [`docs/questions.md`](docs/questions.md) for the question-to-mart-to-chart map
and the known limits of the dataset.

- `stg_reddit__posts` — cleaned, de-duplicated to latest snapshot per post.
- `fct_posts` — one row per post (dashboard detail).
- `dim_authors` — per-author aggregates (top contributors).
- `agg_daily_subreddit` — daily activity time-series (primary chart source).

---

## Project reflection

### 1. What did you learn from this project?

I learned how the pieces of a modern ELT stack actually fit together rather than
in isolation. Concretely:

- **Orchestration as the backbone.** Airflow turned five separate scripts into
  one dependency-aware pipeline with retries and XCom hand-off. I saw why the
  *order* and *idempotency* of tasks matter as much as the code inside them.
- **Lake + warehouse separation.** Landing raw JSON in MinIO first (bronze) means
  I can re-load ClickHouse without re-hitting the Reddit API — extraction and
  loading are decoupled and replayable.
- **ClickHouse `s3()`.** Reading files directly from object storage into a
  MergeTree table was a genuinely new pattern for me and avoids shuttling data
  through the worker.
- **Analytics engineering with dbt.** Splitting logic into staging → marts,
  and expressing data quality as `not_null` / `unique` / `accepted_range` tests,
  made "data governance" concrete instead of abstract.
- **The last-mile problem.** A local warehouse can't be reached by a cloud BI
  tool, so I learned to design a deliberate serving layer (export to Sheets) —
  the dashboard is a product decision, not an afterthought.

### 2. How would you improve it?

- Make the raw load and the marts **incremental** (dbt incremental models keyed
  on `ingest_date`) so daily runs stay cheap as history grows.
- Add **comments** as a second source and model post↔comment relationships.
- Replace the Sheets bridge with a proper serving path (ClickHouse behind a
  small API, or ClickHouse Cloud) so Looker reads the warehouse directly.
- Add **data-contract / freshness alerting** (dbt `source freshness` in CI +
  Slack notification on test failure) and capture run metadata for observability.
- Add a lightweight **ML** model (predict post score from title/flair/hour) and
  an **RAG** search over post text — both map to later bootcamp modules.
- CI: run `dbt build` against a throwaway ClickHouse in GitHub Actions on each PR.

### 3. If you had to do it all over again, what would you do differently?

- **Model the questions first.** I would write the dashboard's questions and the
  target marts *before* writing extraction, then work backwards. It would have
  kept the raw schema leaner and avoided columns I never used.
- **Design idempotency from day one.** I bolted on the snapshot/de-dup pattern
  after seeing duplicates; I'd bake `partition by ingest_date` + latest-snapshot
  logic in from the start.
- **Pick the serving layer earlier.** Discovering the local-ClickHouse ↔ Looker
  gap late forced rework; I'd choose the BI connection strategy up front.
- **Smaller, testable commits.** Stand up each layer end-to-end with a tiny
  sample (one day of data) before scaling the pull limit — faster feedback loops.

---

## Repo layout

```
reddit-dataeng-pipeline/
├── docker-compose.yml          # Airflow + MinIO + ClickHouse + Postgres
├── Makefile                    # make up / trigger / dbt-run / dbt-test
├── .env.example
├── airflow/
│   ├── Dockerfile              # Airflow image with dbt-clickhouse
│   └── dags/
│       ├── reddit_elt_dag.py
│       └── scripts/            # extract / load / export
├── dbt/
│   ├── dbt_project.yml · profiles.yml · packages.yml
│   └── models/
│       ├── staging/            # stg_reddit__posts + tests
│       └── marts/              # fct_posts · dim_authors · agg_daily_subreddit
├── clickhouse/init/01_init.sql # raw_posts DDL
└── docs/                       # questions · architecture · looker_studio_setup · roadmap
```

## Data source & credits

Data comes from the public Reddit API (r/dataengineering) via PRAW. Project idea
adapted from the "Reddit ETL Pipeline" entry in the Data Engineer Cafe project
list; the implementation here is an independent rebuild on Airflow + dbt +
ClickHouse + Looker Studio.
