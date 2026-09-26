{{ config(materialized='table') }}

with posts as (
    select
        post_id,
        lower(title) as title_text,
        lower(concat(title, ' ', coalesce(body, ''))) as post_text,
        posted_at,
        flair,
        is_removed_at_capture,
        is_removed_later,
        score,
        num_comments
    from {{ ref('stg_reddit__posts') }}
),
tools as (
    select * from {{ ref('tools') }}
),
post_tools as (
    select
        posts.*,
        tools.tool,
        tools.category,
        -- removed posts lose their body, so title-only matches are the fair
        -- basis for comparing periods with different removal rates
        {{ mentions_tool('posts.title_text') }} as is_in_title,
        {{ mentions_tool('posts.post_text') }} as is_in_post
    from posts
    cross join tools
)

select
    post_id,
    tool,
    category,
    is_in_title,
    posted_at,
    flair,
    is_removed_at_capture,
    is_removed_later,
    score,
    num_comments
from post_tools
where is_in_post
