"""Settings page -- System status, collection controls, and configuration."""

from __future__ import annotations

import pathlib

import streamlit as st

from dashboard.api_client import APIError, get_api
from dashboard.components import (
    format_number,
    metric_card,
    section_header,
    status_badge,
)

# ------------------------------------------------------------------
# Page config
# ------------------------------------------------------------------

st.set_page_config(page_title="Settings | AI Trend Monitor", page_icon="\u2699\uFE0F", layout="wide")

_CSS_PATH = pathlib.Path(__file__).resolve().parent.parent / "static" / "style.css"
if _CSS_PATH.exists():
    st.markdown(f"<style>{_CSS_PATH.read_text()}</style>", unsafe_allow_html=True)

st.title("Settings & Status")
st.caption("System health, data collection controls, and configuration")

api = get_api()

# ------------------------------------------------------------------
# Fetch system status
# ------------------------------------------------------------------

try:
    status = api.get_status()
except APIError as exc:
    st.error(f"Cannot reach backend API: {exc.detail}")
    st.stop()

# ------------------------------------------------------------------
# System Status Overview
# ------------------------------------------------------------------

section_header("System Status")

# Parse status sections
collections: dict = status.get("collections", {})
database: dict = status.get("database", {})
ollama: dict = status.get("ollama", {})
environment: dict = status.get("environment", {})

# Status badges row
badge_col1, badge_col2, badge_col3, badge_col4 = st.columns(4)

with badge_col1:
    # API is reachable if we got here
    status_badge("API Server", True)
with badge_col2:
    db_ok = database.get("connected", database.get("status") == "connected" if "status" in database else bool(database))
    status_badge("Database", db_ok)
with badge_col3:
    ollama_ok = ollama.get("available", ollama.get("status") == "available" if "status" in ollama else False)
    status_badge("Ollama LLM", ollama_ok)
with badge_col4:
    # Check if any environment tokens are configured
    env_ok = bool(environment)
    status_badge("Environment", env_ok)

st.markdown("")

# ------------------------------------------------------------------
# Detailed status cards (glassmorphism grid)
# ------------------------------------------------------------------

detail_col1, detail_col2 = st.columns(2)

# Database info
with detail_col1:
    section_header("Database Records")

    if database:
        # Try to display record counts from various possible structures
        record_items: list[tuple[str, str]] = []

        # Direct counts
        for key in ["models", "repos", "papers", "niches", "signals", "reports"]:
            val = database.get(key, database.get(f"total_{key}", database.get(f"{key}_count")))
            if val is not None:
                record_items.append((key.capitalize(), format_number(val)))

        # Nested "counts" or "tables" key
        counts = database.get("counts", database.get("tables", {}))
        if isinstance(counts, dict):
            for key, val in counts.items():
                if isinstance(val, (int, float)):
                    record_items.append((key.replace("_", " ").capitalize(), format_number(val)))

        if record_items:
            html_items = "".join(
                f'<div class="settings-item">'
                f'<span class="settings-key">{k}</span>'
                f'<span class="settings-value">{v}</span>'
                f"</div>"
                for k, v in record_items
            )
            st.markdown(
                f'<div class="settings-card"><h4>Record Counts</h4>{html_items}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="settings-card"><h4>Database</h4>'
                '<div class="settings-item">'
                '<span class="settings-key">Status</span>'
                f'<span class="settings-value">{"Connected" if db_ok else "Disconnected"}</span>'
                "</div></div>",
                unsafe_allow_html=True,
            )
    else:
        st.info("No database information available.")

# Ollama + environment
with detail_col2:
    # Ollama status
    section_header("Ollama LLM")

    ollama_items: list[tuple[str, str]] = []
    ollama_items.append(("Status", "Available" if ollama_ok else "Unavailable"))

    if ollama.get("model"):
        ollama_items.append(("Model", str(ollama["model"])))
    if ollama.get("url", ollama.get("base_url")):
        ollama_items.append(("URL", str(ollama.get("url", ollama.get("base_url", "")))))
    if ollama.get("version"):
        ollama_items.append(("Version", str(ollama["version"])))

    ollama_html = "".join(
        f'<div class="settings-item">'
        f'<span class="settings-key">{k}</span>'
        f'<span class="settings-value">{v}</span>'
        f"</div>"
        for k, v in ollama_items
    )
    st.markdown(
        f'<div class="settings-card"><h4>LLM Backend</h4>{ollama_html}</div>',
        unsafe_allow_html=True,
    )

    # API token status
    section_header("API Tokens")

    token_keys = ["huggingface_token", "github_token", "HUGGINGFACE_TOKEN", "GITHUB_TOKEN", "HF_TOKEN"]
    token_items: list[tuple[str, bool]] = []

    for key in token_keys:
        if key in environment:
            val = environment[key]
            # Could be True/False, or "configured"/"not_configured", or the masked token itself
            configured = bool(val) and str(val).lower() not in ("false", "not_configured", "none", "")
            display_key = key.replace("_", " ").title()
            token_items.append((display_key, configured))

    # Also check for generic structure
    if not token_items and isinstance(environment, dict):
        for key, val in environment.items():
            if "token" in key.lower() or "key" in key.lower() or "secret" in key.lower():
                configured = bool(val) and str(val).lower() not in ("false", "not_configured", "none", "")
                display_key = key.replace("_", " ").title()
                token_items.append((display_key, configured))

    if token_items:
        token_html = "".join(
            f'<div class="settings-item">'
            f'<span class="settings-key">{name}</span>'
            f'<span class="settings-value" style="color:{"#00FF88" if ok else "#FF4444"}">'
            f'{"Configured" if ok else "Not Configured"}</span>'
            f"</div>"
            for name, ok in token_items
        )
        st.markdown(
            f'<div class="settings-card"><h4>Token Status</h4>{token_html}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="settings-card"><h4>Token Status</h4>'
            '<div class="settings-item">'
            '<span class="settings-key">Info</span>'
            '<span class="settings-value">No token information available</span>'
            "</div></div>",
            unsafe_allow_html=True,
        )

