# คำถามเชิงวิเคราะห์ (Phase 0 — Thinking with Data)

เอกสารนี้เขียน **ก่อน** สร้าง mart และ dashboard เพื่อให้ทุกตารางที่สร้างมีคำถามรองรับ
ไม่ใช่สร้าง mart ไว้ก่อนแล้วค่อยหาคำถามมาใส่ทีหลัง

**กติกา:** จะเพิ่ม mart ใหม่ ต้องเพิ่มคำถามที่มันตอบลงตารางนี้ก่อน
mart ที่ไม่มีคำถามรองรับ = ไม่ต้องสร้าง

แหล่งข้อมูลคือ **Hacker News** ผ่าน HN Algolia API — เหตุผลที่ไม่ใช่ Reddit อยู่ในหัวข้อ
"ทำไมถึงไม่ใช่ Reddit" ด้านล่าง

---

## คำถาม → mart → chart

| # | คำถาม | mart ที่ตอบ | คอลัมน์ที่ใช้ | chart ใน Looker Studio |
|---|-------|-------------|----------------|------------------------|
| 1 | ชุมชน HN คึกคักแค่ไหนในแต่ละวัน | `agg_daily_activity` | `activity_date`, `story_count` | time series |
| 2 | คุณภาพการมีส่วนร่วมเปลี่ยนไปตามเวลาไหม | `agg_daily_activity` | `avg_score`, `avg_comments` | time series สองแกน |
| 3 | โพสต์ที่มีลิงก์กับโพสต์ข้อความล้วน อันไหนได้ engagement ดีกว่า | `agg_daily_activity`, `fct_stories` | `self_posts`, `link_posts`, `is_self`, `engagement_score` | stacked bar + scorecard เทียบค่าเฉลี่ย |
| 4 | Ask HN / Show HN / ข่าวทั่วไป แบบไหนดึงคนได้มากสุด | `fct_stories`, `agg_daily_activity` | `post_type`, `engagement_score`, `ask_hn_count`, `show_hn_count` | bar chart เรียงจากมากไปน้อย |
| 5 | เวลาไหนของสัปดาห์คนโพสต์มากสุด | `fct_stories` | `created_hour`, `created_dow` | heatmap ชั่วโมง × วันในสัปดาห์ |
| 6 | ใครคือ contributor ตัวท็อป และเรื่องที่ดังที่สุดคืออะไร | `dim_authors`, `fct_stories` | `author`, `total_stories`, `avg_score`, `best_story_score` / `title`, `permalink`, `score` | table สองอัน (คน + เรื่องพร้อมลิงก์) |

---

## ทำไม mart ถึงมีสามตัว

| mart | grain | ตอบคำถามข้อ | เหตุผลที่แยกออกมา |
|------|-------|--------------|---------------------|
| `agg_daily_activity` | 1 แถว = 1 วัน | 1, 2, 3, 4 | dashboard หน้าแรกโหลดเร็ว ไม่ต้อง aggregate ตอน query |
| `fct_stories` | 1 แถว = 1 story (สถานะล่าสุด) | 3, 4, 5, 6 | ต้อง drill ลงระดับโพสต์เพื่อดูประเภท / ชั่วโมง / ลิงก์ |
| `dim_authors` | 1 แถว = 1 author | 6 | มิติของคน แยกจาก fact ตามหลัก star schema |

---

## ทำไมถึงไม่ใช่ Reddit

โปรเจคนี้ตั้งใจทำกับ r/dataengineering ตาม brief ตอนแรก แต่ระหว่างลงมือพบว่า
Reddit **ปิดการสมัคร API แบบ self-service ไปตั้งแต่ พ.ย. 2025** ตาม Responsible Builder Policy
OAuth token ใหม่ทุกตัวต้องผ่านการอนุมัติด้วยมือ และ endpoint `.json` สาธารณะที่เคยเรียกได้
โดยไม่ต้อง login ก็ถูกปิดตามไปด้วย ทดสอบแล้วได้ผลดังนี้

| endpoint | ผล |
|---|---|
| `www.reddit.com/r/<sub>/hot.json` | 403 หน้า block ของ Reddit |
| `api.reddit.com/r/<sub>/hot` | 403 |
| `old.reddit.com/r/<sub>/hot.json` | 302 เด้งไปหน้า login |

