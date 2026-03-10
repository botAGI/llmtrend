"""Niches page -- Browse, filter, and analyze AI niches."""

from __future__ import annotations

import pathlib

import pandas as pd
import streamlit as st

from dashboard.api_client import APIError, get_api
from dashboard.components import (
    create_bar_chart,
    create_treemap,
    format_number,
    metric_card,
    model_card,
    search_filter,
    section_header,
    signal_card,
    sort_filter,
)

# ------------------------------------------------------------------
# Page config
# ------------------------------------------------------------------

st.set_page_config(page_title="Niches | AI Trend Monitor", page_icon="\U0001F3AF", layout="wide")

_CSS_PATH = pathlib.Path(__file__).resolve().parent.parent / "static" / "style.css"
if _CSS_PATH.exists():
    st.markdown(f"<style>{_CSS_PATH.read_text()}</style>", unsafe_allow_html=True)

st.title("AI Niches")
st.caption("Explore and analyze emerging AI categories")

api = get_api()

# ------------------------------------------------------------------
# Fetch niches
# ------------------------------------------------------------------

try:
    niches: list[dict] = api.get_niches()
except APIError as exc:
    st.error(f"Failed to load niches: {exc.detail}")
    st.stop()

if not niches:
    st.info("No niches tracked yet. Head to Settings and run a collection.")
    st.stop()

# ------------------------------------------------------------------
# Filter bar
# ------------------------------------------------------------------

col_search, col_sort = st.columns([3, 1])
with col_search:
    query = search_filter(placeholder="Filter niches by name...", key="niche_search")
with col_sort:
    sort_option = sort_filter(
        options=["total_downloads", "avg_growth_percent", "model_count", "name"],
        default="total_downloads",
        key="niche_sort",
        label="Sort by",
    )

# Apply client-side filter & sort
filtered = niches
if query:
    q_lower = query.lower()
    filtered = [n for n in filtered if q_lower in n.get("name", "").lower()]

reverse = sort_option != "name"
filtered.sort(key=lambda n: n.get(sort_option, 0), reverse=reverse)

# ------------------------------------------------------------------
# Summary metrics
# ------------------------------------------------------------------

st.markdown("")
mc1, mc2, mc3, mc4 = st.columns(4)
with mc1:
    metric_card("Total Niches", len(niches), icon="\U0001F3AF")
with mc2:
    total_models = sum(n.get("model_count", 0) for n in niches)
    metric_card("Total Models", total_models, icon="\U0001F916")
with mc3:
    total_dl = sum(n.get("total_downloads", 0) for n in niches)
    metric_card("Total Downloads", total_dl, icon="\U0001F4E5")
with mc4:
    avg_growth = (
        sum(n.get("avg_growth_percent", 0) for n in niches) / len(niches) if niches else 0
    )
    metric_card("Avg Growth", f"{avg_growth:.1f}%", icon="\U0001F4C8")

st.markdown("")

# ------------------------------------------------------------------
# Data table
# ------------------------------------------------------------------

section_header("All Niches", f"Showing {len(filtered)} of {len(niches)}")


def _growth_color(val: float) -> str:
    if val >= 20:
        return "color: #00FF88"
    if val >= 5:
        return "color: #FFD93D"
    if val >= 0:
        return "color: #8B95A5"
    return "color: #FF4444"


if filtered:
    df = pd.DataFrame(
        [
            {
                "Name": n.get("name", ""),
                "Models": n.get("model_count", 0),
                "Repos": n.get("repo_count", 0),
                "Papers": n.get("paper_count", 0),
                "Downloads": n.get("total_downloads", 0),
                "Growth %": round(n.get("avg_growth_percent", 0), 2),
                "Top Model": n.get("top_model", "N/A"),
                "_niche_id": n.get("niche_id", n.get("id")),
            }
            for n in filtered
        ]
    )

    st.dataframe(
        df.drop(columns=["_niche_id"]).style.applymap(
            _growth_color, subset=["Growth %"]
        ),
        use_container_width=True,
        hide_index=True,
        height=min(len(df) * 38 + 40, 600),
    )

    # ------------------------------------------------------------------
    # Expandable niche detail
    # ------------------------------------------------------------------

    section_header("Niche Detail", "Expand a niche to see models, repos, papers, and signals")

    for niche in filtered:
        niche_id = niche.get("niche_id", niche.get("id"))
        niche_name = niche.get("name", "Unknown")
        growth = niche.get("avg_growth_percent", 0)
        growth_badge = f"+{growth:.1f}%" if growth >= 0 else f"{growth:.1f}%"

        with st.expander(f"{niche_name}  ({growth_badge} growth)"):
            # Fetch detail on demand
            try:
                detail = api.get_niche_detail(niche_id)
            except APIError as exc:
                st.warning(f"Could not load detail: {exc.detail}")
                continue

            # Description
            if detail.get("description"):
                st.markdown(detail["description"])

            # Sub-metrics
            d1, d2, d3, d4 = st.columns(4)
            with d1:
                metric_card("Models", len(detail.get("models", [])), icon="\U0001F916")
            with d2:
                metric_card("Repos", len(detail.get("repos", [])), icon="\U0001F4C2")
            with d3:
                metric_card("Papers", len(detail.get("papers", [])), icon="\U0001F4D1")
            with d4:
                metric_card("Signals", len(detail.get("signals", [])), icon="\u26A1")

            # Models bar chart
            models = detail.get("models", [])
            if models:
                chart_data = [
                    {
                        "model": m.get("model_id", m.get("id", ""))[:40],
                        "downloads": m.get("downloads", m.get("total_downloads", 0)),
                    }
                    for m in models[:15]
                ]
                fig = create_bar_chart(
                    chart_data,
                    x="model",
                    y="downloads",
                    title=f"Top Models in {niche_name}",
                    height=320,
                )
                st.plotly_chart(fig, use_container_width=True)

            # Signals
            signals = detail.get("signals", [])
            if signals:
                st.markdown("**Recent Signals**")
                for sig in signals[:5]:
                    signal_card(sig)

            # AI Analysis button
            st.markdown("---")
            if st.button(
                "Generate AI Analysis",
                key=f"analyze_{niche_id}",
                type="primary",
            ):
                with st.spinner("Analyzing niche with LLM..."):
                    try:
                        result = api.analyze_niche(niche_id)
                        if result.get("analysis"):
                            st.markdown(result["analysis"])
                        if not result.get("llm_available", True):
                            st.warning(
                                "LLM not available. Analysis may be limited."
                            )
                    except APIError as exc:
                        st.error(f"Analysis failed: {exc.detail}")
else:
    st.info("No niches match the current filter.")
