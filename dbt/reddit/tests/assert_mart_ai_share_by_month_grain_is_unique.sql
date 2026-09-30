select
    month,
    measure,
    count() as rows
from {{ ref('mart_ai_share_by_month') }}
group by month, measure
having rows > 1
