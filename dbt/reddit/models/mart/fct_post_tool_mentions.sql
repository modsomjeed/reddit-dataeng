{{ config(materialized='table') }}

with posts as (
    select
        post_id,
        lower(concat(title, ' ', coalesce(body, ''))) as post_text,
        posted_at,
        flair,
        is_removed,
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
        tools.pattern,
        -- blank out phrases that reuse the tool's word for something else,
        -- e.g. "sql server agent" for AI Agent
        if(
            coalesce(tools.exclude_pattern, '') = '',
            posts.post_text,
            replaceRegexpAll(posts.post_text, concat('\\b(', tools.exclude_pattern, ')\\b'), ' ')
        ) as match_text
    from posts
    cross join tools
)

select
    post_id,
    tool,
    category,
    posted_at,
    flair,
    is_removed,
    score,
    num_comments
from post_tools
where match(match_text, concat('\\b(', pattern, ')\\b'))
