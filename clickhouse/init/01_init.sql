-- ============================================================
--  ClickHouse bootstrap ― runs once on first container start
--  Creates the database + the RAW (bronze) landing table that
--  Airflow loads Hacker News stories into. dbt builds staging/marts on top.
-- ============================================================

CREATE DATABASE IF NOT EXISTS hackernews;

-- Raw landing table. One row per (story_id, ingested_at) snapshot.
-- We keep every snapshot so dbt can de-duplicate to the latest state
-- and we can observe how score / comments change over time.
CREATE TABLE IF NOT EXISTS hackernews.raw_stories
(
    story_id       String,
    title          String,
    story_text     String,
    author         String,
    score          Int32,
    num_comments   Int32,
    permalink      String,
    url            String,
    -- HN has no flair; this is the community's own category, taken from the
    -- title prefix: 'ask_hn' | 'show_hn' | 'story'
    post_type      String,
    is_self        UInt8,
    created_utc    DateTime,
    ingested_at    DateTime,
    ingest_date    Date
)
ENGINE = MergeTree
PARTITION BY ingest_date
ORDER BY (story_id, ingested_at)
SETTINGS index_granularity = 8192;
