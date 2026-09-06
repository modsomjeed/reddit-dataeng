-- Silver layer: clean + de-duplicate raw_posts to the LATEST snapshot per post.
-- raw_posts keeps every snapshot; here we keep only the most recent ingest
-- so downstream marts see one current row per post.

with source as (

    select * from {{ source('raw', 'raw_posts') }}

),

deduped as (

    select
        *,
        row_number() over (
            partition by post_id
            order by ingested_at desc
        ) as _rn
    from source

)

select
    post_id,
    subreddit,
    trim(title)                                as title,
    selftext,
    author,
    score,
    upvote_ratio,
    num_comments,
    permalink,
    url,
    nullif(flair, '')                          as flair,
    over_18                                     as is_nsfw,
    is_self,
    created_utc,
    ingested_at,
    ingest_date,
    -- helpful derived fields for analysis
    toHour(created_utc)                        as created_hour,
    toDayOfWeek(created_utc)                   as created_dow,
    length(selftext)                           as selftext_length,
    (score + num_comments)                     as engagement_score
from deduped
where _rn = 1
