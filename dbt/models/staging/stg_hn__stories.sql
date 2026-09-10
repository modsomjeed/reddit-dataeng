-- Silver layer: clean + de-duplicate raw_stories to the LATEST snapshot per story.
-- raw_stories keeps every snapshot; here we keep only the most recent ingest
-- so downstream marts see one current row per story.

with source as (

    select * from {{ source('raw', 'raw_stories') }}

),

deduped as (

    select
        *,
        row_number() over (
            partition by story_id
            order by ingested_at desc
        ) as _rn
    from source

),

cleaned as (

    -- Algolia returns story_text as escaped HTML: real tags ("<p>", "<a>") plus
    -- entity-encoded characters ("&#x2F;"). extractTextFromHTML drops the tags
    -- but leaves entities untouched, so decodeHTMLComponent has to run after it
    -- -- on the visible text only. Done once here rather than in every mart.
    select
        *,
        decodeHTMLComponent(extractTextFromHTML(story_text)) as body_text
    from deduped
    where _rn = 1

)

select
    story_id,
    trim(title)                                as title,
    body_text                                  as story_text,
    author,
    score,
    num_comments,
    permalink,
    url,
    post_type,
    is_self,
    created_utc,
    ingested_at,
    ingest_date,
    -- helpful derived fields for analysis
    toHour(created_utc)                        as created_hour,
    toDayOfWeek(created_utc)                   as created_dow,
    length(body_text)                          as story_text_length,
    (score + num_comments)                     as engagement_score
from cleaned
