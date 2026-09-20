# Checklist ปิดงาน — จาก workshop ใน bootcamp สู่โปรเจกต์ที่ส่งได้

เอกสารนี้ไล่ทุก workshop / hands-on / lab จากสไลด์ทั้ง 5 ไฟล์ แล้วแปลงเป็นงานที่ต้องทำจริง
ในโปรเจกต์นี้ พร้อมบอกว่าอะไรเสร็จแล้วและอะไรยังขาด

🟢 เสร็จ · 🟡 บางส่วน · 🔴 ยังไม่เริ่ม · 👩 กวางต้องทำเอง (ต้องล็อกอิน/ตัดสินใจ) · 🤖 ให้ Claude ทำได้

---

## เส้นทางวิกฤต (critical path)

Phase 5 — Dashboard คือ **deliverable เดียวที่โจทย์บังคับแต่ยังไม่เริ่ม** และมันติดที่
การสร้าง GCP service account ซึ่งต้องทำในเบราว์เซอร์ด้วยบัญชี Google ของกวาง

> **ทำ M2.1 ให้เสร็จก่อนเป็นอันดับแรก** แล้วงานอื่นค่อยทำคู่ขนานไปได้

---

## M1 — ปิดงานค้างจากวันนี้  ·  ~20 นาที

- [ ] 🤖 รอ backfill 2 เดือนจบ แล้วตรวจว่าทุกวันมีข้อมูลต่อเนื่อง ไม่มีวันหาย
- [ ] 🤖 `make dbt-test` + `make dbt-freshness` ต้องเขียวหลัง backfill
- [ ] 🤖 ลบของตกค้างยุค Reddit — ClickHouse database `reddit`, MinIO bucket `reddit-raw`
- [ ] 🤖 เคลียร์ DAG run สีแดงที่ค้างใน UI (`manual__2026-09-20T08:26:51`)
- [ ] 👩 สั่ง push 5 commits ขึ้น GitHub (backup งานก่อนทำต่อ)

---

## M2 — Dashboard & Data Storytelling  ·  ~3 ชม.  ·  **สำคัญที่สุด**

อ้างอิง: `DataDesignDecisions.pdf` ทั้งเล่ม + `docs/looker_studio_setup.md`

### M2.1 เชื่อมท่อข้อมูลไป Looker Studio  🔴
- [ ] 👩 สร้าง GCP project + service account + ดาวน์โหลด JSON key
- [ ] 👩 วาง key ที่ `secrets/gcp-service-account.json` (gitignored แล้ว)
- [ ] 👩 สร้าง Google Sheet เปล่า + แชร์สิทธิ์ Editor ให้อีเมล service account
- [ ] 👩 ก๊อป Sheet ID จาก URL มาใส่ `GSHEET_ID` ใน `.env`
- [ ] 🤖 ตั้ง `ENABLE_SHEETS_EXPORT=true` แล้วรัน DAG ตรวจว่า 3 marts ขึ้น Sheet ครบ

### M2.2 ออกแบบก่อนลงมือวาด  🔴
อย่าเปิด Looker Studio ก่อนทำ 2 ข้อนี้ — สไลด์หน้า 46 บอกว่า dashboard ที่ดีต้องเล็งผู้ใช้คนเดียว

- [ ] 👩 **User Empathy Map** (หน้า 47) — เลือกผู้ใช้ 1 คน (เช่น "คนทำ content ด้าน tech")
      แล้วเขียน SEE / THINK / DO ว่าเขาเห็นอะไร คิดอะไร ตัดสินใจอะไร
- [ ] 🤖 **จับคู่คำถาม → หมวด viz** (หน้า 35, 42) — 6 คำถามใน `questions.md`
      เข้าหมวดไหนบ้าง: correlation / ranking / distribution / change over time / magnitude / part-to-whole
- [ ] 🤖 เขียน layout 3 หน้าลง `looker_studio_setup.md` ว่าแต่ละหน้ามี chart อะไร ตอบคำถามข้อไหน

### M2.3 สร้าง dashboard  🔴
- [ ] 👩 ต่อ Looker Studio → Google Sheets connector → เลือก 3 tabs
- [ ] 👩 **หน้า 1 Overview** — scorecard (stories, avg score, authors) + time series รายวัน
- [ ] 👩 **หน้า 2 Content** — bar chart ตาม `post_type` + stacked bar self vs link + heatmap ชั่วโมง × วัน
- [ ] 👩 **หน้า 3 People** — table top authors + table top stories พร้อมลิงก์
- [ ] ⚠️ ตัดสินใจเรื่อง **วันปัจจุบันที่ยังไม่จบ** — กรองออกจากกราฟ หรือใส่หมายเหตุกำกับ
      (ไม่งั้น time series จะมีหน้าผาดิ่งที่ทำให้คนอ่านเข้าใจผิด)
- [ ] 👩 ตั้งค่าแชร์แบบ "anyone with the link can view"

### M2.4 Data Storytelling  🔴
- [ ] 🤖 เขียน **GAME** (หน้า 56) — Goal / Audience / Message / Expression ลง `docs/storytelling.md`
- [ ] 🤖 เขียน **What? So What? Now What?** (หน้า 65) จาก insight ที่เจอในข้อมูลจริง
- [ ] 🤖 แปลงเป็น **SCQA** (หน้า 63) — Situation / Complication / Question / Answer
- [ ] 👩 ทวนด้วย checklist 7 ข้อ (หน้า 72) — goal ชัดไหม, so what ชัดไหม, now what ทำได้จริงไหม

### M2.5 เก็บหลักฐาน  🔴
- [ ] 👩 แคปหน้า dashboard ทั้ง 3 หน้า ใส่ `images/`
- [ ] 🤖 อ้างรูป + ใส่ลิงก์ dashboard ใน README

