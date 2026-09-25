select
    month,
    flair,
    count() as rows
from {{ ref('mart_ai_share_by_flair_month') }}
group by month, flair
having rows > 1
