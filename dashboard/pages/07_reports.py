"""Reports page -- Generate, view, and download AI trend reports."""

from __future__ import annotations

import pathlib

import streamlit as st

from dashboard.api_client import APIError, get_api
from dashboard.components import (
    format_number,
    metric_card,
    section_header,
)

# ------------------------------------------------------------------
# Page config
# ------------------------------------------------------------------

st.set_page_config(page_title="Reports | AI Trend Monitor", page_icon="\U0001F4CA", layout="wide")

_CSS_PATH = pathlib.Path(__file__).resolve().parent.parent / "static" / "style.css"
if _CSS_PATH.exists():
    st.markdown(f"<style>{_CSS_PATH.read_text()}</style>", unsafe_allow_html=True)

st.title("Reports")
st.caption("Generate and review AI trend analysis reports")

api = get_api()

# ------------------------------------------------------------------
# Report generation form
# ------------------------------------------------------------------

section_header("Generate Report", "Create a new trend analysis report using AI")

gen_col1, gen_col2, gen_col3 = st.columns([2, 2, 1])

with gen_col1:
    report_type = st.selectbox(
        "Report Type",
        options=["general", "niche", "trending", "signals", "weekly"],
        format_func=lambda x: {
            "general": "General Overview",
            "niche": "Niche Deep-Dive",
            "trending": "Trending Analysis",
            "signals": "Signal Summary",
            "weekly": "Weekly Digest",
        }.get(x, x.capitalize()),
        key="report_type",
    )

with gen_col2:
    # Niche selector (only relevant for niche reports)
    niche_id: int | None = None
    if report_type == "niche":
        try:
            niches = api.get_niches()
            niche_options = {n.get("name", "Unknown"): n.get("niche_id", n.get("id")) for n in niches}
        except APIError:
            niche_options = {}

        if niche_options:
            selected_niche_name = st.selectbox(
                "Select Niche",
                options=list(niche_options.keys()),
                key="report_niche",
            )
            niche_id = niche_options.get(selected_niche_name)
        else:
            st.info("No niches available. Run collection first.")
    else:
        st.markdown("")  # Spacing

with gen_col3:
    st.markdown("")  # Align button
    generate_clicked = st.button(
        "Generate Report",
        type="primary",
        key="generate_report_btn",
        use_container_width=True,
    )

if generate_clicked:
    with st.spinner("Generating report... This may take up to 2 minutes."):
        try:
            result = api.generate_report(report_type=report_type, niche_id=niche_id)
            st.success("Report generated successfully!")

            # Display the freshly generated report
            if result.get("content_markdown"):
                st.markdown("---")
                section_header(result.get("title", "Generated Report"))
                st.markdown(
                    f'<div class="report-content">{result["content_markdown"]}</div>',
                    unsafe_allow_html=True,
                )

                # Download button
                st.download_button(
                    label="Download Report (Markdown)",
                    data=result["content_markdown"],
                    file_name=f"report_{result.get('id', 'new')}_{report_type}.md",
                    mime="text/markdown",
                    key="download_new_report",
                )
        except APIError as exc:
            st.error(f"Failed to generate report: {exc.detail}")

st.markdown("")

# ------------------------------------------------------------------
# Report type filter
# ------------------------------------------------------------------

section_header("Previous Reports")

filter_col1, filter_col2 = st.columns([2, 1])

with filter_col1:
    filter_type = st.selectbox(
        "Filter by type",
        options=["All", "general", "niche", "trending", "signals", "weekly"],
        key="report_filter_type",
    )
    filter_type_param = None if filter_type == "All" else filter_type

with filter_col2:
    report_limit = st.selectbox(
        "Show last",
        options=[10, 20, 50],
        index=1,
        key="report_limit",
    )

# ------------------------------------------------------------------
# Fetch report list
# ------------------------------------------------------------------

try:
    reports_data = api.get_reports(report_type=filter_type_param, limit=report_limit)
    reports: list[dict] = reports_data.get("reports", [])
except APIError as exc:
    st.error(f"Failed to load reports: {exc.detail}")
    reports = []

if reports:
    st.markdown(f"Showing {len(reports)} reports")
    st.markdown("")

    for report in reports:
        report_id = report.get("id", "")
        title = report.get("title", f"Report #{report_id}")
        rtype = report.get("report_type", "general")
        created = str(report.get("created_at", ""))[:16].replace("T", " ")

        # Type badge color
        type_colors: dict[str, str] = {
            "general": "#00D4FF",
            "niche": "#00FF88",
            "trending": "#FFD93D",
            "signals": "#FF6B6B",
            "weekly": "#9B59B6",
        }
        badge_color = type_colors.get(rtype, "#8B95A5")

        with st.expander(f"{title}  |  {rtype.upper()}  |  {created}"):
            # Fetch full report
            try:
                detail = api.get_report_detail(report_id)
            except APIError as exc:
                st.warning(f"Could not load report detail: {exc.detail}")
                continue

            # Metadata
            meta_col1, meta_col2, meta_col3 = st.columns(3)
            with meta_col1:
                st.markdown(
                    f'<span style="background:{badge_color};color:#0E1117;'
                    f'padding:0.2rem 0.6rem;border-radius:4px;font-size:0.78rem;'
                    f'font-weight:600;">{rtype.upper()}</span>',
                    unsafe_allow_html=True,
                )
            with meta_col2:
                if created:
                    st.markdown(f"**Created:** {created}")
            with meta_col3:
                if detail.get("niche_name"):
                    st.markdown(f"**Niche:** {detail['niche_name']}")

            # Content
            content = detail.get("content_markdown", detail.get("content", ""))
            if content:
                st.markdown("---")
                st.markdown(
                    f'<div class="report-content">{content}</div>',
                    unsafe_allow_html=True,
                )

                # Download
                st.download_button(
                    label="Download Report (Markdown)",
                    data=content,
                    file_name=f"report_{report_id}_{rtype}.md",
                    mime="text/markdown",
                    key=f"download_report_{report_id}",
                )
            else:
                st.info("Report content is empty.")
else:
    st.info(
        "No reports found. Generate your first report using the form above."
    )
