-- One row per (flair, period): share of post titles mentioning AI in each comparison window.
select
    f.flair as flair,
    w.period as period,
    sum(f.posts) as posts,
    sum(f.ai_posts_in_title) as ai_posts_in_title,
    round(ai_posts_in_title / posts * 100, 2) as ai_title_share_pct
from {{ ref('mart_ai_share_by_flair_month') }} as f
inner join {{ ref('dim_comparison_windows') }} as w on f.month = w.month
group by f.flair, w.period
