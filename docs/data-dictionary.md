# Data Dictionary

> สร้างอัตโนมัติด้วย `make docs-gen` — อย่าแก้ไฟล์นี้ด้วยมือ
> คำอธิบายคอลัมน์มาจาก `description:` ใน schema yml ของ dbt

| ชั้น | Database | ใครสร้าง |
|---|---|---|
| bronze (raw) | `hackernews` | Airflow task `load_clickhouse_raw` |
| silver (staging) | `hackernews_staging` | dbt |
| gold (marts) | `hackernews_marts` | dbt |


## 🗄️ `hackernews.raw_stories` — bronze

One row per (story_id, ingested_at) snapshot, as extracted from the HN Algolia API. Append-only: re-running a day adds a newer snapshot rather than replacing the old one.

**Grain:** 1 แถว = 1 snapshot ของ 1 story → `(story_id, ingested_at)`  
**Engine:** `MergeTree` · `PARTITION BY ingest_date` · `ORDER BY (story_id, ingested_at)`

| คอลัมน์ | ชนิด | คำอธิบาย | tests |
|---|---|---|---|
| `story_id` | `String` | Hacker News item id (Algolia objectID). Not unique here ― one row per snapshot. | `not_null` |
| `title` | `String` | Story headline as submitted. May carry an 'Ask HN:' / 'Show HN:' prefix. | `not_null` |
| `story_text` | `String` | Body of a self-post, as escaped HTML from Algolia (real tags plus entity-encoded characters). Empty string for link posts. | — |
| `author` | `String` | Submitter's public HN username. '[deleted]' when the account is gone. | `not_null` |
| `score` | `Int32` | Points at extraction time. HN does not expose downvotes, so there is no upvote ratio. | — |
| `num_comments` | `Int32` | Comment count at extraction time. | — |
| `permalink` | `String` | Canonical HN discussion URL for the story. | — |
| `url` | `String` | Outbound link the story points at. Empty for self-posts. | — |
| `post_type` | `String` | ask_hn \| show_hn \| story ― derived from the title prefix. | — |
| `is_self` | `UInt8` | 1 when the story has body text and no outbound link, 0 otherwise. | — |
| `created_utc` | `DateTime` | When the story was submitted, from Algolia's created_at_i epoch (seconds, UTC). | — |
| `ingested_at` | `DateTime` | When this snapshot was pulled. Combined with story_id it forms the grain, and staging orders on it to pick the latest state. | — |
| `ingest_date` | `Date` | Date part of ingested_at. The table's partition key. | — |

## `hackernews_staging.stg_hn__stories` — silver

Cleaned, de-duplicated Hacker News stories (latest snapshot per story_id), with HTML decoded out of story_text. This is the trusted silver model every mart builds on.

**Grain:** 1 แถว = 1 story (snapshot ล่าสุด) → `story_id`  
**Materialized:** `view`

| คอลัมน์ | ชนิด | คำอธิบาย | tests |
|---|---|---|---|
| `story_id` | `String` | Unique HN item id (grain of this model). | `not_null`, `unique` |
| `title` | `String` | Story headline, trimmed of surrounding whitespace. | `not_null` |
| `story_text` | `String` | Body of a self-post with HTML tags stripped and entities decoded (extractTextFromHTML then decodeHTMLComponent). Empty for link posts. | — |
| `author` | `String` | Submitter's public HN username. | — |
| `score` | `Int32` | Points at the latest snapshot. Can be 0 for a brand-new story. | `not_null`, `accepted_range` |
| `num_comments` | `Int32` | Comment count at the latest snapshot. | `accepted_range` |
| `permalink` | `String` | Canonical HN discussion URL ― used as the click-through in the dashboard. | — |
| `url` | `String` | Outbound link the story points at. Empty for self-posts. | — |
| `post_type` | `String` | ask_hn \| show_hn \| story ― the community's own category, from the title prefix. | `not_null`, `accepted_values` |
| `is_self` | `UInt8` | 1 = text post, 0 = link post. Splits the stacked bar on the content page. | — |
| `created_utc` | `DateTime` | Submission timestamp in UTC. Drives activity_date in the daily mart. | — |
| `ingested_at` | `DateTime` | Extraction timestamp of the snapshot that survived de-duplication, i.e. the newest one for this story. The singular test assert_staging_keeps_latest_snapshot asserts exactly that. | — |
| `ingest_date` | `Date` | Date part of ingested_at, carried through from the bronze partition key. | — |
| `created_hour` | `UInt8` | Hour of day (0-23, UTC) the story was posted. One axis of the heatmap. | `accepted_range` |
| `created_dow` | `UInt8` | Day of week (1 = Monday … 7 = Sunday). The other axis of the heatmap. | — |
| `story_text_length` | `UInt64` | Character count of the decoded body text. 0 for link posts. | — |
| `engagement_score` | `Int64` | score + num_comments ― simple engagement proxy. | — |

