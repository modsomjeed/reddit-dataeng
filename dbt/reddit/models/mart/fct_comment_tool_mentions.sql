{{ config(materialized='table') }}

-- Comments keep their text far more often than posts (about 3% removed vs up to 95%),
-- so they are the steadier signal of what people actually discuss.
with comments as (
    select
        comment_id,
        post_id,
        lower(body) as comment_text,
        commented_at,
        is_top_level,
        score
    from {{ ref('stg_reddit__comments') }}
    where not is_automoderator
      and body is not null
),
tools as (
    select * from {{ ref('tools') }}
)

select
    comments.comment_id as comment_id,
    comments.post_id as post_id,
    tools.tool as tool,
    tools.category as category,
    comments.commented_at as commented_at,
    comments.is_top_level as is_top_level,
    comments.score as score
from comments
cross join tools
where {{ mentions_tool('comments.comment_text') }}
