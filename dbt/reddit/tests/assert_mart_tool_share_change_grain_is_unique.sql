select
    tool,
    measure,
    count() as rows
from {{ ref('mart_tool_share_change') }}
group by tool, measure
having rows > 1
