-- The two periods the dashboard compares: the first and the last N complete months.
-- The first and last months of the data are partial (the extraction window starts and
-- ends mid-month), so they are left out. The windows move by themselves as data arrives.
with months as (
    select distinct toStartOfMonth(posted_at) as month
    from {{ ref('stg_reddit__posts') }}
),
ranked as (
    select
        month,
        row_number() over (order by month) as month_number,
        count() over () as month_count
    from months
),
complete_months as (
    -- position among complete months, 1-based
    select
        month,
        month_number - 1 as position,
        month_count - 2 as complete_month_count
    from ranked
    where month_number > 1 and month_number < month_count
)

select
    month,
    if(position <= {{ var('comparison_window_months') }}, 'first', 'last') as period
from complete_months
where position <= {{ var('comparison_window_months') }}
   or position > complete_month_count - {{ var('comparison_window_months') }}
