"""Analytics layer for the AI Trend Monitor.

Re-exports the most commonly used functions and classes so that consumers can
import directly from ``app.analytics`` rather than reaching into sub-modules.
"""

from app.analytics.forecasting import (
    compute_moving_average,
    detect_trend_direction,
    forecast_trend,
)
from app.analytics.llm_analyzer import LLMAnalyzer
from app.analytics.niches import (
    assign_models_to_niches,
    ensure_default_niches,
    get_niche_detail,
    get_niche_summary,
)
from app.analytics.signals import (
    generate_signals,
    get_recent_signals,
    get_signal_stats,
)
from app.analytics.trends import (
    compute_growth_rates,
    get_download_timeline,
    get_overview_stats,
    get_top_trending,
)

__all__: list[str] = [
    # trends
    "compute_growth_rates",
    "get_top_trending",
    "get_download_timeline",
    "get_overview_stats",
    # signals
    "generate_signals",
    "get_recent_signals",
    "get_signal_stats",
    # niches
    "ensure_default_niches",
    "assign_models_to_niches",
    "get_niche_summary",
    "get_niche_detail",
    # forecasting
    "forecast_trend",
    "compute_moving_average",
    "detect_trend_direction",
    # llm
    "LLMAnalyzer",
]
