-- One row per measure: AI share in the first vs the last comparison window.
with monthly as (
    select
        a.measure as measure,
        w.period as period,
        a.mentions_ai as mentions_ai,
        a.total as total
    from {{ ref('mart_ai_share_by_month') }} as a
    inner join {{ ref('dim_comparison_windows') }} as w on a.month = w.month
),
by_period as (
    select
        measure,
        sumIf(mentions_ai, period = 'first') / nullIf(sumIf(total, period = 'first'), 0) * 100 as first_share,
        sumIf(mentions_ai, period = 'last') / nullIf(sumIf(total, period = 'last'), 0) * 100 as last_share
    from monthly
    group by measure
)

select
    measure,
    round(first_share, 2) as first_share_pct,
    round(last_share, 2) as last_share_pct,
    round(last_share - first_share, 2) as change_pts,
    round(last_share / nullIf(first_share, 0), 2) as growth_ratio
from by_period
