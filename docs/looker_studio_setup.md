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
Re-run the DAG. Tabs `agg_daily_subreddit`, `fct_posts`, `dim_authors` appear.

### 4. Build the dashboard
1. <https://lookerstudio.google.com> → Create → Data source → **Google Sheets**.
2. Pick your Sheet + the `agg_daily_subreddit` tab → Connect → Add to report.
3. Suggested charts (see below).

---

## Option B ― Direct ClickHouse via MySQL interface + tunnel (advanced)

ClickHouse speaks the MySQL wire protocol. You can expose it and use a
Looker Studio **MySQL** connector.

1. Enable the MySQL port in ClickHouse (`9004`) and publish it in compose.
2. Tunnel it publicly, e.g. `ngrok tcp 9004` (or Cloudflare Tunnel).
3. In Looker Studio add a **MySQL** data source pointing at the ngrok host/port,
   database `reddit`, and query a mart/view.

This is closer to "real" BI-on-warehouse but the free tunnel URL changes on each
restart, so Option A is more reliable for a submission.

---

## Suggested dashboard (Dashboard Design)

**Page 1 — Subreddit pulse** (source: `agg_daily_subreddit`)
- Scorecards: total posts, avg score, total comments (last 7 days).
- Time series: `post_count` and `total_comments` by `post_date`.
- Line: `avg_upvote_ratio` over time.
- Stacked bar: `text_posts` vs `link_posts` by day.

**Page 2 — Top content** (source: `fct_posts`)
- Table: top posts by `score` (title, author, score, num_comments, permalink).
- Bar: posts by `flair`.
- Heatmap / bar: posts by `created_hour` (best time to post).

**Page 3 — Contributors** (source: `dim_authors`)
- Table: top authors by `total_score` / `total_posts`.
- Scatter: `total_posts` vs `avg_score`.

Design tips: one accent colour, consistent number formatting, date-range control
on every page, and a short title + "data refreshed daily via Airflow" note.
