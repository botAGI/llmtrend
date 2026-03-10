"""Models page -- Search, filter, and explore HuggingFace models."""

from __future__ import annotations

import pathlib

import pandas as pd
import streamlit as st

from dashboard.api_client import APIError, get_api
from dashboard.components import (
    create_bar_chart,
    format_number,
    metric_card,
    model_card,
    pagination,
    pipeline_tag_filter,
    search_filter,
    section_header,
    sort_filter,
    order_filter,
)

# ------------------------------------------------------------------
# Page config
# ------------------------------------------------------------------

st.set_page_config(page_title="Models | AI Trend Monitor", page_icon="\U0001F916", layout="wide")

_CSS_PATH = pathlib.Path(__file__).resolve().parent.parent / "static" / "style.css"
if _CSS_PATH.exists():
    st.markdown(f"<style>{_CSS_PATH.read_text()}</style>", unsafe_allow_html=True)

st.title("HuggingFace Models")
st.caption("Browse and search tracked models from the HuggingFace Hub")

api = get_api()

# ------------------------------------------------------------------
# Filter bar
# ------------------------------------------------------------------

section_header("Filters")

fcol1, fcol2, fcol3, fcol4 = st.columns([3, 2, 2, 1])

with fcol1:
    search_query = search_filter(placeholder="Search models by name or author...", key="model_search")

with fcol2:
    # Provide common pipeline tags
    common_tags = [
        "text-generation",
        "text-classification",
        "token-classification",
        "question-answering",
        "summarization",
        "translation",
        "fill-mask",
        "image-classification",
        "object-detection",
        "text-to-image",
        "automatic-speech-recognition",
        "feature-extraction",
    ]
    selected_tag = pipeline_tag_filter(common_tags, key="model_pipeline")

with fcol3:
    sort_by = sort_filter(
        options=["downloads", "likes", "growth_percent", "created_at"],
        default="downloads",
        key="model_sort",
        label="Sort by",
    )

with fcol4:
    order = order_filter(key="model_order")

# Author filter (optional)
author_query = st.text_input(
    "Author filter",
    placeholder="Filter by author (optional)...",
    key="model_author",
    label_visibility="collapsed",
)

# ------------------------------------------------------------------
# Fetch models
# ------------------------------------------------------------------

# Determine current page
page_key = "models_page_current"
current_page = st.session_state.get(page_key, 1)
per_page = 20

try:
    result = api.get_models(
        search=search_query or None,
        pipeline_tag=selected_tag,
        author=author_query or None,
        sort_by=sort_by,
        order=order,
        page=current_page,
        per_page=per_page,
    )
except APIError as exc:
    st.error(f"Failed to load models: {exc.detail}")
    st.stop()

items: list[dict] = result.get("items", [])
total: int = result.get("total", 0)
total_pages: int = result.get("pages", 1)

# ------------------------------------------------------------------
# Results info + pagination
# ------------------------------------------------------------------

st.markdown("")
section_header("Results", f"{total:,} models found")

if items:
    # Data table
    df = pd.DataFrame(
        [
            {
                "Model ID": m.get("model_id", m.get("id", "")),
                "Author": m.get("author", ""),
                "Pipeline Tag": m.get("pipeline_tag", ""),
                "Downloads": m.get("downloads", m.get("total_downloads", 0)),
                "Likes": m.get("likes", 0),
                "Growth %": round(m.get("growth_percent", 0), 2),
            }
            for m in items
        ]
    )

    def _highlight_growth(val: float) -> str:
        if val >= 20:
            return "color: #00FF88"
        if val >= 5:
            return "color: #FFD93D"
        if val >= 0:
            return "color: #8B95A5"
        return "color: #FF4444"

    st.dataframe(
        df.style.applymap(_highlight_growth, subset=["Growth %"]),
        use_container_width=True,
        hide_index=True,
        height=min(len(df) * 38 + 40, 700),
    )

    # Pagination
    page, _ = pagination(total, per_page=per_page, key="models_page")
    if page != current_page:
        st.session_state[page_key] = page
        st.rerun()

    # ------------------------------------------------------------------
    # Model detail expanders
    # ------------------------------------------------------------------

    section_header("Model Details", "Expand to view full model information")

    for model in items:
        model_id = model.get("model_id", model.get("id", "unknown"))
        downloads = model.get("downloads", model.get("total_downloads", 0))
        likes = model.get("likes", 0)

        with st.expander(f"{model_id}  --  {format_number(downloads)} downloads"):
            try:
                detail = api.get_model_detail(model_id)
            except APIError:
                # Fall back to list-level data
                detail = model

            dcol1, dcol2, dcol3, dcol4 = st.columns(4)
            with dcol1:
                metric_card("Downloads", detail.get("downloads", detail.get("total_downloads", 0)), icon="\U0001F4E5")
            with dcol2:
                metric_card("Likes", detail.get("likes", 0), icon="\u2764\uFE0F")
            with dcol3:
                metric_card("Pipeline", detail.get("pipeline_tag", "N/A"), icon="\U0001F527")
            with dcol4:
                growth = detail.get("growth_percent", 0)
                delta_str = f"{growth:+.1f}%" if isinstance(growth, (int, float)) else None
                metric_card("Growth", f"{growth:.1f}%", delta=delta_str, icon="\U0001F4C8")

            # Additional fields
            if detail.get("author"):
                st.markdown(f"**Author:** `{detail['author']}`")
            if detail.get("tags"):
                tags = detail["tags"]
                if isinstance(tags, list):
                    st.markdown("**Tags:** " + ", ".join(f"`{t}`" for t in tags[:20]))
            if detail.get("library_name"):
                st.markdown(f"**Library:** `{detail['library_name']}`")
            if detail.get("created_at"):
                st.markdown(f"**Created:** {str(detail['created_at'])[:10]}")
            if detail.get("last_modified"):
                st.markdown(f"**Last Modified:** {str(detail['last_modified'])[:10]}")

else:
    st.info("No models found matching the current filters.")
