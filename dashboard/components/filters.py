"""Reusable Streamlit filter / input widgets for dashboard pages."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import streamlit as st


def date_range_filter(key: str = "date") -> tuple[date, date]:
    """Render a date range picker and return (start, end)."""
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input(
            "From",
            value=date.today() - timedelta(days=30),
            key=f"{key}_start",
        )
    with col2:
        end = st.date_input(
            "To",
            value=date.today(),
            key=f"{key}_end",
        )
    return start, end


def pipeline_tag_filter(tags: list[str], key: str = "pipeline") -> str | None:
    """Render a selectbox for pipeline_tag filtering.

    Returns the selected tag, or None for 'All'.
    """
    options = ["All"] + sorted(tags)
    selected = st.selectbox("Pipeline Tag", options, key=key)
    return None if selected == "All" else selected


def search_filter(
    placeholder: str = "Search...",
    key: str = "search",
) -> str:
    """Render a text search input and return the query string."""
    return st.text_input(
        "Search",
        placeholder=placeholder,
        key=key,
        label_visibility="collapsed",
    )


def sort_filter(
    options: list[str],
    default: str = "",
    key: str = "sort",
    label: str = "Sort by",
) -> str:
    """Render a sort dropdown and return the selected option."""
    if default and default in options:
        index = options.index(default)
    else:
        index = 0
    return st.selectbox(label, options, index=index, key=key)


def order_filter(key: str = "order") -> str:
    """Render ascending/descending toggle. Returns 'asc' or 'desc'."""
    return st.selectbox(
        "Order",
        ["desc", "asc"],
        format_func=lambda x: "Descending" if x == "desc" else "Ascending",
        key=key,
    )


def pagination(
    total: int,
    per_page: int = 20,
    key: str = "page",
) -> tuple[int, int]:
    """Render pagination controls and return (page, per_page).

    Shows current page info and prev/next buttons.
    """
    total_pages = max(1, (total + per_page - 1) // per_page)
    current = st.session_state.get(f"{key}_current", 1)

    col_prev, col_info, col_next = st.columns([1, 2, 1])

    with col_prev:
        if st.button("\u25C0 Previous", key=f"{key}_prev", disabled=(current <= 1)):
            current = max(1, current - 1)
            st.session_state[f"{key}_current"] = current

    with col_info:
        st.markdown(
            f"<div style='text-align:center; padding-top:8px; color:#8B95A5;'>"
            f"Page {current} of {total_pages} &middot; {total:,} results</div>",
            unsafe_allow_html=True,
        )

    with col_next:
        if st.button("Next \u25B6", key=f"{key}_next", disabled=(current >= total_pages)):
            current = min(total_pages, current + 1)
            st.session_state[f"{key}_current"] = current

    return current, per_page


def severity_filter(key: str = "severity") -> str | None:
    """Dropdown for signal severity filtering."""
    options = ["All", "critical", "high", "medium", "low", "info"]
    selected = st.selectbox(
        "Severity",
        options,
        format_func=lambda x: x.capitalize(),
        key=key,
    )
    return None if selected == "All" else selected


def language_filter(languages: list[str], key: str = "language") -> str | None:
    """Dropdown for programming language filtering."""
    options = ["All"] + sorted(languages)
    selected = st.selectbox("Language", options, key=key)
    return None if selected == "All" else selected


def per_page_selector(
    options: list[int] | None = None,
    default: int = 20,
    key: str = "per_page",
) -> int:
    """Selector for items per page."""
    if options is None:
        options = [10, 20, 50, 100]
    return st.selectbox(
        "Per page",
        options,
        index=options.index(default) if default in options else 0,
        key=key,
    )
