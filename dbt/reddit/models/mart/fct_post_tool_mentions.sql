{{ config(materialized='table') }}

with posts as (
    select
        post_id,
        lower(title) as title_text,
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
        concat('\\b(', tools.pattern, ')\\b') as tool_regex,
        -- blank out phrases that reuse the tool's word for something else,
        -- e.g. "sql server agent" for AI Agent
        coalesce(tools.exclude_pattern, '') = '' as has_no_exclusions,
        concat('\\b(', tools.exclude_pattern, ')\\b') as exclude_regex,
        if(has_no_exclusions, posts.post_text, replaceRegexpAll(posts.post_text, exclude_regex, ' ')) as match_text,
        if(has_no_exclusions, posts.title_text, replaceRegexpAll(posts.title_text, exclude_regex, ' ')) as match_title
    from posts
    cross join tools
)

select
    post_id,
    tool,
    category,
    -- removed posts lose their body, so title-only matches are the fair
    -- basis for comparing periods with different removal rates
    match(match_title, tool_regex) as is_in_title,
    posted_at,
    flair,
    is_removed,
    score,
    num_comments
from post_tools
where match(match_text, tool_regex)
