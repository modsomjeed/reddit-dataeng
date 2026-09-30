"""AI and the data engineering stack: a one-page dashboard for a DE lead (see docs/dashboard/story.md)."""

import os

import altair as alt
import clickhouse_connect
import pandas as pd
import streamlit as st

# Validated reference palette (light surface): categorical slots in fixed order,
# plus a neutral for de-emphasised marks.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
NEUTRAL = "#c3c2b7"
MUTED_INK = "#898781"
DEFAULT_TOOLS = ["AI (general)", "Spark", "Airflow", "dbt"]

st.set_page_config(page_title="AI and the DE stack", layout="wide")


@st.cache_resource
def client():
    return clickhouse_connect.get_client(
        host=os.environ.get("CLICKHOUSE_HOST", "localhost"),
        port=int(os.environ.get("CLICKHOUSE_HTTP_PORT", "8123")),
        username=os.environ["CLICKHOUSE_USER"],
        password=os.environ["CLICKHOUSE_PASSWORD"],
    )


@st.cache_data(ttl=3600)
def query(sql: str) -> pd.DataFrame:
    return client().query_df(sql)


# All the numbers are computed and tested in dbt; the dashboard only selects and draws them.
windows = query("select month, period from reddit_analytics.dim_comparison_windows order by month")
ai_monthly = query("""
    select month, measure, mentions_ai, total, share_pct
    from reddit_analytics.mart_ai_share_by_month
    order by month
""")
ai_change = query("select * from reddit_analytics.mart_ai_share_change").set_index("measure")
tool_changes = query("select * from reddit_analytics.mart_tool_share_change")
tool_changes["group"] = tool_changes["is_ai"].map({True: "AI tools", False: "Other tools"})
flair_windows = query("select * from reddit_analytics.mart_ai_share_by_flair_window")
# monthly per-tool series, for the compare-tools lines
tools = query("""
    select month, tool, posts_mentioning_in_title, title_share_pct
    from reddit_analytics.mart_tool_mentions_by_month
    order by month
""")
comment_tools = query("""
    select month, tool, comments_mentioning, share_pct
    from reddit_analytics.mart_comment_tool_mentions_by_month
    order by month
""")


def window_label(period: str) -> str:
    months = windows.loc[windows["period"] == period, "month"]
    return f"{pd.Timestamp(months.min()):%b %Y} – {pd.Timestamp(months.max()):%b %Y}"


first_label, last_label = window_label("first"), window_label("last")
titles, comments = ai_change.loc["Post titles"], ai_change.loc["Comments"]
title_tools = tool_changes[(tool_changes["measure"] == "Post titles") & ~tool_changes["is_ai"]]
biggest_other = title_tools.loc[title_tools["change_pts"].abs().idxmax()]
post_total = int(ai_monthly.loc[ai_monthly["measure"] == "Post titles", "total"].sum())
comment_total = int(ai_monthly.loc[ai_monthly["measure"] == "Comments", "total"].sum())

# Each measure: the monthly per-tool table, its mention and share columns, and axis labels.
MEASURES = {
    "Post titles": (tools, "posts_mentioning_in_title", "title_share_pct", "% of titles", "Posts"),
    "Comments": (comment_tools, "comments_mentioning", "share_pct", "% of comments", "Comments"),
}

# --- Header and headline numbers -------------------------------------------------

st.title("Is AI replacing the data engineering stack?")
st.caption(
    f"r/dataengineering, {post_total:,} posts and {comment_total:,} comments · "
    f"comparing {first_label} with {last_label}"
)

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric(
    "Posts that mention AI in the title",
    f"{titles['last_share_pct']:.1f}%",
    f"{titles['change_pts']:+.1f} pts vs {titles['first_share_pct']:.1f}%",
)
kpi2.metric(
    "Comments that mention AI",
    f"{comments['last_share_pct']:.1f}%",
    f"{comments['change_pts']:+.1f} pts vs {comments['first_share_pct']:.1f}%",
)
kpi3.metric(
    "Growth in AI conversation",
    f"×{comments['growth_ratio']:.1f}",
    f"×{titles['growth_ratio']:.1f} in titles",
    delta_color="off",
)
kpi4.metric(
    "Largest move of any non-AI tool",
    f"{biggest_other['change_pts']:+.1f} pts",
    biggest_other["tool"],
    delta_color="off",
)

