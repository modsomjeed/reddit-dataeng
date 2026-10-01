from datetime import date

import send_digest

DATA = {
    "windows": [
        {"month": "2024-10-01", "period": "first"},
        {"month": "2025-03-01", "period": "first"},
        {"month": "2026-03-01", "period": "last"},
        {"month": "2026-08-01", "period": "last"},
    ],
    "ai_change": [
        {"measure": "Comments", "first_share_pct": 4.55, "last_share_pct": 13.18,
         "change_pts": 8.63, "growth_ratio": 2.9},
        {"measure": "Post titles", "first_share_pct": 4.04, "last_share_pct": 11.71,
         "change_pts": 7.66, "growth_ratio": 2.9},
    ],
    "by_month": [
        {"month": "2026-07-01", "measure": "Post titles", "share_pct": 10.5},
        {"month": "2026-08-01", "measure": "Post titles", "share_pct": 10.93},
        {"month": "2026-09-01", "measure": "Post titles", "share_pct": 9.67},
        {"month": "2026-08-01", "measure": "Comments", "share_pct": 15.79},
        {"month": "2026-09-01", "measure": "Comments", "share_pct": 20.83},
    ],
    "tools": [
        {"tool": "AI (general)", "is_ai": True, "measure": "Post titles", "change_pts": 4.6},
        {"tool": "LLM", "is_ai": True, "measure": "Post titles", "change_pts": 1.3},
        {"tool": "Databricks", "is_ai": False, "measure": "Post titles", "change_pts": 0.9},
        {"tool": "DuckDB", "is_ai": False, "measure": "Post titles", "change_pts": 0.4},
        {"tool": "Airflow", "is_ai": False, "measure": "Post titles", "change_pts": -0.5},
        {"tool": "Snowflake", "is_ai": False, "measure": "Comments", "change_pts": -3.0},
    ],
}


def test_digest_compares_the_windows_and_the_latest_two_months():
    body = send_digest.build_digest(DATA, date(2026, 9, 28), "http://localhost:8501")

    assert "Mar 2026 – Aug 2026 vs Oct 2024 – Mar 2025" in body
    assert "Post titles  4.0% → 11.7%  (+7.7 pts, ×2.9)" in body
    assert "Latest months: Aug 2026, Sep 2026 (so far)" in body
    assert "Comments     15.8% → 20.8%" in body
    assert body.endswith("Dashboard: http://localhost:8501")


def test_digest_ranks_tools_by_post_titles_only():
    body = send_digest.build_digest(DATA, date(2026, 9, 28), "http://localhost:8501")
    rising, falling = body.split("Other tools rising most")[1].split("Other tools falling most")

    assert rising.index("Databricks") < rising.index("DuckDB")
    assert "Airflow          -0.5" in falling
    # Snowflake only moved in comments, so it is not in a post-title ranking
    assert "Snowflake" not in body


def test_month_label_marks_the_current_month():
    assert send_digest.month_label("2026-09-01", date(2026, 9, 28)) == "Sep 2026 (so far)"
    assert send_digest.month_label("2026-08-01", date(2026, 9, 28)) == "Aug 2026"
