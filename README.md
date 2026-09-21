# โพสต์ยังไงให้มีคนเห็นบน Hacker News
### โปรเจกต์ปิด ODT Internal Bootcamp ของกวาง — Airflow + dbt + ClickHouse + Looker Studio

หลังจบ bootcamp กวางได้โจทย์ว่า *"เอาข้อมูลจากโปรเจกต์ Reddit ETL Pipeline
มาสร้าง data stack ของตัวเอง ด้วยเครื่องมือที่เรียนมา แล้วเอาขึ้น GitHub"*
repo นี้คือผลลัพธ์ และเป็นบันทึกว่ากวางได้อะไรจากการลงมือทำจริงบ้าง

```
HN Algolia API → MinIO (bronze) → ClickHouse → dbt (silver → gold) → Google Sheets → Looker Studio
                          └──────────── Airflow คุมทั้งเส้น วันละรอบ ────────────┘
```

---

## ข้อมูลบอกอะไรกวาง

กวางเก็บสตอรี่บน Hacker News ย้อนหลัง 2 เดือน (**62,419 เรื่อง จากผู้โพสต์ 22,419 คน**
ช่วง 20 ก.ค. – 19 ก.ย. 2026) แล้วตั้งคำถามว่า *ถ้าจะโพสต์สักเรื่อง ทำอะไรได้บ้างให้มีคนเห็น*

- **ส่วนใหญ่ไม่มีใครเห็นเลย** ครึ่งหนึ่งได้ไม่เกิน 2 คะแนน และ 62% ไม่มีคอมเมนต์สักอัน
  ขณะที่ 1% บนสุดกินคะแนนไปถึง 35% ของทั้งหมด
- **ตัวแปรที่เปลี่ยนผลได้มากที่สุดคือ "โพสต์บ่อยแค่ไหน"** คนที่โพสต์ 11 ครั้งขึ้นไป
  มีโพสต์ที่ดีที่สุดได้ 278 คะแนน เทียบกับ 17 คะแนนของคนที่โพสต์ครั้งเดียว (ต่างกัน **16 เท่า**)
- **ประเภทโพสต์** มีผลรองลงมา สตอรี่ธรรมดาติดกระแส 7.5% ส่วน Show HN กับ Ask HN แค่ ~2.7% (**2.7 เท่า**)
- **เวลาโพสต์** มีผลน้อยกว่าที่คิด ช่วงดีที่สุดกับแย่ที่สุดต่างกันแค่ **1.4 เท่า**
  (ช่วงที่ดีคือ 11–16 UTC หรือหัวค่ำเมืองไทย)

รายละเอียดการคิดและเล่าเรื่องอยู่ที่ [`docs/storytelling.md`](docs/storytelling.md)
และคำถามทั้งหมดที่ตั้งไว้ก่อนสร้างตารางอยู่ที่ [`docs/questions.md`](docs/questions.md)

---

## สิ่งที่กวางได้เรียนรู้

### 1. แหล่งข้อมูลหายไปได้ ระหว่างที่เรากำลังสร้างอยู่
กวางออกแบบฝั่งดึงข้อมูลไว้กับ Reddit API ครบแล้ว พอไปขอ key จริงถึงเพิ่งรู้ว่า Reddit
ปิดการสมัครใช้ API แบบบริการตัวเองไปตั้งแต่ พ.ย. 2025 เลยต้องย้ายไปใช้ Hacker News แทน

สิ่งที่ได้คือ ได้เห็นกับตาว่าการแบ่ง pipeline เป็นชั้นมีประโยชน์ยังไง เพราะที่ต้องแก้มีแค่ตัว extract
ส่วน warehouse, dbt, DAG และแบบ dashboard ยังใช้ของเดิมได้หมด
และได้บทเรียนว่า **วันแรกควรลองยิง API จริงก่อนสัก 10 นาที** ก่อนจะออกแบบอะไรต่อ

