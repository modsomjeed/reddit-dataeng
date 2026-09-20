-- raw_stories เป็น append-only: รันวันเดิมซ้ำจะได้ snapshot ใหม่เพิ่มเข้ามา
-- สัญญาของ stg_hn__stories คือ "หนึ่ง story = แถวเดียว และต้องเป็น snapshot ล่าสุด"
-- นี่คือหัวใจของ idempotency ทั้งโปรเจกต์ ถ้า test นี้แดงแปลว่า mart กำลังรายงาน
-- คะแนนเก่าที่ถูกแทนที่ไปแล้ว
--
-- ผ่านเมื่อไม่มีแถวคืนมา

with latest_in_raw as (

    select
        story_id,
        max(ingested_at) as max_ingested_at
    from {{ source('raw', 'raw_stories') }}
    group by story_id

)

select
    s.story_id,
    s.ingested_at as staging_ingested_at,
    l.max_ingested_at
from {{ ref('stg_hn__stories') }} as s
inner join latest_in_raw as l using (story_id)
where s.ingested_at != l.max_ingested_at
