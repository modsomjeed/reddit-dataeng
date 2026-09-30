-- each window holds at most N months, and no month may sit in both
select period, count() as months
from {{ ref('dim_comparison_windows') }}
group by period
having months > {{ var('comparison_window_months') }}
