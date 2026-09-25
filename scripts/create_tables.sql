-- ============================================================
-- Reddit raw tables — ClickHouse DDL
-- Runs on first startup via /docker-entrypoint-initdb.d/
-- ============================================================

CREATE DATABASE IF NOT EXISTS reddit;

-- ------------------------------------------------------------
-- posts
-- One row per post as returned by Arctic Shift. `raw` keeps the
-- full JSON so fields can be added later without re-extracting.
-- ReplacingMergeTree keeps the newest load of each id, so
-- reloading a day never duplicates posts.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reddit.posts (
    id                   String,
    subreddit            String,
    author               String,
    title                String,
    selftext             String,
    url                  String,
    permalink            String,
    link_flair_text      Nullable(String),
    is_self              Bool,
    over_18              Bool,
    score                Int32,
    num_comments         Int32,
    upvote_ratio         Float32,
    removed_by_category  Nullable(String),
    created_utc          DateTime('UTC'),
    retrieved_on         DateTime('UTC'),
    raw                  String,
    _loaded_at           DateTime('UTC') DEFAULT now()
)
ENGINE = ReplacingMergeTree(_loaded_at)
PARTITION BY toYYYYMM(created_utc)
ORDER BY id;
