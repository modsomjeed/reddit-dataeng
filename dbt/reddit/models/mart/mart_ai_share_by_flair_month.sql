{{ config(materialized='table') }}

with posts as (
    select * from {{ ref('fct_posts') }}
)

-- AI share uses title mentions only: removed posts have no body, and the
-- removal rate changes a lot over time
select
    toStartOfMonth(posted_at) as month,
    coalesce(flair, 'No flair') as flair,
    count() as posts,
    countIf(mentions_ai_in_title) as ai_posts_in_title,
    round(ai_posts_in_title / posts * 100, 2) as ai_title_share_pct
from posts
group by month, flair
