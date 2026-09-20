-- created_utc มาจาก `created_at_i` ของ Algolia ซึ่งเป็น unix epoch วินาที
-- ถ้าแปลงหน่วยผิด (เอา milliseconds มาตีเป็น seconds) วันที่จะกระเด็นไปอนาคตไกล
-- และ time series ทั้งอันจะเพี้ยนโดยที่ not_null กับ unique จับไม่ได้เลย
--
-- เผื่อ clock skew ระหว่างเครื่องเรากับ HN ไว้ 1 ชั่วโมง
--
-- ผ่านเมื่อไม่มีแถวคืนมา

select
    story_id,
    created_utc,
    now() as checked_at
from {{ ref('stg_hn__stories') }}
where created_utc > now() + interval 1 hour
