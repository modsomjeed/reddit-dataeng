-- Gold: daily activity of the subreddit ― the primary time-series that
-- drives the Looker Studio dashboard (posts, engagement, avg score over time).

select
    toDate(created_utc)               as post_date,
    subreddit,
    count(*)                          as post_count,
    sum(score)                        as total_score,
    round(avg(score), 1)              as avg_score,
    sum(num_comments)                 as total_comments,
    round(avg(upvote_ratio), 3)       as avg_upvote_ratio,
    countIf(is_self = 1)              as text_posts,
    countIf(is_self = 0)              as link_posts
from {{ ref('stg_reddit__posts') }}
group by post_date, subreddit
order by post_date desc
