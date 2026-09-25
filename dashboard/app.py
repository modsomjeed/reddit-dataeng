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
WINDOW_MONTHS = 6
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


tools = query("""
    select month, tool, category, posts_mentioning_in_title, posts_in_month, title_share_pct
    from reddit_analytics.mart_tool_mentions_by_month
    order by month
""")
flairs = query("""
    select month, flair, posts, ai_posts_in_title
    from reddit_analytics.mart_ai_share_by_flair_month
""")

# The first and last months of the data are partial, so compare complete months only.
months = sorted(tools["month"].unique())[1:-1]
first_window, last_window = months[:WINDOW_MONTHS], months[-WINDOW_MONTHS:]


def window_label(window) -> str:
    return f"{pd.Timestamp(window[0]):%b %Y} – {pd.Timestamp(window[-1]):%b %Y}"


def share_in(df: pd.DataFrame, window, by: str, hits: str, total: str) -> pd.Series:
    part = df[df["month"].isin(window)].groupby(by)[[hits, total]].sum()
    return part[hits] / part[total] * 100


# AI share of all posts per month: posts with any AI tool in the title
ai_monthly = flairs.groupby("month")[["ai_posts_in_title", "posts"]].sum().reset_index()
ai_monthly["ai_share_pct"] = ai_monthly["ai_posts_in_title"] / ai_monthly["posts"] * 100
ai_first = share_in(flairs.assign(all="all"), first_window, "all", "ai_posts_in_title", "posts").iloc[0]
ai_last = share_in(flairs.assign(all="all"), last_window, "all", "ai_posts_in_title", "posts").iloc[0]

change = pd.DataFrame({
    "first": share_in(tools, first_window, "tool", "posts_mentioning_in_title", "posts_in_month"),
    "last": share_in(tools, last_window, "tool", "posts_mentioning_in_title", "posts_in_month"),
})
change["change_pts"] = change["last"] - change["first"]
change = change.join(tools.drop_duplicates("tool").set_index("tool")["category"]).reset_index()
change["group"] = change["category"].map(lambda c: "AI tools" if c == "ai" else "Other tools")
other_tools = change[change["group"] == "Other tools"]
biggest_other = other_tools.loc[other_tools["change_pts"].abs().idxmax()]

# --- Header and headline numbers -------------------------------------------------

st.title("Is AI replacing the data engineering stack?")
st.caption(
    f"r/dataengineering, {int(flairs['posts'].sum()):,} posts · "
    f"comparing {window_label(first_window)} with {window_label(last_window)} · "
    "share of post titles that mention a tool"
)

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Posts that mention AI in the title", f"{ai_last:.1f}%", f"{ai_last - ai_first:+.1f} pts vs {ai_first:.1f}%")
kpi2.metric("Growth in AI conversation", f"×{ai_last / ai_first:.1f}")
kpi3.metric(
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

st.subheader("AI share of post titles, by month")
hover = alt.selection_point(fields=["month"], nearest=True, on="pointerover", empty=False)
base = alt.Chart(ai_monthly).encode(
    x=alt.X("month:T", title=None, axis=alt.Axis(format="%b %Y", grid=False)),
    y=alt.Y("ai_share_pct:Q", title="% of titles", axis=alt.Axis(gridColor="#e1e0d9")),
)
trend = alt.layer(
    base.mark_line(color=SERIES[0], strokeWidth=2),
    base.mark_point(size=80, opacity=0).add_params(hover),
    base.mark_point(size=64, filled=True, color=SERIES[0]).transform_filter(hover),
    base.mark_rule(color=MUTED_INK).encode(
        tooltip=[
            alt.Tooltip("month:T", title="Month", format="%b %Y"),
            alt.Tooltip("ai_share_pct:Q", title="AI share %", format=".1f"),
            alt.Tooltip("ai_posts_in_title:Q", title="AI posts"),
            alt.Tooltip("posts:Q", title="All posts"),
        ]
    ).transform_filter(hover),
).properties(height=280)
st.altair_chart(trend, use_container_width=True)

# --- Which tools moved -----------------------------------------------------------

left, right = st.columns(2)

with left:
    st.subheader("Change in share of titles, per tool")
    st.caption(f"{window_label(last_window)} minus {window_label(first_window)}, percentage points")
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
            alt.Tooltip("first:Q", title=f"{window_label(first_window)} %", format=".1f"),
            alt.Tooltip("last:Q", title=f"{window_label(last_window)} %", format=".1f"),
            alt.Tooltip("change_pts:Q", title="Change (pts)", format="+.1f"),
        ],
    ).properties(height=35 * 22)
    st.altair_chart(bars, use_container_width=True)

with right:
    st.subheader("Where AI shows up")
    st.caption("Share of titles mentioning AI, per flair")
    main_flairs = ["Discussion", "Help", "Career", "Blog", "Personal Project Showcase", "Open Source"]
    by_flair = flairs[flairs["flair"].isin(main_flairs)]
    dumbbell = pd.DataFrame({
        window_label(first_window): share_in(by_flair, first_window, "flair", "ai_posts_in_title", "posts"),
        window_label(last_window): share_in(by_flair, last_window, "flair", "ai_posts_in_title", "posts"),
    }).reset_index().melt("flair", var_name="period", value_name="ai_share_pct")
    periods = [window_label(first_window), window_label(last_window)]
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

st.subheader("Compare tools over time")
picked = st.multiselect(
    "Tools (up to 4)", sorted(tools["tool"].unique()), default=DEFAULT_TOOLS, max_selections=4
)
if picked:
    lines = tools[tools["tool"].isin(picked)]
    compare = alt.Chart(lines).mark_line(strokeWidth=2).encode(
        x=alt.X("month:T", title=None, axis=alt.Axis(format="%b %Y", grid=False)),
        y=alt.Y("title_share_pct:Q", title="% of titles", axis=alt.Axis(gridColor="#e1e0d9")),
        # colour follows the order tools were picked in, so the legend order matches the picker
        color=alt.Color("tool:N", scale=alt.Scale(domain=picked, range=SERIES[: len(picked)]),
                        legend=alt.Legend(title=None, orient="bottom")),
        tooltip=[
            alt.Tooltip("tool:N", title="Tool"),
            alt.Tooltip("month:T", title="Month", format="%b %Y"),
            alt.Tooltip("title_share_pct:Q", title="Share %", format=".2f"),
            alt.Tooltip("posts_mentioning_in_title:Q", title="Posts"),
        ],
    ).properties(height=280)
    st.altair_chart(compare, use_container_width=True)

with st.expander("Data table"):
    st.dataframe(
        change.sort_values("change_pts", ascending=False)
        .rename(columns={"first": f"{window_label(first_window)} %", "last": f"{window_label(last_window)} %",
                         "change_pts": "change (pts)"})
        .drop(columns="group"),
        hide_index=True,
        use_container_width=True,
    )

# --- Caveats ---------------------------------------------------------------------

st.subheader("About the data")
st.markdown(
    "- Source: the Arctic Shift archive of r/dataengineering; `score` and comment counts are as of capture time.\n"
    "- Shares count **titles only**. Removed posts lose their body text and the removal rate rises from about 11% "
    "to 95% over the period, so counting body text would make recent months look quieter than they are.\n"
    "- Tools are matched by keyword (`seeds/tools.csv`). Spot checks found about 90% precision for ambiguous "
    "words like *agent*; known false matches such as *SQL Server Agent* are excluded.\n"
    "- A mention is not an endorsement: a post can mention a tool to criticise it."
)