## `hackernews_marts.fct_stories` — gold — fact

Fact table ― one current row per HN story. Feeds the dashboard detail views.

**Grain:** 1 แถว = 1 story → `story_id`  
**Materialized:** `table`

| คอลัมน์ | ชนิด | คำอธิบาย | tests |
|---|---|---|---|
| `story_id` | `String` | Grain of the table ― one row per Hacker News story. | `not_null`, `unique` |
| `title` | `String` | Story headline, shown in the 'top stories' table. | — |
| `author` | `String` | Submitter's username. Joins to dim_authors. | — |
| `post_type` | `String` | ask_hn \| show_hn \| story ― the slice behind the content-mix chart. | `accepted_values` |
| `score` | `Int32` | Points at the latest snapshot. | `not_null` |
| `num_comments` | `Int32` | Comment count at the latest snapshot. | — |
| `engagement_score` | `Int64` | score + num_comments. | — |
| `story_text_length` | `UInt64` | Character count of the body text. 0 for link posts. | — |
| `is_self` | `UInt8` | 1 = text post, 0 = link post. | — |
| `created_utc` | `DateTime` | Submission timestamp in UTC. | — |
| `created_hour` | `UInt8` | Hour of day (0-23, UTC) ― heatmap axis. | — |
| `created_dow` | `UInt8` | Day of week (1 = Monday … 7 = Sunday) ― heatmap axis. | — |
| `permalink` | `String` | HN discussion URL ― the click-through target in the dashboard table. | — |
| `url` | `String` | Outbound link. Empty for self-posts. | — |
| `ingested_at` | `DateTime` | When the surviving snapshot was extracted. Useful for spotting stale rows. | — |

## `hackernews_marts.dim_authors` — gold — dimension

Author-level aggregates for the 'top contributors' view. Excludes [deleted].

**Grain:** 1 แถว = 1 author → `author`  
**Materialized:** `table`

| คอลัมน์ | ชนิด | คำอธิบาย | tests |
|---|---|---|---|
| `author` | `String` | Grain of the table ― one row per HN username. | `not_null`, `unique` |
| `total_stories` | `UInt64` | How many stories this author submitted in the loaded window. | `accepted_range` |
| `total_score` | `Int64` | Sum of points across all their stories. | — |
| `avg_score` | `Float64` | Mean points per story. Read alongside total_stories ― a single lucky post gives a high average that says little about the author. | — |
| `total_comments` | `Int64` | Sum of comments across all their stories. | — |
| `best_story_score` | `Int32` | Points on their highest-scoring story. | — |
| `first_seen` | `DateTime` | Submission time of their earliest story in the window. | — |
| `last_seen` | `DateTime` | Submission time of their most recent story in the window. | — |

## `hackernews_marts.agg_daily_activity` — gold — aggregate

Daily Hacker News activity ― primary time-series for Looker Studio. There is no average upvote ratio here: HN does not publish downvotes, so unlike the Reddit version of this project there is no ratio to average. Engagement quality is tracked with avg_score and avg_comments instead.
Caveat for the dashboard: the current day is still in progress, so its counts and averages are always low. Filter it out or label it.

