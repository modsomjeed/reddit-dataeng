-- dbt/reddit/models/staging/reddit/stg_reddit__posts.sql
with 

source as (

    -- FINAL collapses reloads of the same post that ClickHouse hasn't merged yet
    select * from {{ source('reddit', 'posts') }} final

)

select
    id as post_id,
    -- usernames are personal data: keep a salted hash so authors can still be
    -- counted and grouped, but not looked up; '[deleted]' accounts have no id
    if(
        author = '[deleted]',
        null,
        lower(hex(SHA256(concat('{{ env_var("PII_HASH_SALT") }}', author))))
    ) as author_id,
    title,
    if(selftext in ('', '[removed]', '[deleted]'), null, selftext) as body,
    link_flair_text as flair,
    is_self as is_text_post,
    over_18 as is_nsfw,
    score,
    num_comments,
    upvote_ratio,
    removed_by_category as removal_reason,
    removed_by_category is not null as is_removed,
    created_utc as posted_at,
    retrieved_on as retrieved_at,
    url,
    permalink
from source
