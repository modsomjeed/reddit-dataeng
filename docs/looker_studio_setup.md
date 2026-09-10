# Connecting Looker Studio (Google Data Studio)

Looker Studio runs in Google's cloud and **cannot reach a ClickHouse container
on your laptop**. Two ways to bridge that gap — Option A is recommended for a
bootcamp project.

---

## Option A ― Google Sheets bridge (recommended)

The `export_to_sheets` Airflow task pushes the (small, aggregated) marts into a
Google Sheet. Looker Studio connects to that Sheet natively.

### 1. Create a Google Cloud service account
1. Go to <https://console.cloud.google.com> → create/select a project.
2. Enable **Google Sheets API** and **Google Drive API**.
3. IAM & Admin → Service Accounts → create one → create a **JSON key**.
4. Save the JSON as `secrets/gcp-service-account.json` in this repo
   (it is gitignored — never commit it).

### 2. Create the target Sheet
1. Create a blank Google Sheet.
2. Copy its ID from the URL: `docs.google.com/spreadsheets/d/<THIS_IS_THE_ID>/edit`.
3. **Share** the Sheet with the service-account email (…@…iam.gserviceaccount.com)
   as **Editor**.

### 3. Configure `.env`
```
ENABLE_SHEETS_EXPORT=true
GSHEET_ID=<your_sheet_id>
GOOGLE_APPLICATION_CREDENTIALS=/opt/airflow/secrets/gcp-service-account.json
```
Re-run the DAG. Tabs `agg_daily_activity`, `fct_stories`, `dim_authors` appear.

### 4. Build the dashboard
1. <https://lookerstudio.google.com> → Create → Data source → **Google Sheets**.
2. Pick your Sheet + the `agg_daily_activity` tab → Connect → Add to report.
3. Suggested charts (see below).

---

## Option B ― Direct ClickHouse via MySQL interface + tunnel (advanced)

ClickHouse speaks the MySQL wire protocol. You can expose it and use a
Looker Studio **MySQL** connector.

1. Enable the MySQL port in ClickHouse (`9004`) and publish it in compose.
2. Tunnel it publicly, e.g. `ngrok tcp 9004` (or Cloudflare Tunnel).
3. In Looker Studio add a **MySQL** data source pointing at the ngrok host/port,
   database `hackernews_marts`, and query a mart/view.

This is closer to "real" BI-on-warehouse but the free tunnel URL changes on each
restart, so Option A is more reliable for a submission.

---

## Suggested dashboard (Dashboard Design)

Each page answers questions from [`questions.md`](./questions.md).

**Page 1 — HN pulse** (source: `agg_daily_activity`, questions 1–4)
- Scorecards: total stories, avg score, total comments (last 7 days).
- Time series: `story_count` and `total_comments` by `activity_date`.
- Line: `avg_score` and `avg_comments` over time — HN has no upvote ratio, so
  these two carry the engagement-quality question.
- Stacked bar: `ask_hn_count` / `show_hn_count` / `link_story_count` by day.

**Page 2 — Top content** (source: `fct_stories`, questions 4–6)
- Table: top stories by `score` (title, author, score, num_comments, permalink).
- Bar: stories by `post_type`.
- Heatmap: `created_hour` × `created_dow` (best time to post).

**Page 3 — Contributors** (source: `dim_authors`, question 6)
- Table: top authors by `total_score` / `total_stories`.
- Scatter: `total_stories` vs `avg_score`.

Design tips: one accent colour, consistent number formatting, date-range control
on every page, and a short title + "data refreshed daily via Airflow" note.
