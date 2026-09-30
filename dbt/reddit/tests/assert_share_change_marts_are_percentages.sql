-- every share is a percentage; NULL means a window had no data (only in tiny test datasets)
select 'mart_ai_share_change' as model, measure as key, first_share_pct, last_share_pct
from {{ ref('mart_ai_share_change') }}
where not (coalesce(first_share_pct, 0) between 0 and 100 and coalesce(last_share_pct, 0) between 0 and 100)
union all
select 'mart_tool_share_change', concat(tool, ' / ', measure), first_share_pct, last_share_pct
from {{ ref('mart_tool_share_change') }}
where not (coalesce(first_share_pct, 0) between 0 and 100 and coalesce(last_share_pct, 0) between 0 and 100)
