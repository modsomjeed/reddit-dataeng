-- dbt/reddit/models/staging/reddit/stg_reddit__comments.sql
with 

source as (

    -- FINAL collapses reloads of the same comment that ClickHouse hasn't merged yet
    select * from {{ source('reddit', 'comments') }} final

)

select
    id as comment_id,
    -- link_id is 't3_<post id>'; parent_id is 't3_<post id>' for a top-level
    -- comment or 't1_<comment id>' for a reply
    substring(link_id, 4) as post_id,
    if(startsWith(parent_id, 't1_'), substring(parent_id, 4), null) as parent_comment_id,
    startsWith(parent_id, 't3_') as is_top_level,
    {{ pseudonymise_author('author') }} as author_id,
    author = 'AutoModerator' as is_automoderator,
    is_submitter as is_by_post_author,
    distinguished,
    -- qualify the raw column: ClickHouse would otherwise resolve `body` in the next
    -- line to the cleaned alias defined here
    source.body in ('[removed]', '[deleted]') as is_body_removed,
    if(is_body_removed, null, source.body) as body,
    nullIf(JSONExtractString(raw, '_meta', 'removal_type'), '') as later_removal_type,
    score,
    controversiality,
    created_utc as commented_at,
    retrieved_on as retrieved_at
from source
