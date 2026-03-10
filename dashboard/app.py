"""AI Trend Monitor -- Streamlit Dashboard entry point.

Run with:
    streamlit run dashboard/app.py
"""

from __future__ import annotations

import pathlib

import streamlit as st

from dashboard.config import PAGE_ICON, PAGE_TITLE

# ------------------------------------------------------------------
# Page configuration (must be the first Streamlit call)
# ------------------------------------------------------------------

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------
# Load custom CSS
# ------------------------------------------------------------------

_CSS_PATH = pathlib.Path(__file__).parent / "static" / "style.css"
if _CSS_PATH.exists():
    st.markdown(f"<style>{_CSS_PATH.read_text()}</style>", unsafe_allow_html=True)

# ------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------

with st.sidebar:
    st.title(PAGE_TITLE)
    st.markdown("---")

    st.markdown(
        """
        **Pages**
        - Overview
        - Niches
        - Models
        - Research
        - GitHub
        - Signals
        - Reports
        - Settings
        """,
    )

    st.markdown("---")

    # Auto-refresh toggle
    auto_refresh = st.toggle("Auto-refresh", value=False, key="auto_refresh")
    if auto_refresh:
        from dashboard.config import REFRESH_INTERVAL

        st.caption(f"Refreshing every {REFRESH_INTERVAL}s")
        st.markdown(
            f'<meta http-equiv="refresh" content="{REFRESH_INTERVAL}">',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div style="position:fixed;bottom:1rem;left:1rem;">'
        '<span style="font-size:0.72rem;color:#5A6370;">AI Trend Monitor v1.0</span>'
        "</div>",
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------------
# Landing page content
# ------------------------------------------------------------------

st.markdown(
    """
    <div style="text-align:center; padding:3rem 1rem;">
        <h1 style="font-size:2.4rem !important;
                    background:linear-gradient(135deg,#00D4FF,#00FF88);
                    -webkit-background-clip:text;
                    -webkit-text-fill-color:transparent;
                    background-clip:text;
                    margin-bottom:0.5rem;">
            AI Trend Monitor
        </h1>
        <p style="color:#8B95A5;font-size:1.1rem;max-width:600px;margin:0 auto 2rem;">
            Track emerging AI models, research papers, and open-source repositories.
            Detect trend signals early and generate analytical reports.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Quick-start cards
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(
        """
        <div class="glass-metric-card" style="text-align:center;">
            <div style="font-size:2rem;margin-bottom:0.3rem;">&#128202;</div>
            <div class="metric-label">Overview</div>
            <div style="font-size:0.82rem;color:#8B95A5;">Dashboard stats &amp; trending</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        """
        <div class="glass-metric-card" style="text-align:center;">
            <div style="font-size:2rem;margin-bottom:0.3rem;">&#129302;</div>
            <div class="metric-label">Models</div>
            <div style="font-size:0.82rem;color:#8B95A5;">HuggingFace model explorer</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        """
        <div class="glass-metric-card" style="text-align:center;">
            <div style="font-size:2rem;margin-bottom:0.3rem;">&#128221;</div>
            <div class="metric-label">Research</div>
            <div style="font-size:0.82rem;color:#8B95A5;">arXiv paper tracker</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col4:
    st.markdown(
        """
        <div class="glass-metric-card" style="text-align:center;">
            <div style="font-size:2rem;margin-bottom:0.3rem;">&#9889;</div>
            <div class="metric-label">Signals</div>
            <div style="font-size:0.82rem;color:#8B95A5;">Trend alerts &amp; anomalies</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.info("Use the sidebar to navigate between pages.", icon="\u2190")
