"""Dashboard configuration loaded from environment variables."""

import os

API_BASE_URL: str = os.getenv("STREAMLIT_API_BASE_URL", "http://api:8000")
REFRESH_INTERVAL: int = int(os.getenv("STREAMLIT_REFRESH_INTERVAL", "300"))
PAGE_TITLE: str = os.getenv("STREAMLIT_PAGE_TITLE", "AI Trend Monitor")
PAGE_ICON: str = os.getenv("STREAMLIT_PAGE_ICON", "\U0001F4C8")

# Chart theming
CHART_TEMPLATE: str = "plotly_dark"
CHART_BG: str = "rgba(0,0,0,0)"
CHART_PAPER_BG: str = "rgba(0,0,0,0)"
CHART_FONT_FAMILY: str = "Plus Jakarta Sans, sans-serif"
CHART_FONT_COLOR: str = "#C8D0DA"
CHART_GRID_COLOR: str = "rgba(200,208,218,0.08)"