st.markdown(
    "**Answer:** no. AI talk has grown and moved into everyday threads, but core tools are "
    "discussed about as much as before. Invest in AI on top of the existing stack, not instead of it."
)

# --- AI share trend --------------------------------------------------------------

st.subheader("AI share of the conversation, by month")
st.caption("Two independent measures agree: post titles and comment text")
hover = alt.selection_point(fields=["month"], nearest=True, on="pointerover", empty=False)
base = alt.Chart(ai_monthly).encode(
    x=alt.X("month:T", title=None, axis=alt.Axis(format="%b %Y", grid=False)),
    y=alt.Y("share_pct:Q", title="% mentioning AI", axis=alt.Axis(gridColor="#e1e0d9")),
    color=alt.Color("measure:N", scale=alt.Scale(domain=["Post titles", "Comments"], range=SERIES[:2]),
                    legend=alt.Legend(title=None, orient="bottom")),
)
trend = alt.layer(
    base.mark_line(strokeWidth=2),
    base.mark_point(size=80, opacity=0).add_params(hover),
    base.mark_point(size=64, filled=True).transform_filter(hover),
    base.mark_rule(color=MUTED_INK).encode(
        tooltip=[
            alt.Tooltip("month:T", title="Month", format="%b %Y"),
            alt.Tooltip("measure:N", title="Measure"),
            alt.Tooltip("share_pct:Q", title="AI share %", format=".1f"),
            alt.Tooltip("mentions_ai:Q", title="Mentioning AI"),
            alt.Tooltip("total:Q", title="All"),
        ]
    ).transform_filter(hover),
    # direct labels at the last point, so the two lines don't rely on colour alone
    base.mark_text(align="left", dx=6, fontSize=12).encode(
        text="measure:N", color=alt.value(MUTED_INK)
    ).transform_window(rank="rank()", sort=[alt.SortField("month", order="descending")], groupby=["measure"])
    .transform_filter("datum.rank == 1"),
).properties(height=280)
st.altair_chart(trend, use_container_width=True)

# --- Which tools moved -----------------------------------------------------------

measure = st.radio("Measure tool mentions in", list(MEASURES), horizontal=True)
df, hits, share_col, share_title, count_title = MEASURES[measure]
change = tool_changes[tool_changes["measure"] == measure]

left, right = st.columns(2)

with left:
    st.subheader(f"Change in share of {measure.lower()}, per tool")
    st.caption(f"{last_label} minus {first_label}, percentage points")
    bars = alt.Chart(change).mark_bar(cornerRadiusEnd=4, height=10).encode(
        x=alt.X("change_pts:Q", title="pts", axis=alt.Axis(gridColor="#e1e0d9")),
        # every tool gets a label; Vega-Lite would otherwise drop overlapping ones
        y=alt.Y("tool:N", sort="-x", title=None, axis=alt.Axis(labelOverlap=False, labelLimit=200)),
        color=alt.Color(
            "group:N",
            scale=alt.Scale(domain=["AI tools", "Other tools"], range=[SERIES[0], NEUTRAL]),
            legend=alt.Legend(title=None, orient="bottom"),
        ),
        tooltip=[
            alt.Tooltip("tool:N", title="Tool"),
            alt.Tooltip("first_share_pct:Q", title=f"{first_label} %", format=".1f"),
            alt.Tooltip("last_share_pct:Q", title=f"{last_label} %", format=".1f"),
            alt.Tooltip("change_pts:Q", title="Change (pts)", format="+.1f"),
        ],
    ).properties(height=35 * 22)
    st.altair_chart(bars, use_container_width=True)

