# Reddit Data Engineering

An end-to-end data project on two years of r/dataengineering posts (Sep 2024 – Sep 2026),
built step by step following the ODT internal bootcamp.

**Question:** Is AI replacing the data engineering stack?
**Answer:** No. Posts with an AI tool in the title went from 4.0% to 11.7% (×2.9) and spread
into Help and Discussion, but no non-AI tool moved more than 0.9 points, so AI is being added on
top of the existing stack, not replacing it.

## Stack

Python · Airflow 3 · RustFS (S3) · ClickHouse · dbt · Streamlit · Docker Compose · PlantUML

```
Arctic Shift API → RustFS (raw JSON) → ClickHouse (raw) → dbt (staging → marts) → Streamlit
                          orchestrated daily by Airflow
```

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

### Step 4 — Load two years of posts

    make backfill      # Arctic Shift → RustFS, one file per day (first run takes a while)
    make load          # RustFS → ClickHouse raw table
    make dbt-build     # staging, facts and marts, plus 27 tests

Every step is safe to rerun: `backfill` skips days already in RustFS, `load` doesn't create
duplicates, and dbt rebuilds the models. Use `make backfill START=2026-09-01 END=2026-09-24`
for a shorter range. `make bootstrap` runs steps 2–4 in one go.

### Step 5 — Look at the results

| What | Where |
|---|---|
| Dashboard | http://localhost:8501 |
| Airflow (airflow / airflow) | http://localhost:8080 — unpause `reddit_daily` to run it daily at 02:00 UTC |
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
| `make backfill [START=… END=…]` | Extract posts to RustFS for a date range (default: the full two years) |
| `make load` | Load every raw file from RustFS into ClickHouse |
| `make dbt-build` | Build and test all dbt models |
| `make dbt-docs` | Generate dbt docs and serve them on port 8081 |
| `make bootstrap` | First run: `setup`, `up`, `backfill`, `load` and `dbt-build` |
| `make airflow-test DAY=…` | Run the whole `reddit_daily` DAG once for one day |
| `make diagrams` | Render the PlantUML architecture diagrams to SVG |

## What's inside

| Path | What |
|---|---|
| `scripts/` | Extract from Arctic Shift to RustFS; load into ClickHouse with `s3()`; ClickHouse init scripts |
| `airflow/` | Custom image (Airflow + dbt) and the `reddit_daily` DAG |
| `dbt/reddit/` | Staging, facts, marts, the `tools` seed and 27 tests |
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
- **Definitions are governance.** "Removed" meant two different things in the data, and two
  moderator rule changes explained most of the rise. Writing that down mattered as much as the code.

### 2. How would you improve it?

- Extract **comments**, to answer questions about response time and what the community
  recommends.
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
