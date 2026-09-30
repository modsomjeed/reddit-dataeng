# Reddit Data Engineering

An end-to-end data project on two years of r/dataengineering posts and comments (Sep 2024 – Sep 2026),
built step by step following the ODT internal bootcamp.

**Question:** Is AI replacing the data engineering stack?
**Answer:** No. Posts with an AI tool in the title went from 4.0% to 11.7% (×2.9), and comments
that mention AI went from 4.5% to 13.2% (also ×2.9). AI spread into Help and Discussion, but no
non-AI tool moved more than 0.9 points in titles, so AI is being added on top of the existing
stack, not replacing it.

## Stack

Python · Airflow 3 · RustFS (S3) · ClickHouse · dbt · Streamlit · Docker Compose · PlantUML

## Data engineering lifecycle

The project follows the data engineering lifecycle from *Fundamentals of Data Engineering*
(Reis & Housley): data moves from generation through ingestion, transformation and serving, on
top of storage, and every stage leans on the same undercurrents.

![Data engineering lifecycle](docs/architecture/diagrams/lifecycle.svg)

| Stage | In this project | Where |
|---|---|---|
| Generation | Reddit r/dataengineering posts and comments, read through the Arctic Shift archive | [`scripts/extract_reddit.py`](scripts/extract_reddit.py) |
| Ingestion | Daily batch: extract a day to RustFS, then ClickHouse loads it with `s3()`; idempotent and backfillable | [`scripts/`](scripts/), [`reddit_ingest`](airflow/dags/reddit_ingest.py) |
| Storage | RustFS data lake (raw JSON, one file per day) and ClickHouse warehouse (raw → staging → marts) | [`docker-compose.yml`](docker-compose.yml), [`scripts/create_tables.sql`](scripts/create_tables.sql) |
| Transformation | dbt staging, facts and marts, a `tools` seed and 45 tests; runs when both raw tables have new data | [`dbt/reddit/`](dbt/reddit/), [`reddit_dbt`](airflow/dags/reddit_dbt.py) |
| Serving | Marts granted to a read-only `analyst` role | [`scripts/create_users.sh`](scripts/create_users.sh) |
| Analytics | Streamlit dashboard for a DE lead | [`dashboard/`](dashboard/) |
| Machine learning | Not covered yet | — |
| Reverse ETL | Not covered yet | — |

| Undercurrent | In this project |
|---|---|
| Security | Secrets only in `.env`, services bound to 127.0.0.1, read-only dashboard user |
| Data management | [Governance](docs/governance.md): pseudonymised usernames, PII tags, dbt docs and lineage, known data limits, raw-bucket backup and restore |
| DataOps | dbt tests, source freshness gate, retries with backoff, idempotent reloads |
| Data architecture | [4+1 View Model](docs/architecture/) and key decisions |
| Orchestration | Airflow 3: a daily ingest DAG and an Asset-triggered dbt DAG |
| Software engineering | Conventional Commits, uv projects, Makefile, Docker Compose |

