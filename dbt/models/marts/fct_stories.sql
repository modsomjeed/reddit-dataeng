-- Gold: fact table ― one row per story, current state, ready for the dashboard.

select
    story_id,
    title,
    author,
    post_type,
    score,
    num_comments,
    engagement_score,
    story_text_length,
    is_self,
    created_utc,
    created_hour,
    created_dow,
    permalink,
    url,
    ingested_at
from {{ ref('stg_hn__stories') }}
