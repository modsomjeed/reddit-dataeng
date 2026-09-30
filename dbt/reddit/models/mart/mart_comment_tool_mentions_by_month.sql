with comments as (
    -- the same population the fact matches against: human comments with text
    select
        comment_id,
        toStartOfMonth(commented_at) as month
    from {{ ref('stg_reddit__comments') }}
    where not is_automoderator
      and body is not null
),
months as (
    select
        month,
        count() as comments_in_month
    from comments
    group by month
),
tools as (
    select tool, category from {{ ref('tools') }}
),
mentions as (
    select
        toStartOfMonth(commented_at) as month,
        tool,
        count() as comments_mentioning
    from {{ ref('fct_comment_tool_mentions') }}
    group by month, tool
)

-- every month × every tool, so a month with no mentions shows up as 0 instead of missing
select
    months.month as month,
    tools.tool as tool,
    tools.category as category,
    coalesce(mentions.comments_mentioning, 0) as comments_mentioning,
    months.comments_in_month as comments_in_month,
    round(comments_mentioning / months.comments_in_month * 100, 2) as share_pct
from months
cross join tools
left join mentions
    on months.month = mentions.month
    and tools.tool = mentions.tool
