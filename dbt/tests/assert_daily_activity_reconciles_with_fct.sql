-- agg_daily_activity กับ fct_stories สร้างจาก staging ตัวเดียวกัน
-- ผลรวม story_count รายวันจึงต้องเท่ากับจำนวนแถวใน fct_stories เป๊ะ
-- ถ้าไม่เท่า แปลว่ามี filter หรือ join หลุดเข้ามาใน mart ใดmart หนึ่ง
-- ทำให้ scorecard บน dashboard ขัดแย้งกับตาราง detail ที่อยู่หน้าเดียวกัน
--
-- ผ่านเมื่อไม่มีแถวคืนมา

with agg as (
    select sum(story_count) as total_from_agg
    from {{ ref('agg_daily_activity') }}
),

fct as (
    select count(*) as total_from_fct
    from {{ ref('fct_stories') }}
)

select
    agg.total_from_agg,
    fct.total_from_fct
from agg
cross join fct
where agg.total_from_agg != fct.total_from_fct
