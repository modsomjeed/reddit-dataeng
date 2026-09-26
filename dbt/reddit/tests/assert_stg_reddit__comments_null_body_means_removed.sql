-- Every comment has text in the raw data, so a null body must come from a removal.
-- Guards against ClickHouse resolving `body` to the cleaned alias instead of the raw column.
select comment_id
from {{ ref('stg_reddit__comments') }}
-- coalesce: the bug this guards against leaves is_body_removed NULL, not false
where body is null and not coalesce(is_body_removed, false)