## Getting started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with Compose (give it at least 4 GB of memory)
- [uv](https://docs.astral.sh/uv/) for the Python scripts and dbt
- `make`

### Step 1 — Get the code

    git clone https://github.com/modsomjeed/reddit-dataeng.git
    cd reddit-dataeng

### Step 2 — Create your `.env`

    make setup

This copies `.env.example` to `.env`. Open `.env` and replace every `change-me` value
(ClickHouse, the read-only dashboard user, RustFS, and `PII_HASH_SALT`).

### Step 3 — Start the services

    make up

This builds the Airflow and dashboard images and starts ClickHouse, RustFS, Airflow and the
dashboard. On first start ClickHouse creates the raw table, the `analyst` role and the
`dashboard` user. `make ps` shows status and URLs at any time.

### Step 4 — Load two years of posts and comments

    make backfill                  # posts: Arctic Shift → RustFS, one file per day
    make backfill KIND=comments    # comments: about 250k, the first run takes a few hours
    make load                      # posts: RustFS → ClickHouse raw table
    make load KIND=comments        # comments: RustFS → ClickHouse raw table
    make dbt-build                 # staging, facts and marts, plus 45 tests

Every step is safe to rerun: `backfill` skips days already in RustFS, `load` doesn't create
duplicates, and dbt rebuilds the models. Use `make backfill START=2026-09-01 END=2026-09-24`
for a shorter range. `make bootstrap` runs steps 2–4 in one go.

### Step 5 — Look at the results

| What | Where |
|---|---|
| Dashboard | http://localhost:8501 |
| Airflow (airflow / airflow) | http://localhost:8082 (`AIRFLOW_PORT` in `.env`) — unpause `reddit_ingest` (daily at 02:00 UTC) and `reddit_dbt` (runs after each ingest) |
| RustFS console | http://localhost:9001/rustfs/console/ (RustFS keys from `.env`) |
| dbt docs and lineage | `make dbt-docs`, then http://localhost:8081 |

### All commands

Run `make` (or `make help`) to list them:

| Command | What it does |
|---|---|
| `make setup` | Create `.env` from `.env.example` (never overwrites an existing `.env`) |
| `make up` | Build images and start every service, then show status and URLs |
| `make down` | Stop every service (data volumes are kept) |
| `make ps` | Show service status and URLs |
| `make logs SERVICE=…` | Follow logs, e.g. `SERVICE=airflow-scheduler` |
| `make backfill [KIND=… START=… END=…]` | Extract posts (default) or comments to RustFS for a date range (default: the full two years) |
| `make backup-raw` | Copy the raw bucket to `data/backup/` (new or changed files only) |
| `make restore-raw` | Upload files from `data/backup/` that the raw bucket is missing |
| `make load [KIND=…]` | Load every raw posts (default) or comments file from RustFS into ClickHouse |
| `make dbt-build` | Build and test all dbt models |
| `make dbt-docs` | Generate dbt docs and serve them on port 8081 |
| `make bootstrap` | First run: `setup`, `up`, backfill and load posts and comments, then `dbt-build` |
| `make ingest-test DAY=…` | Run the `reddit_ingest` DAG once for one day (extract and load only) |
| `make dbt-test` | Run the `reddit_dbt` DAG once (source freshness, then dbt build) |
| `make diagrams` | Render the PlantUML architecture diagrams to SVG |

## What's inside

| Path | What |
|---|---|
| `scripts/` | Extract from Arctic Shift to RustFS; load into ClickHouse with `s3()`; ClickHouse init scripts |
| `airflow/` | Custom image (Airflow + dbt), the `reddit_ingest` DAG and the Asset-triggered `reddit_dbt` DAG |
| `dbt/reddit/` | Staging, facts and marts for posts and comments, the `tools` seed, macros and 45 tests |
| `dashboard/` | Streamlit dashboard for a DE lead |
| `docs/architecture/` | 4+1 View Model (PlantUML) |
| `docs/dashboard/story.md` | User, empathy map, GAME and SCQA, designed before the dashboard |
| `docs/governance.md` | PII, access control, freshness and known data limits |

## Bootcamp coverage

| Topic | Status |
|---|---|
| Thinking with Data | ✅ questions at four analytics levels; main theme chosen |
| Data Engineering 101 + Architecture | ✅ source evaluation, data lake + warehouse, ELT, 4+1 views |
| Data Pipelines with Airflow | ✅ daily DAG, idempotent reloads, backfill, retries, freshness check |
| Analytics Engineering with dbt | ✅ staging / mart layers, seed, generic, singular and grain tests, docs |
| Data Governance | ✅ pseudonymised usernames, read-only analyst role, data limits |
| Dashboard Design + Data Product | ✅ story-first Streamlit dashboard |
| Machine Learning · Kafka · Agentic AI + RAG | ⏸ not covered yet |

## Reflection

### 1. What did you learn from this project?

- **Check the source before designing anything.** The Reddit API couldn't give two years of
  history, so the project runs on the Arctic Shift archive, and that archive's own rules later
  shaped the whole analysis.
- **Idempotency is what makes a pipeline safe to rerun.** A `ReplacingMergeTree` raw table,
  `--force` re-extracts and retries with backoff let me backfill and rerun days without
  duplicates, even when the archive returned errors partway through.
- **Framework defaults can be wrong for your data.** In Airflow 3 a plain cron schedule sets
  `ds` to the run date, so the first runs extracted a day that had only just started. Switching
  to `CronDataIntervalTimetable` fixed it.
- **Tests catch bugs you would never see by eye.** dbt-clickhouse loads empty seed cells as `''`
  rather than NULL, which silently broke multi-word tools like "Power BI". A test now guards it.
- **Question the number before telling the story.** Spark looked like it was falling 4 points,
  but removed posts lose their body text; counting titles only, the drop was 0.4 points.
- **An archive's API has its own limits.** Comment searches timed out whenever the time window
  was narrow, and only probing different query shapes showed it; widening the window to a week
  fixed it without losing a single comment.
- **Definitions are governance.** "Removed" meant two different things in the data, and two
  moderator rule changes explained most of the rise. Writing that down mattered as much as the code.

### 2. How would you improve it?

- Use the **comments** for more questions: time to first answer on Help posts, the best time to
  post, and what the community recommends.
- Replace keyword matching with a better classifier, and measure precision on a labelled sample
  instead of spot checks.
- **Re-extract older days** after a few weeks to catch later removals (today they are
  right-censored), and move the facts to **incremental** dbt models.
- Add **CI** that runs `dbt build` on every change, **alerting** on failed DAG runs, and pin the
  `latest` image tags.
- Keep the hashing salt out of the staging view DDL (for example with a materialised table).
- Finish the remaining topics: topic modelling (ML), a streaming path with Kafka, and RAG over the
  posts.

### 3. If you have to do it all over again, what would you do it differently?

- **Read the source's field semantics on day one.** I only found out late that the removal flag
  is captured seconds after posting and that later removals live in `_meta`.
- **Choose the fair metric (titles only) before building marts**, not after spotting a
  misleading trend.
- **Set up tests and CI with the first model**, not after the first bug.
- **Check infrastructure choices early**: MinIO's images had stopped being published, and the
  compose project name clashed with another branch's stack.
- **Draw the 4+1 views early and update them as I go**, instead of catching up after each step.
