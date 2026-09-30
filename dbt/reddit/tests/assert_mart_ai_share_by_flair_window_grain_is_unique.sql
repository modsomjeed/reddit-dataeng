select
    flair,
    period,
    count() as rows
from {{ ref('mart_ai_share_by_flair_window') }}
group by flair, period
having rows > 1