with right:
    st.subheader("Where AI shows up")
    st.caption("Share of titles mentioning AI, per flair")
    main_flairs = ["Discussion", "Help", "Career", "Blog", "Personal Project Showcase", "Open Source"]
    periods = [first_label, last_label]
    dumbbell = flair_windows[flair_windows["flair"].isin(main_flairs)].assign(
        period=lambda d: d["period"].map({"first": first_label, "last": last_label})
    ).rename(columns={"ai_title_share_pct": "ai_share_pct"})
    order = dumbbell[dumbbell["period"] == periods[1]].sort_values("ai_share_pct", ascending=False)["flair"].tolist()
    y = alt.Y("flair:N", sort=order, title=None, axis=alt.Axis(labelLimit=200))
    dots = alt.layer(
        alt.Chart(dumbbell).mark_line(color=NEUTRAL, strokeWidth=2).encode(
            x="ai_share_pct:Q", y=y, detail="flair:N"
        ),
        alt.Chart(dumbbell).mark_point(size=110, filled=True, opacity=1).encode(
            x=alt.X("ai_share_pct:Q", title="% of titles", axis=alt.Axis(gridColor="#e1e0d9")),
            y=y,
            color=alt.Color(
                "period:N",
                scale=alt.Scale(domain=periods, range=[SERIES[1], SERIES[0]]),
                legend=alt.Legend(title=None, orient="bottom"),
            ),
            tooltip=[
                alt.Tooltip("flair:N", title="Flair"),
                alt.Tooltip("period:N", title="Period"),
                alt.Tooltip("ai_share_pct:Q", title="AI share %", format=".1f"),
            ],
        ),
    ).properties(height=300)
    st.altair_chart(dots, use_container_width=True)
    st.markdown(
        "AI was already common in showcase-type posts. The fastest growth is in **Help** and "
        "**Discussion**: people now ask and argue about AI in day-to-day work."
    )

# --- Compare tools over time -----------------------------------------------------

st.subheader(f"Compare tools over time ({measure.lower()})")
picked = st.multiselect(
    "Tools (up to 4)", sorted(tools["tool"].unique()), default=DEFAULT_TOOLS, max_selections=4
)
if picked:
    lines = df[df["tool"].isin(picked)]
    compare = alt.Chart(lines).mark_line(strokeWidth=2).encode(
        x=alt.X("month:T", title=None, axis=alt.Axis(format="%b %Y", grid=False)),
        y=alt.Y(f"{share_col}:Q", title=share_title, axis=alt.Axis(gridColor="#e1e0d9")),
        # colour follows the order tools were picked in, so the legend order matches the picker
        color=alt.Color("tool:N", scale=alt.Scale(domain=picked, range=SERIES[: len(picked)]),
                        legend=alt.Legend(title=None, orient="bottom")),
        tooltip=[
            alt.Tooltip("tool:N", title="Tool"),
            alt.Tooltip("month:T", title="Month", format="%b %Y"),
            alt.Tooltip(f"{share_col}:Q", title="Share %", format=".2f"),
            alt.Tooltip(f"{hits}:Q", title=count_title),
        ],
    ).properties(height=280)
    st.altair_chart(compare, use_container_width=True)

with st.expander("Data table"):
    st.dataframe(
        change.sort_values("change_pts", ascending=False)[
            ["tool", "category", "first_share_pct", "last_share_pct", "change_pts"]
        ].rename(columns={"first_share_pct": f"{first_label} %", "last_share_pct": f"{last_label} %",
                          "change_pts": "change (pts)"}),
        hide_index=True,
        use_container_width=True,
    )

# --- Caveats ---------------------------------------------------------------------

st.subheader("About the data")
st.markdown(
    "- Source: the Arctic Shift archive of r/dataengineering; scores and comment counts are as of the "
    "archive's re-check about 36 hours after posting.\n"
    "- Post shares count **titles only**. Removed posts lose their body text and the removal rate rises from "
    "about 11% to 95% over the period, so counting body text would make recent months look quieter than they are.\n"
    "- Comment shares count human comments that still have text (about 97% do); AutoModerator is left out. "
    "Comment volume falls after May 2026, when the subreddit started holding most posts for review.\n"
    "- Tools are matched by keyword (`seeds/tools.csv`). Spot checks found about 90% precision for ambiguous "
    "words like *agent*; known false matches such as *SQL Server Agent* are excluded.\n"
    "- A mention is not an endorsement: a post can mention a tool to criticise it."
)