### 2. API บอกว่าสำเร็จ ไม่ได้แปลว่าได้ข้อมูลครบ
Algolia คืนผลได้สูงสุด 1,000 แถวต่อ query แต่วันที่คนโพสต์เยอะมีราว 1,200 เรื่อง
โค้ดวนหน้าแบบปกติจึงทำข้อมูลหายวันละ ~200 แถวแต่ไม่มี error สักอัน
กวางจับได้เพราะเอาจำนวนแถวที่ได้ไปเทียบกับ `nbHits` ที่ API บอกเอง
ตั้งแต่นั้นกวางเชื่อว่า **ข้อมูลหายแบบเงียบ ๆ อันตรายกว่า error**

### 3. Idempotency ต้องออกแบบ ไม่ได้เกิดขึ้นเอง
ชั้น raw ใน ClickHouse เก็บแบบต่อท้ายไปเรื่อย ๆ (เก็บทุก snapshot ที่ดึงมา) แล้วให้ dbt
ชั้น staging เลือกเฉพาะ snapshot ล่าสุดของแต่ละสตอรี่ กวางพิสูจน์ด้วยการรันซ้ำย้อนหลังหลายวัน
แถวใน raw เพิ่มจาก 14,184 เป็น 14,952 แต่ staging กับ mart ไม่ขยับเลยสักแถว
เลยรู้ว่ารันซ้ำหรือ backfill กี่รอบก็ไม่ทำให้ตัวเลขใน dashboard เพี้ยน

### 4. Airflow ไม่ได้ยากที่โค้ด แต่ยากที่ "เวลา"
ตอน backfill ย้อนหลัง 2 เดือน (63 runs) กวางเจอกับดักของ `data_interval` หลายรอบ
- สั่ง `-e 2026-09-19` แต่ได้ข้อมูลถึงแค่วันที่ 18 เพราะ `ds` คือ *ต้น* ช่วงเวลา ไม่ใช่วันที่รัน
- DAG ตั้งไว้ 06:00 แต่สั่ง `-s 2026-09-19` ซึ่งคือเที่ยงคืน เลยไม่ตรงกับ run ไหนเลย
- `--rerun-failed-tasks` ไม่รัน task ที่เคยสำเร็จไปแล้ว ต้องใช้ `airflow tasks clear`
- ถ้าไม่ใส่ `max_active_runs=1` หลาย run จะแย่งกันรัน dbt พร้อมกัน

### 5. dbt ทำให้ "Data Governance" จับต้องได้
จากที่เรียนเป็นแนวคิด กลายเป็นเทสต์ 28 ตัวที่รันทุกวัน ทั้ง generic test, singular test
(เช่น ยอดรวมรายวันต้องตรงกับตาราง fact, ต้องไม่มีสตอรี่จากอนาคต) และ unit test
ที่พิสูจน์ว่าถ้ามีคนแก้ `desc` เป็น `asc` ใน logic dedup เทสต์จะพังทันที
ส่วน lineage กับ data dictionary ก็ generate จาก dbt อัตโนมัติ ไม่ต้องเขียนมือแล้วค่อย ๆ ล้าสมัย

อีกเรื่องที่กวางตั้งเป็นกฎให้ตัวเองคือ **เทสต์พังให้แก้ข้อมูลหรือแก้ logic ห้ามลดเกณฑ์เทสต์ลงเพื่อให้ผ่าน**

### 6. ตัวเลขที่น่าตื่นเต้นที่สุด อาจเป็นตัวเลขที่ไม่ควรเอาไปเล่า
ตอนแรกกวางเจอว่า "โพสต์ในชั่วโมงที่ดีที่สุด ดีกว่าชั่วโมงที่แย่ที่สุดถึง 8 เท่า" ฟังดูเป็นพาดหัวที่ดีมาก
แต่พอเช็กดู ตัวเลขนี้เลือกมาจาก 168 ช่อง (7 วัน × 24 ชั่วโมง) ซึ่งแต่ละช่องมีข้อมูลน้อย
และพอแบ่งข้อมูลเป็นสองครึ่งมาเทียบกัน รูปแบบรายชั่วโมงก็ไม่ค่อยซ้ำเดิม
พอรวมเป็นช่วงละ 6 ชั่วโมงเหลือแค่ **1.4 เท่า** แต่ผลนี้คงที่ไม่ว่าจะตั้งเกณฑ์ "ติดกระแส" ไว้ที่เท่าไร
กวางเลือกเล่า 1.4 เท่า และให้เวลาโพสต์เป็นเรื่องรองแทนเรื่องหลัก

