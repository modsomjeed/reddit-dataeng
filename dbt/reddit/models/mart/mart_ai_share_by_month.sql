-- One row per (month, measure): how much of the conversation mentions any AI tool,
-- measured two independent ways: post titles, and the text of human comments.
with titles as (
    select
        toStartOfMonth(posted_at) as month,
        'Post titles' as measure,
        countIf(mentions_ai_in_title) as mentions_ai,
        count() as total
    from {{ ref('fct_posts') }}
    group by month
),
ai_comments as (
    -- a comment can mention several AI tools; count it once
    select distinct comment_id
    from {{ ref('fct_comment_tool_mentions') }}
    where category = 'ai'
),
comments as (
    -- the same population fct_comment_tool_mentions matches against
    select
        toStartOfMonth(c.commented_at) as month,
        'Comments' as measure,
        countIf(c.comment_id in (select comment_id from ai_comments)) as mentions_ai,
        count() as total
    from {{ ref('stg_reddit__comments') }} as c
    where not c.is_automoderator
      and c.body is not null
    group by month
),
both_measures as (
    select * from titles
    union all
    select * from comments
)

select
    month,
    measure,
    mentions_ai,
    total,
    round(mentions_ai / total * 100, 2) as share_pct
from both_measures
