"""Overview page -- Dashboard home with KPI metrics, trending models, and signals."""

from __future__ import annotations

import pathlib

import streamlit as st

from dashboard.api_client import APIError, get_api
from dashboard.components import (
    create_treemap,
    format_number,
    metric_card,
    model_card,
    section_header,
    signal_card,
    create_area_chart,
)

# ------------------------------------------------------------------
# Page config
# ------------------------------------------------------------------

st.set_page_config(page_title="Overview | AI Trend Monitor", page_icon="\U0001F4C8", layout="wide")

_CSS_PATH = pathlib.Path(__file__).resolve().parent.parent / "static" / "style.css"
if _CSS_PATH.exists():
    st.markdown(f"<style>{_CSS_PATH.read_text()}</style>", unsafe_allow_html=True)

st.title("Overview")
st.caption("Real-time snapshot of the AI landscape")

api = get_api()

# ------------------------------------------------------------------
# Fetch data
# ------------------------------------------------------------------

try:
    overview = api.get_overview()
except APIError as exc:
    st.error(f"Failed to load overview data: {exc.detail}")
    st.stop()

stats: dict = overview.get("stats", {})
trending: list[dict] = overview.get("trending", [])
recent_signals: list[dict] = overview.get("recent_signals", [])

# ------------------------------------------------------------------
# KPI metric cards (6 columns)
# ------------------------------------------------------------------

section_header("Key Metrics")

c1, c2, c3, c4, c5, c6 = st.columns(6)

with c1:
    metric_card("Total Models", stats.get("total_models", 0), icon="\U0001F916")
with c2:
    metric_card(
        "Total Downloads",
        stats.get("total_downloads", 0),
        icon="\U0001F4E5",
    )
with c3:
    metric_card("Active Niches", stats.get("total_niches", 0), icon="\U0001F3AF")
with c4:
    metric_card(
        "Active Signals",
        stats.get("active_signals", 0),
        icon="\u26A1",
    )
with c5:
    metric_card("Total Repos", stats.get("total_repos", 0), icon="\U0001F4C2")
with c6:
    metric_card("Total Papers", stats.get("total_papers", 0), icon="\U0001F4D1")

st.markdown("")

# ------------------------------------------------------------------
# Hot Right Now -- trending models
# ------------------------------------------------------------------

section_header("Hot Right Now", "Fastest-growing models in the last collection cycle")

if trending:
    cols = st.columns(min(len(trending), 5))
    for idx, model in enumerate(trending[:5]):
        with cols[idx]:
            model_card(model)
else:
    st.info("No trending models found yet. Run a collection first.")

st.markdown("")

# ------------------------------------------------------------------
# Niche treemap
# ------------------------------------------------------------------

section_header("Niche Landscape", "Download distribution across tracked AI niches")

try:
    niches = api.get_niches()
except APIError:
    niches = []

if niches:
    treemap_data = [
        {
            "name": n.get("name", "Unknown"),
            "total_downloads": n.get("total_downloads", 0),
            "growth": n.get("avg_growth_percent", 0),
        }
        for n in niches
        if n.get("total_downloads", 0) > 0
    ]
    if treemap_data:
        fig = create_treemap(
            treemap_data,
            names="name",
            values="total_downloads",
            title="Niches by Total Downloads",
            color_field="growth",
            height=480,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No niche download data available yet.")
else:
    st.info("No niches tracked. Go to Settings to trigger a collection.")

# ------------------------------------------------------------------
# Downloads timeline
# ------------------------------------------------------------------

section_header("Download Timeline", "Historical downloads by pipeline tag")

try:
    timeline_data = api.get_timeline()
    timeline_items: list[dict] = timeline_data.get("timeline", [])
except APIError:
    timeline_items = []

if timeline_items:
    fig = create_area_chart(
        timeline_items,
        x="pipeline_tag",
        y="total_downloads",
        title="Downloads by Pipeline Tag",
        height=380,
    )
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------
# Recent signals feed
# ------------------------------------------------------------------

section_header("Recent Signals", "Latest trend alerts and anomalies")

if recent_signals:
    for sig in recent_signals[:10]:
        signal_card(sig)
else:
    st.info("No signals detected yet. Run the analytics pipeline to generate signals.")