### 7. Dashboard คือ product ไม่ใช่ขั้นตอนสุดท้าย
กวางเริ่มจาก *คำถาม* ก่อนแล้วค่อยย้อนกลับมาหาตาราง (คำถาม → mart → กราฟ) และเขียนเรื่องที่จะเล่า
ด้วย GAME, What / So What / Now What และ SCQA ก่อนจะวาดกราฟแรก
คำถามครอบคลุมครบทั้ง 4 ระดับ ตั้งแต่ descriptive ไปถึง prescriptive
อีกเรื่องที่ต้องคิดคือ ClickHouse บนเครื่องตัวเองต่อกับ Looker Studio บน cloud ตรง ๆ ไม่ได้
เลยต้องออกแบบชั้น serving (ส่งออกไป Google Sheets) โดยตั้งใจตั้งแต่ต้น

### 8. งานจริงมีเรื่องนอกตำราเยอะ
image ของ MinIO บน Docker Hub ดึงไม่ได้ ต้องย้ายไป quay.io, tag บางตัวมีแค่ amd64 ใช้กับ Mac M-series ไม่ได้,
port 9000 ชนกับ SonarQube, container ของโปรเจกต์เก่าที่ตั้ง `restart: always` ไว้
มาแย่ง port ทุกครั้งที่เปิด Docker และค่าใน `.env` ที่ค้างจากตอนใช้ Reddit
ทำให้ load หาตารางไม่เจอ เรื่องพวกนี้ไม่มีในสไลด์ แต่กินเวลาจริงมากกว่าเขียนโค้ดอีก

---

## ถ้าได้เริ่มใหม่ กวางจะ…

- **ลองยิง API จริงตั้งแต่วันแรก** ก่อนจะออกแบบอะไรทั้งหมด
- **เขียนคำถามก่อนเขียน extract** แล้วค่อยย้อนกลับมาหาว่าต้องเก็บคอลัมน์อะไร
- **ทำให้ครบทุกชั้นด้วยข้อมูล 1 วัน** ก่อนค่อยขยายเป็น 2 เดือน ได้ feedback เร็วกว่ามาก
- **เลือกวิธีเชื่อมกับ BI ตั้งแต่ต้น** ไม่ใช่มาเจอปัญหาตอนท้าย

## ต่อยอดได้อีก

- เปลี่ยน mart เป็น dbt incremental เมื่อประวัติข้อมูลยาวขึ้น
- ดึงคอมเมนต์มาเป็นแหล่งที่สอง เพื่อวัด "การพูดคุย" ได้จริง
- แยก DAG ด้วย Airflow Assets และเก็บชั้น silver เป็น Parquet
- แจ้งเตือนเข้า Slack เมื่อ freshness หรือเทสต์พัง และรัน `dbt build` ใน CI
- โมเดล ML ทำนายโอกาสติดกระแส และ RAG ค้นเนื้อหาสตอรี่ (ต่อจากหัวข้อ ML / Agentic AI ใน bootcamp)

---

## Stack

| หน้าที่ | เครื่องมือ |
|---|---|
| Orchestration | Apache Airflow 2.10 (LocalExecutor) |
| Ingestion | Python + HN Algolia API |
| Data lake (bronze) | MinIO (S3-compatible) |
| Warehouse | ClickHouse 24.8 |
| Transformation | dbt 1.8 + `dbt-clickhouse` + `dbt_utils` |
| Data quality | dbt tests (28 ตัว) + source freshness |
| Dashboard | Looker Studio ผ่าน Google Sheets |

### Pipeline (DAG `hn_elt`, ทุกวัน 06:00 UTC)

```
extract_stories → load_clickhouse_raw → dbt_run → dbt_test → dbt_source_freshness → export_to_sheets
```

