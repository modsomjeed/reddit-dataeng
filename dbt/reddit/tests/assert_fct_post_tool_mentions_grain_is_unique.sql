select
    post_id,
    tool,
    count() as rows
from {{ ref('fct_post_tool_mentions') }}
group by post_id, tool
having rows > 1
