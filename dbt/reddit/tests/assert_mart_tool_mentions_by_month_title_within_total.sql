-- a title mention is also a title-or-body mention, so it can never exceed the total
select
    month,
    tool,
    posts_mentioning,
    posts_mentioning_in_title
from {{ ref('mart_tool_mentions_by_month') }}
where posts_mentioning_in_title > posts_mentioning
