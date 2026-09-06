-- ============================================================
--  ClickHouse bootstrap ― runs once on first container start
--  Creates the database + the RAW (bronze) landing table that
--  Airflow loads Reddit posts into. dbt builds staging/marts on top.
-- ============================================================

CREATE DATABASE IF NOT EXISTS reddit;

-- Raw landing table. One row per (post_id, ingested_at) snapshot.
-- We keep every snapshot so dbt can de-duplicate to the latest state
-- and we can observe how score / comments change over time.
CREATE TABLE IF NOT EXISTS reddit.raw_posts
(
    post_id        String,
    subreddit      String,
    title          String,
    selftext       String,
    author         String,
    score          Int32,
    upvote_ratio   Float32,
    num_comments   Int32,
    permalink      String,
    url            String,
    flair          String,
    over_18        UInt8,
    is_self        UInt8,
    created_utc    DateTime,
    ingested_at    DateTime,
    ingest_date    Date
)
ENGINE = MergeTree
PARTITION BY ingest_date
ORDER BY (subreddit, post_id, ingested_at)
SETTINGS index_granularity = 8192;