| Task | ชั้น | ทำอะไร |
|---|---|---|
| `extract_stories` | E / bronze | ดึงสตอรี่ 1 วัน (UTC) จาก Algolia → NDJSON → MinIO |
| `load_clickhouse_raw` | L | ClickHouse อ่านไฟล์จาก MinIO ด้วย `s3()` → `raw_stories` |
| `dbt_run` | T | สร้าง `stg_hn__stories` และ mart ทั้งหมด |
| `dbt_test` | Governance | not_null / unique / accepted_values / accepted_range / singular / unit |
| `dbt_source_freshness` | Governance | ล้มถ้าชั้น bronze เก่าเกิน 26 ชม. |
| `export_to_sheets` | Product | mart → Google Sheet → Looker Studio |

### Data models

- `stg_hn__stories` — เหลือ snapshot ล่าสุดต่อสตอรี่ และแปลง HTML เป็นข้อความ
- `fct_stories` — 1 แถวต่อ 1 สตอรี่
- `dim_authors` — สรุปรายผู้โพสต์
- `agg_daily_activity` — สรุปรายวัน ใช้ทำกราฟหลัก

Lineage: [`docs/lineage.md`](docs/lineage.md) · Data dictionary: [`docs/data-dictionary.md`](docs/data-dictionary.md) ·
Architecture: [`docs/architecture.md`](docs/architecture.md)

---

## ลองรันเอง

ต้องมีแค่ Docker + Docker Compose ไม่ต้องมี API key เพราะ HN Algolia API เปิดให้ใช้ฟรี

```bash
cp .env.example .env
# สร้าง Fernet key แล้วใส่ใน AIRFLOW_FERNET_KEY
python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

make build      # build image Airflow (มี dbt ในตัว)
make init       # เปิด stack รอ Airflow พร้อม แล้วติดตั้ง dbt packages
make trigger    # รัน DAG hn_elt หนึ่งรอบ
```

- Airflow → http://localhost:8080 (admin / admin)
- MinIO console → http://localhost:9001 (minio / minio12345)
- ClickHouse HTTP → http://localhost:8123

```bash
make dbt-test       # เทสต์คุณภาพข้อมูล
make dbt-freshness  # เช็กว่าข้อมูลไม่เก่าเกินไป (dbt test ไม่ได้รันส่วนนี้ให้)
make docs-gen       # generate lineage + data dictionary ลง docs/
```

ตั้งค่า dashboard ตาม [`docs/looker_studio_setup.md`](docs/looker_studio_setup.md)

## โครงสร้าง repo

```
reddit-dataeng/
├── docker-compose.yml          # Airflow + MinIO + ClickHouse + Postgres
├── Makefile
├── airflow/dags/               # hn_elt_dag.py + scripts/ (extract · load · export)
├── clickhouse/init/            # DDL ของ raw_stories
├── dbt/models/                 # staging/ · marts/ · tests/
├── scripts/generate_docs.py    # dbt artifacts → docs/lineage.md, data-dictionary.md
└── docs/                       # คำถาม · storytelling · architecture · checklist
```

## สถานะ

- ✅ Pipeline รันครบ 63 วัน, เทสต์ 28/28 ผ่าน, freshness ผ่าน
- ✅ ออกแบบคำถาม เรื่องที่จะเล่า และ layout dashboard แล้ว
- 🚧 กำลังเชื่อม Google Sheets และสร้าง dashboard ใน Looker Studio

## ขอบคุณ

- ข้อมูลจาก [HN Algolia API](https://hn.algolia.com/api) (Hacker News โดย Y Combinator)
- ไอเดียตั้งต้นจาก [Reddit-API-Pipeline](https://github.com/ABZ-Aaron/Reddit-API-Pipeline)
  ใน Data Engineer Cafe โปรเจกต์นี้สร้างใหม่ทั้งหมดบน stack ของตัวเอง
- ODT Internal Bootcamp สำหรับเนื้อหาทั้งหมดที่เอามาใช้
- ใช้ Claude Code เป็นผู้ช่วยสอนและคู่คิดระหว่างทำ
