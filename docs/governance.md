# Data governance

How this project handles personal data, access, freshness and known data-quality limits.

## Data classification

| Layer | Where | Contains | Who can read |
|---|---|---|---|
| Raw files | RustFS `reddit-raw/posts/*.json` | Full post JSON, **usernames** | Pipeline only |
| Raw table | ClickHouse `reddit.posts` | Usernames (`author`, tagged `pii: direct`), full JSON | Pipeline only |
| Staging | `reddit_analytics.stg_reddit__posts` | `author_id` (salted hash, tagged `pii: pseudonymised`) | Pipeline only |
| Marts | `reddit_analytics.fct_*`, `mart_*` | No usernames or author ids | `analyst` role |

## Personal data

- Reddit usernames are public but still identify people, so they stay in the raw layer.
- Staging replaces them with `author_id` = SHA-256 of `PII_HASH_SALT` + username. Authors can still
  be counted and grouped (18,204 distinct before and after hashing) but not looked up.
- `[deleted]` accounts get a null `author_id`.
- Limitation: the salt is visible in the staging view's DDL to anyone who can read staging. The
  `analyst` role can't.

## Access control

- `scripts/create_users.sh` (ClickHouse init script) creates the `analyst` role and the `dashboard`
  user, which gets that role.
- dbt grants `SELECT` on every model in `models/mart/` to `analyst` on each build
  (`+grants` in `dbt_project.yml`).
- Checked as `dashboard`: reading marts works; reading staging or raw, and any `INSERT`, fail with
  `ACCESS_DENIED`.
- The pipeline (Airflow, dbt, loader) uses the admin user from `.env`; credentials never live in the repo.

## Freshness and quality checks

- Source freshness on `reddit.posts.created_utc`: warn after 36 h, error after 72 h. It runs in the
  DAG before `dbt_build`, so a stalled archive stops the pipeline instead of rebuilding on stale data.
- 27 dbt tests: keys unique and not null, relationships between facts and staging/seed, accepted
  values, grain uniqueness, a guard against the multi-word matching bug, and title ≤ total mentions.

## Known data limitations

### What "removed" means (Q6)

The removed share appears to rise from 11% to 95% over two years. Two things drive it:

1. **Real rule changes.** Moderators announced Rule 9 (no low-effort/AI posts) on 2025-09-29 and a
   promotion/AI-text clarification on 2026-05-20. The removal rate jumps after each (Oct→Nov 2025:
   27%→43%; Apr→Jun 2026: 46%→92%). After Rule 9, promotional flairs (28%→82%) and AI-titled posts
   (24%→53%) were hit hardest, as the rule intends.
2. **What the archive records.** `removed_by_category` is the state seconds after posting. Removals
   after that only appear in `_meta.removal_type`. So the model keeps two flags:

| Flag | Meaning | Caveat |
|---|---|---|
| `is_removed_at_capture` | Removed or held when first captured | From late May 2026 nearly every post is flagged, even in Help (92%), and 14% of flagged posts still got 3+ comments: it most likely means *held for review*, not *never shown*. |
| `is_removed_later` | Up at capture, removed later | Right-censored: recent posts have had less time to be re-checked. |

Counting either flag, about 41% of posts before Rule 9 were removed in the end, not 19%.

### Other limits

- Source is the Arctic Shift archive, not the Reddit API. `score` and `num_comments` are as of the
  archive's re-check about 36 hours after posting, not live.
- Tool mentions are keyword matches (`seeds/tools.csv`); spot checks found about 90% precision for
  ambiguous words such as *agent*. A mention is not an endorsement.
- Trends use title-only mentions: removed posts lose their body, and the removal rate changes a lot
  over time.
