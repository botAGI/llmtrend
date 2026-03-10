"""Signals page -- View and filter trend signals and anomalies."""

from __future__ import annotations

import pathlib

import pandas as pd
import streamlit as st

from dashboard.api_client import APIError, get_api
from dashboard.components import (
    create_bar_chart,
    create_donut_chart,
    format_number,
    metric_card,
    pagination,
    section_header,
    severity_filter,
    signal_card,
    sort_filter,
)

# ------------------------------------------------------------------
# Page config
# ------------------------------------------------------------------

st.set_page_config(page_title="Signals | AI Trend Monitor", page_icon="\u26A1", layout="wide")

_CSS_PATH = pathlib.Path(__file__).resolve().parent.parent / "static" / "style.css"
if _CSS_PATH.exists():
    st.markdown(f"<style>{_CSS_PATH.read_text()}</style>", unsafe_allow_html=True)

st.title("Trend Signals")
st.caption("Anomalies, breakouts, and emerging trend alerts")

api = get_api()

# ------------------------------------------------------------------
# Signal stats
# ------------------------------------------------------------------

try:
    stats = api.get_signal_stats()
except APIError:
    stats = {}

section_header("Signal Stats")

sc1, sc2, sc3, sc4, sc5 = st.columns(5)

with sc1:
    metric_card(
        "Total Signals",
        stats.get("total", stats.get("total_signals", 0)),
        icon="\u26A1",
    )
with sc2:
    metric_card(
        "Critical",
        stats.get("critical", stats.get("by_severity", {}).get("critical", 0)),
        icon="\U0001F534",
    )
with sc3:
    metric_card(
        "High",
        stats.get("high", stats.get("by_severity", {}).get("high", 0)),
        icon="\U0001F7E0",
    )
with sc4:
    metric_card(
        "Medium",
        stats.get("medium", stats.get("by_severity", {}).get("medium", 0)),
        icon="\U0001F7E1",
    )
with sc5:
    metric_card(
        "Low / Info",
        stats.get("low", 0) + stats.get("info", 0),
        icon="\U0001F7E2",
    )

st.markdown("")

# ------------------------------------------------------------------
# Stats charts
# ------------------------------------------------------------------

chart_col1, chart_col2 = st.columns(2)

# Severity distribution donut
severity_data = stats.get("by_severity", {})
if not severity_data:
    # Try flat keys
    severity_data = {
        k: v for k, v in stats.items()
        if k in ("critical", "high", "medium", "low", "info") and isinstance(v, (int, float)) and v > 0
    }

if severity_data:
    with chart_col1:
        sev_chart = [
            {"severity": k.capitalize(), "count": v}
            for k, v in severity_data.items()
            if v > 0
        ]
        if sev_chart:
            fig = create_donut_chart(
                sev_chart,
                names="severity",
                values="count",
                title="Signals by Severity",
                height=320,
            )
            st.plotly_chart(fig, use_container_width=True)

# Type distribution bar
type_data = stats.get("by_type", stats.get("by_signal_type", {}))
if type_data:
    with chart_col2:
        type_chart = [
            {"type": k, "count": v}
            for k, v in sorted(type_data.items(), key=lambda x: x[1], reverse=True)
            if v > 0
        ]
        if type_chart:
            fig = create_bar_chart(
                type_chart,
                x="type",
                y="count",
                title="Signals by Type",
                height=320,
            )
            st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------
# Filters
# ------------------------------------------------------------------

section_header("Signal Feed")

fcol1, fcol2, fcol3 = st.columns([2, 2, 2])

with fcol1:
    selected_severity = severity_filter(key="signal_severity")

with fcol2:
    # Signal type filter
    signal_types = ["All", "growth_spike", "new_entry", "trending", "anomaly", "breakout", "decline"]
    selected_type = st.selectbox(
        "Signal Type",
        signal_types,
        key="signal_type_filter",
    )
    selected_type = None if selected_type == "All" else selected_type

with fcol3:
    source_types = ["All", "huggingface", "github", "arxiv"]
    selected_source = st.selectbox(
        "Source Type",
        source_types,
        key="signal_source_filter",
    )
    selected_source = None if selected_source == "All" else selected_source

# ------------------------------------------------------------------
# Fetch signals
# ------------------------------------------------------------------

sig_page_key = "signals_offset"
current_offset = st.session_state.get(sig_page_key, 0)
limit = 30

try:
    result = api.get_signals(
        severity=selected_severity,
        signal_type=selected_type,
        source_type=selected_source,
        limit=limit,
        offset=current_offset,
    )
except APIError as exc:
    st.error(f"Failed to load signals: {exc.detail}")
    st.stop()

signals: list[dict] = result.get("signals", [])
total_signals: int = result.get("total", 0)

st.markdown(f"Showing {len(signals)} of {total_signals:,} signals")
st.markdown("")

# ------------------------------------------------------------------
# Signal card feed
# ------------------------------------------------------------------

if signals:
    for sig in signals:
        signal_card(sig)

    # Pagination
    st.markdown("")
    pcol1, pcol2, pcol3 = st.columns([1, 2, 1])

    with pcol1:
        if st.button(
            "\u25C0 Previous",
            key="sig_prev",
            disabled=(current_offset <= 0),
        ):
            st.session_state[sig_page_key] = max(0, current_offset - limit)
            st.rerun()

    with pcol2:
        current_page_num = (current_offset // limit) + 1
        total_pages = max(1, (total_signals + limit - 1) // limit)
        st.markdown(
            f"<div style='text-align:center;padding-top:8px;color:#8B95A5;'>"
            f"Page {current_page_num} of {total_pages}</div>",
            unsafe_allow_html=True,
        )

    with pcol3:
        if st.button(
            "Next \u25B6",
            key="sig_next",
            disabled=(current_offset + limit >= total_signals),
        ):
            st.session_state[sig_page_key] = current_offset + limit
            st.rerun()
else:
    st.info("No signals found matching the current filters. Try running the analytics pipeline from Settings.")
