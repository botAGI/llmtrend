"""GitHub page -- Search and browse tracked GitHub repositories."""

from __future__ import annotations

import pathlib

import pandas as pd
import streamlit as st

from dashboard.api_client import APIError, get_api
from dashboard.components import (
    create_bar_chart,
    format_number,
    language_filter,
    metric_card,
    pagination,
    search_filter,
    section_header,
    sort_filter,
)

# ------------------------------------------------------------------
# Page config
# ------------------------------------------------------------------

st.set_page_config(page_title="GitHub | AI Trend Monitor", page_icon="\U0001F4C2", layout="wide")

_CSS_PATH = pathlib.Path(__file__).resolve().parent.parent / "static" / "style.css"
if _CSS_PATH.exists():
    st.markdown(f"<style>{_CSS_PATH.read_text()}</style>", unsafe_allow_html=True)

st.title("GitHub Repositories")
st.caption("Explore trending open-source AI repositories")

api = get_api()

# ------------------------------------------------------------------
# Filter bar
# ------------------------------------------------------------------

section_header("Filters")

fcol1, fcol2, fcol3 = st.columns([4, 2, 2])

with fcol1:
    search_query = search_filter(placeholder="Search repos by name or description...", key="gh_search")

with fcol2:
    common_languages = [
        "Python",
        "Jupyter Notebook",
        "C++",
        "Rust",
        "JavaScript",
        "TypeScript",
        "Go",
        "Java",
        "Cuda",
        "Shell",
    ]
    selected_lang = language_filter(common_languages, key="gh_language")

with fcol3:
    sort_by = sort_filter(
        options=["stars", "forks", "updated_at", "created_at"],
        default="stars",
        key="gh_sort",
        label="Sort by",
    )

# ------------------------------------------------------------------
# Fetch repos
# ------------------------------------------------------------------

page_key = "gh_page_current"
current_page = st.session_state.get(page_key, 1)
per_page = 20

try:
    result = api.get_github_repos(
        search=search_query or None,
        language=selected_lang,
        sort_by=sort_by,
        page=current_page,
        per_page=per_page,
    )
except APIError as exc:
    st.error(f"Failed to load repositories: {exc.detail}")
    st.stop()

items: list[dict] = result.get("items", [])
total: int = result.get("total", 0)

# ------------------------------------------------------------------
# Summary metrics
# ------------------------------------------------------------------

st.markdown("")
mc1, mc2, mc3 = st.columns(3)
with mc1:
    metric_card("Repositories", total, icon="\U0001F4C2")
with mc2:
    total_stars = sum(r.get("stars", r.get("stargazers_count", 0)) for r in items)
    metric_card("Stars (page)", total_stars, icon="\u2B50")
with mc3:
    total_forks = sum(r.get("forks", r.get("forks_count", 0)) for r in items)
    metric_card("Forks (page)", total_forks, icon="\U0001F500")

st.markdown("")

# ------------------------------------------------------------------
# Results table
# ------------------------------------------------------------------

section_header("Results", f"{total:,} repositories found")

if items:
    df = pd.DataFrame(
        [
            {
                "Repository": r.get("full_name", r.get("name", "")),
                "Language": r.get("language", "N/A"),
                "Stars": r.get("stars", r.get("stargazers_count", 0)),
                "Forks": r.get("forks", r.get("forks_count", 0)),
                "Open Issues": r.get("open_issues", r.get("open_issues_count", 0)),
                "Updated": str(r.get("updated_at", ""))[:10],
            }
            for r in items
        ]
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=min(len(df) * 38 + 40, 700),
    )

    # Pagination
    page, _ = pagination(total, per_page=per_page, key="gh_page")
    if page != current_page:
        st.session_state[page_key] = page
        st.rerun()

    # ------------------------------------------------------------------
    # Repo detail expanders
    # ------------------------------------------------------------------

    section_header("Repository Details", "Expand for more information")

    for repo in items:
        repo_name = repo.get("full_name", repo.get("name", "unknown"))
        stars = repo.get("stars", repo.get("stargazers_count", 0))
        language = repo.get("language", "N/A")

        with st.expander(f"{repo_name}  --  {format_number(stars)} stars  [{language}]"):
            rcol1, rcol2, rcol3, rcol4 = st.columns(4)
            with rcol1:
                metric_card("Stars", stars, icon="\u2B50")
            with rcol2:
                metric_card("Forks", repo.get("forks", repo.get("forks_count", 0)), icon="\U0001F500")
            with rcol3:
                metric_card("Issues", repo.get("open_issues", repo.get("open_issues_count", 0)), icon="\U0001F41B")
            with rcol4:
                metric_card("Language", language, icon="\U0001F4BB")

            description = repo.get("description", "")
            if description:
                st.markdown(f"**Description:** {description}")

            if repo.get("topics"):
                topics = repo["topics"]
                if isinstance(topics, list):
                    st.markdown("**Topics:** " + ", ".join(f"`{t}`" for t in topics[:15]))

            if repo.get("created_at"):
                st.markdown(f"**Created:** {str(repo['created_at'])[:10]}")
            if repo.get("updated_at"):
                st.markdown(f"**Last Updated:** {str(repo['updated_at'])[:10]}")

            url = repo.get("html_url", repo.get("url", ""))
            if url:
                st.markdown(f"[View on GitHub]({url})")

    # ------------------------------------------------------------------
    # Stars distribution chart
    # ------------------------------------------------------------------

    chart_data = [
        {
            "repo": r.get("full_name", r.get("name", ""))[:30],
            "stars": r.get("stars", r.get("stargazers_count", 0)),
        }
        for r in items[:15]
    ]
    if chart_data:
        fig = create_bar_chart(
            chart_data,
            x="repo",
            y="stars",
            title="Stars Comparison (Current Page)",
            height=350,
        )
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("No repositories found matching the current filters.")
