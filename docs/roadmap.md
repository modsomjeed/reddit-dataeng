# Roadmap — พาทำทีละ step (map กับหัวข้อ bootcamp)

โปรเจค: **Reddit ELT (r/dataengineering)** บน Airflow + dbt + ClickHouse + MinIO + Looker Studio

แต่ละ phase ผูกกับหัวข้อที่เรียนใน internal bootcamp โดยตรง ทำไล่จากบนลงล่างได้เลย
เครื่องหมาย ✅ = มี scaffold ให้แล้วในrepo, 🔨 = ต้องลงมือ/กรอกค่าเอง, 🚀 = ของแถม (bonus)

---

## Phase 0 — Thinking with Data (Advanced)
**เป้าหมาย:** ตั้งคำถามก่อนเขียนโค้ด เพื่อกำหนดว่า mart/dashboard ต้องตอบอะไร

✅ คำถาม 6 ข้อ + ตาราง map คำถาม → mart → chart — ดู [`docs/questions.md`](./questions.md)
🔨 อ่านทวนแล้วปรับให้เป็นคำถามที่ตัวเองอยากรู้จริง

> คำถามพวกนี้ = spec ของ marts (`agg_daily_subreddit`, `fct_posts`, `dim_authors`)
> ทำ phase นี้ก่อน จะได้ไม่ดึง field ที่ไม่ได้ใช้
> จะเพิ่ม mart ใหม่ ต้องเพิ่มคำถามที่มันตอบก่อน — mart ที่ไม่มีคำถามรองรับ ไม่ต้องสร้าง

---

## Phase 1 — Data Engineering 101 + Coding Essentials + Data Architecture Design
**เป้าหมาย:** วางสถาปัตยกรรม + โครง repo

✅ โครง repo, medallion architecture (bronze/silver/gold) — ดู `docs/architecture.md`
✅ เลือก ELT (ไม่ใช่ ETL) เพราะ transform หนักๆ ให้ ClickHouse/dbt ทำในคลัง
🔨 ทำความเข้าใจ diagram + วาด draw.io ของตัวเองใส่ `images/` ไว้โชว์ใน README

**คำสั่งเริ่ม:**
```bash
cp .env.example .env      # แล้วกรอก Reddit credentials + Fernet key
make build && make init   # init = up + รอ airflow + ติดตั้ง dbt packages
```

---

## Phase 2 — Data Pipelines with Airflow
**เป้าหมาย:** orchestrate E + L ด้วย DAG

✅ `airflow/dags/reddit_elt_dag.py` — DAG 5 task พร้อม retry + XCom
✅ `airflow/dags/scripts/reddit_extract.py` — PRAW ดึง hot+new+top แล้ว land NDJSON ลง MinIO
✅ `airflow/dags/scripts/clickhouse_load.py` — ClickHouse `s3()` อ่านจาก MinIO → `raw_posts`
🔨 สมัคร Reddit app (type = script) เอา client_id/secret มาใส่ `.env`
🔨 เปิด DAG ใน UI (localhost:8080) กด trigger / `make trigger`
🔨 ตรวจว่า task เขียว + เช็คไฟล์ใน MinIO console (localhost:9001)

> script ทั้งสามอยู่ใต้ `airflow/dags/` เพราะ compose ตั้ง `PYTHONPATH=/opt/airflow/dags`
> DAG จึง `import` ด้วย `from scripts.reddit_extract import ...` ได้ตรงๆ

**สิ่งที่ควรอธิบายได้:** ทำไมแยก extract กับ load, XCom ส่ง key อย่างไร, retry/idempotency

---

## Phase 3 — Analytics Engineering with dbt
**เป้าหมาย:** transform เป็น staging → marts

✅ `dbt/models/staging/stg_reddit__posts.sql` — clean + de-dup เอา snapshot ล่าสุด
✅ marts: `fct_posts`, `dim_authors`, `agg_daily_subreddit`
✅ sources + `ref()` lineage
🔨 `make dbt-run` (ถ้ารัน `make init` แล้ว dbt_utils ติดตั้งให้อัตโนมัติ)
🔨 `make dbt-docs` เพื่อ generate lineage graph ที่ `dbt/target/` (แคปใส่ README ได้)

