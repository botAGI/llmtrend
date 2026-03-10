"""Research page -- Browse arXiv papers tracked via niches."""

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
    search_filter,
    section_header,
)

# ------------------------------------------------------------------
# Page config
# ------------------------------------------------------------------

st.set_page_config(page_title="Research | AI Trend Monitor", page_icon="\U0001F4D1", layout="wide")

_CSS_PATH = pathlib.Path(__file__).resolve().parent.parent / "static" / "style.css"
if _CSS_PATH.exists():
    st.markdown(f"<style>{_CSS_PATH.read_text()}</style>", unsafe_allow_html=True)

st.title("arXiv Research")
st.caption("Track research papers across AI niches")

api = get_api()

# ------------------------------------------------------------------
# Gather papers from all niches
# ------------------------------------------------------------------

try:
    niches: list[dict] = api.get_niches()
except APIError as exc:
    st.error(f"Failed to load niches: {exc.detail}")
    st.stop()

all_papers: list[dict] = []
papers_by_niche: dict[str, int] = {}

for niche in niches:
    niche_id = niche.get("niche_id", niche.get("id"))
    niche_name = niche.get("name", "Unknown")
    paper_count = niche.get("paper_count", 0)
    if paper_count > 0:
        papers_by_niche[niche_name] = paper_count

# Fetch detail only for niches that have papers (limit to avoid too many calls)
niches_with_papers = [n for n in niches if n.get("paper_count", 0) > 0]

with st.spinner("Loading research papers..."):
    for niche in niches_with_papers[:20]:  # cap to avoid excessive API calls
        niche_id = niche.get("niche_id", niche.get("id"))
        niche_name = niche.get("name", "Unknown")
        try:
            detail = api.get_niche_detail(niche_id)
            for paper in detail.get("papers", []):
                paper["_niche"] = niche_name
                all_papers.append(paper)
        except APIError:
            continue

# ------------------------------------------------------------------
# Summary metrics
# ------------------------------------------------------------------

section_header("Research Overview")

mc1, mc2, mc3 = st.columns(3)
with mc1:
    metric_card("Total Papers", len(all_papers), icon="\U0001F4D1")
with mc2:
    metric_card("Niches with Papers", len(papers_by_niche), icon="\U0001F3AF")
with mc3:
    categories: set[str] = set()
    for p in all_papers:
        cats = p.get("categories", p.get("category", ""))
        if isinstance(cats, list):
            categories.update(cats)
        elif isinstance(cats, str) and cats:
            categories.add(cats)
    metric_card("Unique Categories", len(categories), icon="\U0001F3F7\uFE0F")

st.markdown("")

# ------------------------------------------------------------------
# Papers by niche bar chart
# ------------------------------------------------------------------

if papers_by_niche:
    section_header("Papers by Niche", "Distribution of research papers across tracked niches")

    chart_data = [
        {"niche": name, "papers": count}
        for name, count in sorted(papers_by_niche.items(), key=lambda x: x[1], reverse=True)
    ][:25]

    fig = create_bar_chart(
        chart_data,
        x="niche",
        y="papers",
        title="Papers per Niche",
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------
# Papers by category donut
# ------------------------------------------------------------------

if categories:
    # Count papers per category
    cat_counts: dict[str, int] = {}
    for p in all_papers:
        cats = p.get("categories", p.get("category", ""))
        if isinstance(cats, list):
            for c in cats:
                cat_counts[c] = cat_counts.get(c, 0) + 1
        elif isinstance(cats, str) and cats:
            cat_counts[cats] = cat_counts.get(cats, 0) + 1

    if cat_counts:
        section_header("Papers by Category")
        cat_chart_data = [
            {"category": cat, "count": cnt}
            for cat, cnt in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
        ][:15]

        fig = create_donut_chart(
            cat_chart_data,
            names="category",
            values="count",
            title="Top Categories",
            height=400,
        )
        st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------
# Search & paper list
# ------------------------------------------------------------------

section_header("Recent Papers")

search_query = search_filter(placeholder="Search papers by title or author...", key="paper_search")

filtered_papers = all_papers
if search_query:
    q_lower = search_query.lower()
    filtered_papers = [
        p
        for p in all_papers
        if q_lower in str(p.get("title", "")).lower()
        or q_lower in str(p.get("authors", "")).lower()
        or q_lower in str(p.get("summary", "")).lower()
    ]

# Sort by date (most recent first)
filtered_papers.sort(
    key=lambda p: p.get("published", p.get("created_at", "")),
    reverse=True,
)

if filtered_papers:
    st.markdown(f"Showing {len(filtered_papers)} papers")
    st.markdown("")

    for paper in filtered_papers[:50]:
        title = paper.get("title", "Untitled")
        authors = paper.get("authors", "")
        if isinstance(authors, list):
            authors = ", ".join(authors[:5])
            if len(paper.get("authors", [])) > 5:
                authors += " et al."
        summary = paper.get("summary", paper.get("abstract", ""))
        published = str(paper.get("published", paper.get("created_at", "")))[:10]
        arxiv_id = paper.get("arxiv_id", paper.get("id", ""))
        niche_name = paper.get("_niche", "")
        url = paper.get("url", f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "")

        with st.expander(f"{title}  ({published})"):
            if authors:
                st.markdown(f"**Authors:** {authors}")
            if niche_name:
                st.markdown(f"**Niche:** `{niche_name}`")
            if published:
                st.markdown(f"**Published:** {published}")

            # Categories
            cats = paper.get("categories", paper.get("category", ""))
            if isinstance(cats, list) and cats:
                st.markdown("**Categories:** " + ", ".join(f"`{c}`" for c in cats))
            elif isinstance(cats, str) and cats:
                st.markdown(f"**Categories:** `{cats}`")

            if summary:
                st.markdown("**Abstract:**")
                st.markdown(
                    f'<div style="font-size:0.88rem;color:#8B95A5;line-height:1.6;">{summary[:1000]}</div>',
                    unsafe_allow_html=True,
                )

            if url:
                st.markdown(f"[View on arXiv]({url})")
else:
    st.info("No papers found matching the search criteria.")
