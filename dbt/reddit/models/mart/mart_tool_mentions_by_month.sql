{{ config(materialized='table') }}

with posts as (
    select
        post_id,
        toStartOfMonth(posted_at) as month
    from {{ ref('stg_reddit__posts') }}
),
months as (
    select
        month,
        count() as posts_in_month
    from posts
    group by month
),
tools as (
    select tool, category from {{ ref('tools') }}
),
mentions as (
    select
        toStartOfMonth(posted_at) as month,
        tool,
        count() as posts_mentioning
    from {{ ref('fct_post_tool_mentions') }}
    group by month, tool
)

-- every month × every tool, so a month with no mentions shows up as 0 instead of missing
select
    months.month as month,
    tools.tool as tool,
    tools.category as category,
    coalesce(mentions.posts_mentioning, 0) as posts_mentioning,
    months.posts_in_month as posts_in_month,
    round(posts_mentioning / months.posts_in_month * 100, 2) as share_pct
from months
cross join tools
left join mentions
    on months.month = mentions.month
    and tools.tool = mentions.tool