**สิ่งที่ควรอธิบายได้:** staging vs marts, materialization (view vs table), de-dup ด้วย window function

---

## Phase 4 — Data Governance
**เป้าหมาย:** คุณภาพ + ความน่าเชื่อถือของข้อมูล

✅ dbt tests: `not_null`, `unique`, `dbt_utils.accepted_range` (score, upvote_ratio 0–1 ฯลฯ)
✅ `source freshness` (เตือนถ้าข้อมูลเก่าเกิน 26 ชม.)
✅ naming convention: `stg_`, `fct_`, `dim_`, `agg_` + คำอธิบายทุก model/column
🔨 `make dbt-test` ต้องผ่านทั้งหมด
🔨 `make dbt-freshness` — `dbt test` ไม่ได้รัน source freshness ให้ ต้องสั่งแยก
🔨 จด data dictionary สั้นๆ + ประเด็น PII (author = username สาธารณะ, ไม่เก็บ PII เพิ่ม)

> ห้ามลด `accepted_range` หรือถอด `not_null`/`unique` เพื่อให้ test เขียว —
> test พวกนี้คือสัญญาว่าข้อมูลถูกต้อง ถ้าแดงแปลว่า pipeline มีปัญหา ไม่ใช่ test มีปัญหา

**สิ่งที่ควรอธิบายได้:** test แต่ละแบบกันปัญหาอะไร, freshness/observability, lineage = governance

---

## Phase 5 — Dashboard Design + Data Product
**เป้าหมาย:** dashboard ที่บังคับใช้ (Looker Studio)

✅ `airflow/dags/scripts/export_to_sheets.py` — push marts → Google Sheet (สะพานให้ Looker อ่าน local ClickHouse)
✅ คู่มือ + layout dashboard 3 หน้า — ดู `docs/looker_studio_setup.md`
🔨 สร้าง service account + Google Sheet, ตั้ง `ENABLE_SHEETS_EXPORT=true`
🔨 ต่อ Looker Studio → ทำ scorecard + time series + top posts + heatmap ชั่วโมง
🔨 แคปหน้า dashboard ใส่ `images/` แล้วอ้างใน README

**สิ่งที่ควรอธิบายได้:** เลือก chart ตามคำถาม Phase 0, ทำไมต้องมี serving layer

---

## Phase 6 — ตอบ 3 คำถาม + ส่งงาน
✅ README มีคำตอบ 3 ข้อครบแล้ว (What learned / How improve / Do differently) — ปรับให้เป็นเสียงตัวเอง
✅ git repo + remote `origin` ตั้งไว้แล้ว (ไม่ต้อง `git init` ใหม่)
🔨 `git push` ขึ้น GitHub
🔨 ใส่ลิงก์ dashboard (แชร์แบบ view) ใน README

---

## 🚀 Bonus (หัวข้อ bootcamp ที่เหลือ — ทำเพิ่มเพื่อคะแนน/พอร์ต)

- **Stream Processing with Kafka** 🚀 — เพิ่ม producer อ่าน `subreddit.stream.submissions()`
  ส่งเข้า Kafka topic แล้ว consumer เขียนลง ClickHouse (มี Kafka engine table ได้)
- **Machine Learning** 🚀 — โมเดลทำนาย `score` จาก title/flair/created_hour หรือ topic clustering
- **Agentic AI + RAG** 🚀 — ทำ embedding ของ `selftext` + RAG ให้ถาม-ตอบเนื้อหาในซับได้

---

## ลำดับลงมือที่แนะนำ (ครั้งแรก)
1. `cp .env.example .env` → กรอก Reddit + Fernet key
2. `make build && make init`
3. เปิด DAG `reddit_elt` → `make trigger` → ดูให้เขียวครบ
4. `make dbt-run && make dbt-test && make dbt-freshness`
5. เช็คตาราง marts ใน ClickHouse
6. ตั้งค่า Google Sheet + Looker Studio ทำ dashboard
7. เขียน/ปรับคำตอบ 3 ข้อใน README → `git push`