**Grain:** 1 แถว = 1 วัน → `activity_date`  
**Materialized:** `table`

| คอลัมน์ | ชนิด | คำอธิบาย | tests |
|---|---|---|---|
| `activity_date` | `Date` | Grain of the table ― one row per UTC day, from created_utc. | `not_null` |
| `story_count` | `UInt64` | Stories submitted that day. | `accepted_range` |
| `total_score` | `Int64` | Sum of points across that day's stories. | — |
| `avg_score` | `Float64` | Mean points per story that day ― the engagement-quality line. | `accepted_range` |
| `total_comments` | `Int64` | Sum of comments across that day's stories. | — |
| `avg_comments` | `Float64` | Mean comments per story that day ― the second engagement-quality line. | `accepted_range` |
| `ask_hn_count` | `UInt64` | Stories titled 'Ask HN:' that day. | — |
| `show_hn_count` | `UInt64` | Stories titled 'Show HN:' that day. | — |
| `link_story_count` | `UInt64` | Everything that is neither Ask HN nor Show HN. | — |
| `self_posts` | `UInt64` | Stories with body text and no outbound link. | — |
| `link_posts` | `UInt64` | Stories pointing at an external URL. | — |

---

## ข้อมูลส่วนบุคคล (PII)

> ส่วนนี้เขียนด้วยมือ `scripts/generate_docs.py` จะต่อท้ายให้อัตโนมัติ

### เก็บอะไรที่ระบุตัวตนได้บ้าง

| ฟิลด์ | เป็น PII ไหม | เหตุผล |
|---|---|---|
| `author` | ⚠️ pseudonymous | เป็น **username สาธารณะ** ที่ผู้ใช้เลือกเอง ไม่ใช่ชื่อจริง แต่เป็น identifier ที่ตามรอยพฤติกรรมข้ามโพสต์ได้ |
| `title`, `story_text` | ⚠️ อาจมีได้ | เป็นข้อความอิสระ ผู้ใช้อาจเขียนชื่อหรืออีเมลตัวเองลงไปเอง (เช่นในโพสต์ "Ask HN: หางาน") |
| `permalink`, `url` | ไม่ | ลิงก์สาธารณะ |
| `score`, `num_comments`, `created_utc` | ไม่ | ตัวเลขและเวลาสาธารณะ |

### สิ่งที่ตั้งใจ **ไม่** เก็บ

ไม่ดึง `author_id` ภายในของ HN · ไม่ดึง comment ของผู้ใช้ · ไม่ทำ profile ข้ามแพลตฟอร์ม
และไม่พยายาม deanonymize username ให้กลายเป็นตัวตนจริง

### การจัดการ

- ข้อมูลทั้งหมดเป็น **ข้อมูลสาธารณะ** ที่ HN เผยแพร่ผ่าน Algolia API — ไม่มีการเข้าถึงข้อมูลที่ต้องล็อกอิน
- `dim_authors` ตัด `[deleted]` ออกแล้ว ซึ่งคือผู้ใช้ที่ลบบัญชีไป — **เคารพการตัดสินใจลบของเจ้าของบัญชี**
- ถ้าจะเอาไปใช้งานจริงควรเพิ่ม: retention policy (เช่น TTL บน partition เก่า) และขั้นตอนลบข้อมูลรายบุคคลเมื่อมีคำขอ
- ยังไม่มี access control ใน ClickHouse — ทุกคนใช้ user `default` รับได้สำหรับโปรเจกต์เรียนรู้ที่รันบนเครื่องตัวเอง แต่ **ห้ามใช้แบบนี้ใน production**

### ความลับในระบบ

ไฟล์ที่มีความลับถูก gitignore ทั้งหมด — `.env`, `.env.*`, `secrets/`
ตัวที่ต้องระวังที่สุดคือ **GCP service-account key** (`secrets/gcp-service-account.json`)
ซึ่งเปิด Google Sheet ของเจ้าของได้ ถ้าหลุดขึ้น GitHub ต้อง revoke key ทันที
