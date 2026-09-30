# Data governance

How this project handles personal data, access, freshness and known data-quality limits.

## Data classification

| Layer | Where | Contains | Who can read |
|---|---|---|---|
| Raw files | RustFS `reddit-raw/posts/*.json`, `reddit-raw/comments/*.json` | Full post and comment JSON, **usernames** | Pipeline only |
| Raw tables | ClickHouse `reddit.posts`, `reddit.comments` | Usernames (`author`, tagged `pii: direct`), full JSON | Pipeline only |
| Staging | `reddit_analytics.stg_reddit__posts`, `stg_reddit__comments` | `author_id` (salted hash, tagged `pii: pseudonymised`) | Pipeline only |
| Marts | `reddit_analytics.fct_*`, `mart_*` | No usernames or author ids | `analyst` role |

## Personal data

- Reddit usernames are public but still identify people, so they stay in the raw layer.
- Staging replaces them with `author_id` = SHA-256 of `PII_HASH_SALT` + username (the
  `pseudonymise_author` macro, shared by posts and comments). Authors can still be counted, grouped
  and matched across posts and comments, but not looked up.
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

## Backup and restore

- The raw bucket is the only copy of what was extracted; ClickHouse and every dbt model can be
  rebuilt from it with `make load` and `make dbt-build`.
- `make backup-raw` copies the bucket to `data/backup/reddit-raw/` (git-ignored), downloading only
  new or changed files. `make restore-raw` uploads whatever the bucket is missing.
- Why: deleting the Docker volumes once wiped both RustFS and ClickHouse. Posts came back from a
  local copy in minutes; comments had no copy and took hours to re-extract from the archive.
  A restore test into a scratch bucket reproduced all 1,468 files exactly.

## Freshness and quality checks

- Source freshness on `created_utc` of both `reddit.posts` and `reddit.comments`: warn after 36 h,
  error after 72 h. It is the first task of the `reddit_dbt` DAG, so a stalled archive stops the
  rebuild instead of refreshing the marts on stale data.
- 45 dbt tests: keys unique and not null, relationships between facts and staging/seed, accepted
  values, grain uniqueness, a guard against the multi-word matching bug, title ≤ total mentions,
  and a guard that a null comment body always means a removed one. The comment → post relationship
  is a warning: about 900 comments (0.4%) belong to posts made before the extraction window.

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

### Comments

- Comments keep their text far more often than posts: only 3.4% are removed or deleted.
  AutoModerator comments (about 6,000) are excluded from the tool analysis.
- Comment volume holds at 10–14k a month, then falls after the May 2026 clarification (to 4k in
  August 2026), consistent with posts being held for review. The AI share of comments in those
  last months rises to 16–20% on much smaller volumes, so treat it with care.

### Other limits

- Source is the Arctic Shift archive, not the Reddit API. `score` and `num_comments` are as of the
  archive's re-check about 36 hours after posting, not live.
- Tool mentions are keyword matches (`seeds/tools.csv`); spot checks found about 90% precision for
  ambiguous words such as *agent*. A mention is not an endorsement.
- Post trends use title-only mentions: removed posts lose their body, and the removal rate changes
  a lot over time. Comment text is the second, independent measure.
