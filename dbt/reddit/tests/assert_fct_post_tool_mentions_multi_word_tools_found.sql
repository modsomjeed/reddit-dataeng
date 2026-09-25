-- Multi-word patterns ("power bi", "sql server", "delta lake") break if the text
-- gets extra spaces between words, so each of these tools must be found at least once.
with expected as (
    select arrayJoin(['Power BI', 'SQL Server', 'Delta Lake']) as tool
),
found as (
    select tool, count() as mentions
    from {{ ref('fct_post_tool_mentions') }}
    group by tool
)

select expected.tool
from expected
left join found on expected.tool = found.tool
where coalesce(found.mentions, 0) = 0
