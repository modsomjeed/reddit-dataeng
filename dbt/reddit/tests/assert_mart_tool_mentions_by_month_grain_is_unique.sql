select
    month,
    tool,
    count() as rows
from {{ ref('mart_tool_mentions_by_month') }}
group by month, tool
having rows > 1
