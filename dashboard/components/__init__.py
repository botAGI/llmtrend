"""Dashboard UI components -- re-export public API."""

from dashboard.components.cards import (
    metric_card,
    model_card,
    section_header,
    signal_card,
    status_badge,
)
from dashboard.components.charts import (
    COLOR_SEQUENCE,
    COLORS,
    apply_common_layout,
    create_area_chart,
    create_bar_chart,
    create_donut_chart,
    create_gauge,
    create_heatmap,
    create_line_chart,
    create_sparkline,
    create_treemap,
    format_number,
)
from dashboard.components.filters import (
    date_range_filter,
    language_filter,
    order_filter,
    pagination,
    per_page_selector,
    pipeline_tag_filter,
    search_filter,
    severity_filter,
    sort_filter,
)

__all__ = [
    # Cards
    "metric_card",
    "model_card",
    "signal_card",
    "section_header",
    "status_badge",
    # Charts
    "COLORS",
    "COLOR_SEQUENCE",
    "apply_common_layout",
    "create_area_chart",
    "create_bar_chart",
    "create_donut_chart",
    "create_gauge",
    "create_heatmap",
    "create_line_chart",
    "create_sparkline",
    "create_treemap",
    "format_number",
    # Filters
    "date_range_filter",
    "language_filter",
    "order_filter",
    "pagination",
    "per_page_selector",
    "pipeline_tag_filter",
    "search_filter",
    "severity_filter",
    "sort_filter",
]
