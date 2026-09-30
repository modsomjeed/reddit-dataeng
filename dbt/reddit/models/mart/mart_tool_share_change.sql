-- One row per (tool, measure): the tool's share of post titles or of comments in the
-- first vs the last comparison window, and the change in percentage points.
with monthly as (
    select
        month,
        tool,
        category,
        'Post titles' as measure,
        posts_mentioning_in_title as mentions,
        posts_in_month as total
    from {{ ref('mart_tool_mentions_by_month') }}
    union all
    select
        month,
        tool,
        category,
        'Comments' as measure,
        comments_mentioning as mentions,
        comments_in_month as total
    from {{ ref('mart_comment_tool_mentions_by_month') }}
),
by_period as (
    select
        m.tool as tool,
        m.category as category,
        m.measure as measure,
        sumIf(m.mentions, w.period = 'first') / nullIf(sumIf(m.total, w.period = 'first'), 0) * 100 as first_share,
        sumIf(m.mentions, w.period = 'last') / nullIf(sumIf(m.total, w.period = 'last'), 0) * 100 as last_share
    from monthly as m
    inner join {{ ref('dim_comparison_windows') }} as w on m.month = w.month
    group by m.tool, m.category, m.measure
)

select
    tool,
    category,
    toBool(category = 'ai') as is_ai,
    measure,
    round(first_share, 2) as first_share_pct,
    round(last_share, 2) as last_share_pct,
    round(last_share - first_share, 2) as change_pts
from by_period