ทางเลือกที่พิจารณาคือ (ก) ใช้ Reddit dataset ย้อนหลังจาก Hugging Face หรือ (ข) เปลี่ยนแหล่ง
เลือก (ข) เพราะ dataset ที่ครบที่สุด (`HuggingFaceGECLM/REDDIT_submissions`) มี `upvote_ratio`
เป็น null สลับกับมีค่าตามยุคที่ Pushshift เก็บ ซึ่งเมื่อ load ลงคอลัมน์ `Float32` จะกลายเป็น `0.0`
ทำให้ค่าเฉลี่ยผิดโดยที่ dbt test ยังผ่านเขียว — เป็น false green ที่อันตรายกว่าการยอมรับว่า
ข้อมูลนั้นไม่มีตั้งแต่แรก อีกทั้ง dataset หยุดอยู่ที่ปี 2021 ทำให้ DAG รายวันไม่มีความหมาย

HN Algolia API ไม่ต้องใช้ credentials กรองตามช่วงเวลาได้ และสถาปัตยกรรมทั้งหมด
(MinIO → ClickHouse → dbt → Looker) ใช้ต่อได้โดยไม่ต้องรื้อ

---

## ข้อจำกัดที่รู้ตัว

**ไม่มี upvote ratio** — HN ไม่เปิดเผยจำนวน downvote จึงไม่มีอัตราส่วน upvote ให้คำนวณ
คำถามข้อ 2 เรื่อง "คุณภาพการมีส่วนร่วม" จึงวัดด้วย `avg_score` กับ `avg_comments` แทน
และ **ถอด dbt test `accepted_range 0–1` ที่เคยผูกกับ `upvote_ratio` ออกอย่างเปิดเผย**
ไม่ใช่ปล่อยคอลัมน์ว่างไว้ให้ test ผ่านแบบไร้ความหมาย

**ตอบไม่ได้: "มี comment กี่อันต่อวัน"** — pipeline ดึงเฉพาะ story ไม่ได้ดึงตัว comment
`num_comments` เป็นตัวนับที่ติดมากับ story ณ เวลาที่ extract บอกได้ว่าเรื่องนั้นมีคนคุยกี่ครั้ง
แต่บอกไม่ได้ว่า comment เกิดวันไหนหรือใครเขียน ถ้าต้องการต้องเพิ่ม `tags=comment` เป็น source ที่สอง

**ตัวเลข score เป็นค่า ณ เวลาที่ดึง ไม่ใช่ค่าสุดท้าย** — เรื่องที่เพิ่งลงไม่กี่ชั่วโมง score ยังไม่นิ่ง
DAG ดึงข้อมูลของ "เมื่อวาน" ตอนเช้า จึงได้ค่าที่ค่อนข้างเสถียรแล้ว แต่ยังไม่ใช่ค่าสุดท้าย
`raw_stories` เก็บทุก snapshot ไว้ ถ้ารันซ้ำวันเดิมจะได้ค่าที่อัปเดตขึ้น และ staging จะเลือกอันล่าสุด

**`post_type` เดาจากหัวข้อ** — HN ไม่มี flair ระบบ การแยก Ask HN / Show HN ใช้คำขึ้นต้นของ title
ซึ่งเป็นธรรมเนียมของชุมชนที่คนส่วนใหญ่ทำตาม แต่ไม่ได้บังคับ จึงมีโอกาสจัดประเภทพลาดเล็กน้อย

**`dim_authors` ไม่นับ `[deleted]`** — เรื่องที่เจ้าของบัญชีถูกลบถูกกรองออก ยอดรวมใน `dim_authors`
จึงน้อยกว่าใน `fct_stories` เล็กน้อย เป็นความตั้งใจ ไม่ใช่ข้อมูลหาย

---

## PII

`author` เป็น username สาธารณะบน Hacker News ไม่ใช่ชื่อจริงหรืออีเมล pipeline ไม่ได้ดึง
ข้อมูลระบุตัวตนเพิ่มเติมใดๆ และไม่พยายาม join กับแหล่งอื่นเพื่อระบุตัวบุคคล
`story_text` เก็บข้อความตามที่ผู้ใช้โพสต์เอง — ถ้ามีใครใส่ข้อมูลส่วนตัวลงไปเอง ก็จะติดมาด้วย
ซึ่งเป็นข้อจำกัดที่ยอมรับสำหรับโปรเจคเรียนรู้นี้