# ------------------------------------------------------------------
# Collection Status
# ------------------------------------------------------------------

section_header("Last Collection")

if collections:
    coll_items: list[tuple[str, str]] = []
    for key, val in collections.items():
        if isinstance(val, dict):
            last_run = val.get("last_run", val.get("last_collected", "N/A"))
            status_text = val.get("status", "unknown")
            coll_items.append((key.capitalize(), f"{status_text} ({str(last_run)[:16]})"))
        elif isinstance(val, str):
            coll_items.append((key.replace("_", " ").capitalize(), val))

    if coll_items:
        coll_html = "".join(
            f'<div class="settings-item">'
            f'<span class="settings-key">{k}</span>'
            f'<span class="settings-value">{v}</span>'
            f"</div>"
            for k, v in coll_items
        )
        st.markdown(
            f'<div class="settings-card"><h4>Collection History</h4>{coll_html}</div>',
            unsafe_allow_html=True,
        )
else:
    st.info("No collection history available.")

st.markdown("")

# ------------------------------------------------------------------
# Collection Controls
# ------------------------------------------------------------------

section_header("Data Collection", "Trigger manual data collection from different sources")

btn_col1, btn_col2, btn_col3, btn_col4, btn_col5 = st.columns(5)

with btn_col1:
    if st.button("Collect All", type="primary", use_container_width=True, key="collect_all"):
        with st.spinner("Collecting from all sources..."):
            try:
                result = api.trigger_collection("all")
                st.success(f"Collection started. Task: {result.get('task_id', 'N/A')}")
            except APIError as exc:
                st.error(f"Failed: {exc.detail}")

with btn_col2:
    if st.button("HuggingFace", use_container_width=True, key="collect_hf"):
        with st.spinner("Collecting from HuggingFace..."):
            try:
                result = api.trigger_collection("huggingface")
                st.success(f"HuggingFace collection started. Task: {result.get('task_id', 'N/A')}")
            except APIError as exc:
                st.error(f"Failed: {exc.detail}")

with btn_col3:
    if st.button("GitHub", use_container_width=True, key="collect_github"):
        with st.spinner("Collecting from GitHub..."):
            try:
                result = api.trigger_collection("github")
                st.success(f"GitHub collection started. Task: {result.get('task_id', 'N/A')}")
            except APIError as exc:
                st.error(f"Failed: {exc.detail}")

with btn_col4:
    if st.button("arXiv", use_container_width=True, key="collect_arxiv"):
        with st.spinner("Collecting from arXiv..."):
            try:
                result = api.trigger_collection("arxiv")
                st.success(f"arXiv collection started. Task: {result.get('task_id', 'N/A')}")
            except APIError as exc:
                st.error(f"Failed: {exc.detail}")

with btn_col5:
    if st.button("Run Analytics", use_container_width=True, key="run_analytics"):
        with st.spinner("Running analytics pipeline..."):
            try:
                result = api.trigger_analytics()
                st.success(f"Analytics started. Task: {result.get('task_id', 'N/A')}")
            except APIError as exc:
                st.error(f"Failed: {exc.detail}")

st.markdown("")
st.markdown("---")

# ------------------------------------------------------------------
# Dashboard configuration info
# ------------------------------------------------------------------

section_header("Dashboard Configuration")

from dashboard.config import API_BASE_URL, REFRESH_INTERVAL, PAGE_TITLE

config_items: list[tuple[str, str]] = [
    ("API Base URL", API_BASE_URL),
    ("Refresh Interval", f"{REFRESH_INTERVAL}s"),
    ("Page Title", PAGE_TITLE),
]

config_html = "".join(
    f'<div class="settings-item">'
    f'<span class="settings-key">{k}</span>'
    f'<span class="settings-value">{v}</span>'
    f"</div>"
    for k, v in config_items
)
st.markdown(
    f'<div class="settings-card"><h4>Dashboard Config</h4>{config_html}</div>',
    unsafe_allow_html=True,
)

st.caption(
    "Configuration can be changed via environment variables: "
    "STREAMLIT_API_BASE_URL, STREAMLIT_REFRESH_INTERVAL, STREAMLIT_PAGE_TITLE"
)
