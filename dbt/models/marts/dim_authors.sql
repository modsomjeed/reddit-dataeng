-- Gold: author-level aggregates. "Who are the most active / most upvoted
-- contributors in r/dataengineering?"

select
    author,
    count(*)                          as total_posts,
    sum(score)                        as total_score,
    round(avg(score), 1)              as avg_score,
    sum(num_comments)                 as total_comments,
    max(score)                        as best_post_score,
    min(created_utc)                  as first_seen,
    max(created_utc)                  as last_seen
from {{ ref('stg_reddit__posts') }}
where author != '[deleted]'
group by author
