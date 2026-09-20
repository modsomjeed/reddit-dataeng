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

## Dashboard layout (Dashboard Design)

The reader, the message and the story arc are set in
[`storytelling.md`](./storytelling.md); this is that story laid out as pages.
Build it in this order — the pages are a sequence, not a menu.

**Reader:** a developer or founder about to post their own work to HN.
**Message:** the lever people argue about — posting time — is the weakest of
the three they control.

### Picking the chart type

The Data. Design. Decisions. deck (p. 35) sorts visuals into six jobs. Match
the question to its job first, then pick the chart — not the other way round.

| Question | Job | Chart |
|---|---|---|
| 1 — how busy is HN each day | change over time | line |
| 2 — is engagement quality shifting | change over time | two lines, one axis each page |
| 3 — link posts vs text posts | part-to-whole | stacked bar |
| 4 — which post type pulls people in | ranking | sorted bar |
| 5 — when do people post | distribution | heatmap, hour × weekday |
| 6 — who contributes most | ranking | sorted table |
| 7 — odds of clearing 50 points | magnitude | table, post type × 6-hour block |
| 8 — where to spend effort | ranking | sorted bar, one row per lever |

Nothing here needs a correlation chart. Question 8 sounds like one, but the
honest reading is a ranking of three measured effects — a scatter would imply
a relationship the data does not support.

### Page 1 — What actually happens

Source: `fct_stories`. Sets expectations before offering any advice.

- Scorecards: median score, share of stories with 0 comments, highest score.
  Lead with the **median**, not the mean — the mean is 19 and describes nobody.
- Bar: stories by score band (0–2, 3–9, 10–49, 50–99, 100+).
- Scorecard: share of all points held by the top 1% of stories.

### Page 2 — The three levers

Sources: `fct_stories`, `dim_authors`. Questions 7 and 8. The page the reader
came for.

- Bar, sorted: effect size per lever — how often you post (16×), what you post
  (2.7×), when you post (1.4×).
- Table: hit rate by `post_type` × 6-hour block. This is the predictive view;
  label it as a historical base rate, not a forecast for any one post.
- Table: author buckets by story count, showing points per story next to best
  post. Those two columns side by side are the whole argument — read alone,
  either one misleads.

### Page 3 — Pulse and drill-down

Sources: `agg_daily_activity`, `fct_stories`, `dim_authors`. Questions 1–6.
Where someone goes after they believe pages 1 and 2.

- Time series: `story_count` by `activity_date`.
- Two lines: `avg_score` and `avg_comments` over time.
- Stacked bar: `ask_hn_count` / `show_hn_count` / `link_story_count` by day.
- Table: top stories by `score` (title, author, score, comments, permalink).
- Table: top authors by `total_stories` and `avg_score`.

### Two things that will mislead if you skip them

**Filter out the current day.** It is still in progress, so its story count and
averages are always far below a finished day. Left in, every time series ends
in a cliff that reads as the site collapsing. Add a date-range control ending
yesterday, or label the last point.

**Do not make the hour × weekday heatmap the hero.** It is the prettiest chart
here and the least trustworthy: 168 cells over a few hundred posts each, and
the two halves of the window only correlate at 0.60 hour by hour. Show it as
texture for question 5, and keep every number someone might act on sourced
from the 6-hour blocks on page 2.

### Consistency

One accent colour, used only for "made it" — everything else neutral. Same
number formatting throughout, a date-range control on every page, and a note
saying the data refreshes daily via Airflow with the window it covers.
