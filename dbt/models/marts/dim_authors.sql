-- Gold: author-level aggregates. "Who are the most active / most upvoted
-- contributors on Hacker News?"

select
    author,
    count(*)                          as total_stories,
    sum(score)                        as total_score,
    round(avg(score), 1)              as avg_score,
    sum(num_comments)                 as total_comments,
    max(score)                        as best_story_score,
    min(created_utc)                  as first_seen,
    max(created_utc)                  as last_seen
from {{ ref('stg_hn__stories') }}
where author != '[deleted]'
group by author