---

## M3 — ปิดช่องว่าง dbt  ·  ~1 ชม.  ·  ✅ เสร็จแล้ว

อ้างอิง: `analytics-engineering-dbt-clickhouse.pdf` หน้า 46–60

- [x] 🤖 **Singular test** (หน้า 55–56) — เขียน `.sql` ใน `dbt/tests/`
      เช่น ยืนยันว่าไม่มี story ที่ `score < 0` หรือ `created_utc` อยู่ในอนาคต
- [x] 🤖 **Unit test** (หน้า 57–59) — mock input แล้วยืนยัน logic
      เช่น `engagement_score = score + num_comments` และ `post_type` แยก Ask/Show ถูกต้อง
- [x] 🤖 lineage graph — ทำเป็น Mermaid ใน `docs/lineage.md` แทนการแคปภาพ (GitHub เรนเดอร์ให้ และอัปเดตตามโค้ดด้วย `make docs-gen`)
- [x] 🤖 **data dictionary** + PII — `docs/data-dictionary.md` generate จาก dbt artifacts

---

## M4 — ปิดช่องว่าง Thinking with Data  ·  ~30 นาที

อ้างอิง: `Thinking with Data.pdf` หน้า 41–49

ตอนนี้คำถามทั้ง 6 ข้อใน `questions.md` เป็น Descriptive/Diagnostic ล้วน ยังขาดอีก 2 ระดับ

- [ ] 🤖 ติดป้ายคำถามเดิม 6 ข้อว่าเป็นระดับไหน (Descriptive / Diagnostic)
- [ ] 👩 เพิ่มคำถาม **Predictive** — เช่น "โพสต์แบบไหนมีแนวโน้มได้คะแนนสูง" แล้วบอกว่า mart ไหนตอบ
- [ ] 👩 เพิ่มคำถาม **Prescriptive** — เช่น "ถ้าจะโพสต์ให้คนเห็นเยอะ ควรโพสต์กี่โมง วันไหน แบบไหน"
- [ ] 🤖 ถ้าคำถามใหม่ต้องการ mart ใหม่ ให้เพิ่ม — แต่ตามกติกาใน `questions.md`
      ต้องเพิ่มคำถามก่อนเสมอ ห้ามสร้าง mart ที่ไม่มีคำถามรองรับ

---

## M5 — ยกระดับงานวิศวกรรม (ไม่บังคับ แต่ได้คะแนน)  ·  ~2 ชม.

- [ ] 🤖 **Airflow Connections & Hooks** แทน env var ดิบ (Airflow deck หน้า 41, poc 07)
      — เป็น best practice จริงและสไลด์สอนไว้ แต่โปรเจกต์ยังไม่ได้ใช้
- [ ] 🤖 **Parquet ใน silver layer** (DE101 hands-on 5.1) — ตอนนี้ NDJSON เข้า ClickHouse ตรงๆ
      ควรมีขั้น bronze NDJSON → silver Parquet ให้ครบ medallion ตามที่เรียน
- [ ] 🤖 **แยก DAG ingest / transform** ด้วย Asset-based scheduling (Airflow deck หน้า 48)
      — จะแก้ปัญหาที่ backfill 48 วันต้องรัน dbt ซ้ำ 48 รอบ
- [ ] 🤖 **Window functions เพิ่ม** (DE101 slide 47–50) — `LAG` เทียบยอดวันก่อนหน้า (day-over-day %)
      ตอนนี้ใช้แค่ `row_number()` ใน staging

---

## M6 — ส่งงาน  ·  ~1 ชม.

- [ ] 👩 วาด **architecture diagram** ด้วย draw.io ใส่ `images/` แล้วอ้างใน README
- [ ] 👩 ปรับคำตอบ 3 คำถามใน README ให้เป็นเสียงตัวเอง
      (What learned / How improve / Do differently)
- [ ] 🤖 quality gate รอบสุดท้าย — `make dbt-run && make dbt-test && make dbt-freshness`
- [ ] 🤖 ตรวจว่าไม่มีความลับหลุดใน repo — `git log -p | grep -iE "secret|password|key"`
- [ ] 👩 `git push` ครั้งสุดท้าย

---

## Bonus — หัวข้อ bootcamp ที่ยังไม่มีในโปรเจกต์

4 หัวข้อนี้ไม่มีไฟล์สไลด์ในโฟลเดอร์ และไม่ได้อยู่ในโจทย์ ทำเพิ่มถ้ามีเวลาเหลือ

- [ ] **Stream Processing with Kafka** — producer poll HN Firebase `/v0/maxitem.json`
      → Kafka topic → ClickHouse Kafka engine table
- [ ] **Machine Learning** — ทำนาย `score` จาก title / post_type / created_hour
- [ ] **Agentic AI + RAG** — embedding ของ `story_text` + ถาม-ตอบเนื้อหา
- [ ] **Data Governance เชิงลึก** — data lineage, access control, retention policy

---

## Definition of Done — ถือว่าจบเมื่อ

1. `make dbt-test` และ `make dbt-freshness` เขียวทั้งหมด
2. DAG รันผ่านครบทุก task และ backfill พิสูจน์แล้วว่า idempotent
3. Looker Studio dashboard เปิดดูได้จากลิงก์สาธารณะ และตอบคำถามใน `questions.md` ได้จริง
4. README มี: architecture diagram · ภาพ dashboard · ภาพ dbt lineage · คำตอบ 3 คำถาม
5. เอกสารครบ: `questions.md` (4 ระดับ) · `architecture.md` · `storytelling.md` (GAME + SCQA) · data dictionary
6. ไม่มีความลับหลุดใน git history
7. push ขึ้น GitHub เรียบร้อย
