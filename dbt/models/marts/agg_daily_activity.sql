-- Gold: daily activity on Hacker News ― the primary time-series that drives
-- the Looker Studio dashboard (stories, engagement, avg score over time).

select
    toDate(created_utc)                   as activity_date,
    count(*)                              as story_count,
    sum(score)                            as total_score,
    round(avg(score), 1)                  as avg_score,
    sum(num_comments)                     as total_comments,
    round(avg(num_comments), 1)           as avg_comments,
    countIf(post_type = 'ask_hn')         as ask_hn_count,
    countIf(post_type = 'show_hn')        as show_hn_count,
    countIf(post_type = 'story')          as link_story_count,
    countIf(is_self = 1)                  as self_posts,
    countIf(is_self = 0)                  as link_posts
from {{ ref('stg_hn__stories') }}
group by activity_date
order by activity_date desc
