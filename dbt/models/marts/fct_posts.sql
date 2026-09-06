-- Gold: fact table ― one row per post, current state, ready for the dashboard.

select
    post_id,
    subreddit,
    title,
    author,
    flair,
    score,
    upvote_ratio,
    num_comments,
    engagement_score,
    selftext_length,
    is_self,
    is_nsfw,
    created_utc,
    created_hour,
    created_dow,
    permalink,
    url,
    ingested_at
from {{ ref('stg_reddit__posts') }}
