select
    comment_id,
    tool,
    count() as rows
from {{ ref('fct_comment_tool_mentions') }}
group by comment_id, tool
having rows > 1
