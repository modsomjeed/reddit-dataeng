{{ config(materialized='table') }}

with posts as (
    select * from {{ ref('stg_reddit__posts') }}
),
mentions as (
    select
        post_id,
        count() as tools_mentioned,
        countIf(category = 'ai') > 0 as mentions_ai,
        countIf(category = 'ai' and is_in_title) > 0 as mentions_ai_in_title
    from {{ ref('fct_post_tool_mentions') }}
    group by post_id
)

select
    posts.post_id as post_id,
    posts.posted_at as posted_at,
    posts.flair as flair,
    posts.is_text_post as is_text_post,
    posts.is_removed as is_removed,
    posts.removal_reason as removal_reason,
    posts.score as score,
    posts.num_comments as num_comments,
    posts.upvote_ratio as upvote_ratio,
    coalesce(mentions.tools_mentioned, 0) as tools_mentioned,
    coalesce(mentions.mentions_ai, false) as mentions_ai,
    coalesce(mentions.mentions_ai_in_title, false) as mentions_ai_in_title
from posts
left join mentions on posts.post_id = mentions.post_id
