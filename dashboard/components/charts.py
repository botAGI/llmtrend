"""Plotly chart builders with consistent dark theme styling."""

from __future__ import annotations

from typing import Any

import plotly.express as px
import plotly.graph_objects as go

from dashboard.config import (
    CHART_BG,
    CHART_FONT_COLOR,
    CHART_FONT_FAMILY,
    CHART_GRID_COLOR,
    CHART_PAPER_BG,
    CHART_TEMPLATE,
)

# ------------------------------------------------------------------
# Color palette
# ------------------------------------------------------------------

COLORS: dict[str, str] = {
    "primary": "#00D4FF",
    "positive": "#00FF88",
    "negative": "#FF4444",
    "warning": "#FFD93D",
    "neutral": "#8B95A5",
    "bg": "#0E1117",
    "card": "#1E2530",
    "text": "#C8D0DA",
}

COLOR_SEQUENCE: list[str] = [
    "#00D4FF",
    "#00FF88",
    "#FF6B6B",
    "#FFD93D",
    "#6BCB77",
    "#4D96FF",
    "#9B59B6",
    "#FF8C42",
    "#E056A0",
    "#45B7D1",
]


def apply_common_layout(fig: go.Figure, title: str = "", height: int | None = None) -> go.Figure:
    """Apply consistent dark-theme layout to any Plotly figure."""
    layout_kwargs: dict[str, Any] = {
        "template": CHART_TEMPLATE,
        "paper_bgcolor": CHART_PAPER_BG,
        "plot_bgcolor": CHART_BG,
        "font": dict(family=CHART_FONT_FAMILY, color=CHART_FONT_COLOR, size=13),
        "title": dict(
            text=title,
            font=dict(size=16, color="#FFFFFF", family=CHART_FONT_FAMILY),
            x=0,
            xanchor="left",
            yanchor="top",
        )
        if title
        else None,
        "margin": dict(l=40, r=20, t=50 if title else 20, b=40),
        "xaxis": dict(
            gridcolor=CHART_GRID_COLOR,
            zerolinecolor=CHART_GRID_COLOR,
            showgrid=True,
        ),
        "yaxis": dict(
            gridcolor=CHART_GRID_COLOR,
            zerolinecolor=CHART_GRID_COLOR,
            showgrid=True,
        ),
        "legend": dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color=CHART_FONT_COLOR),
        ),
        "hoverlabel": dict(
            bgcolor="#1E2530",
            font_size=12,
            font_family=CHART_FONT_FAMILY,
            bordercolor="#00D4FF",
        ),
    }
    if height:
        layout_kwargs["height"] = height

    fig.update_layout(**{k: v for k, v in layout_kwargs.items() if v is not None})
    return fig


# ------------------------------------------------------------------
# Chart builders
# ------------------------------------------------------------------


def create_area_chart(
    data: list[dict[str, Any]],
    x: str,
    y: str,
    color: str | None = None,
    title: str = "",
    height: int = 400,
) -> go.Figure:
    """Stacked area chart -- ideal for downloads over time by pipeline_tag."""
    if not data:
        return _empty_figure(title, height)

    fig = px.area(
        data,
        x=x,
        y=y,
        color=color,
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig.update_traces(line=dict(width=1.5), opacity=0.75)
    return apply_common_layout(fig, title=title, height=height)


def create_bar_chart(
    data: list[dict[str, Any]],
    x: str,
    y: str,
    title: str = "",
    color_field: str | None = None,
    orientation: str = "v",
    height: int = 400,
) -> go.Figure:
    """Bar chart with custom styling."""
    if not data:
        return _empty_figure(title, height)

    kwargs: dict[str, Any] = {
        "x": x,
        "y": y,
        "color_discrete_sequence": COLOR_SEQUENCE,
        "orientation": orientation,
    }
    if color_field:
        kwargs["color"] = color_field

    fig = px.bar(data, **kwargs)
    fig.update_traces(
        marker_line_width=0,
        opacity=0.9,
    )
    return apply_common_layout(fig, title=title, height=height)


def create_treemap(
    data: list[dict[str, Any]],
    names: str,
    values: str,
    title: str = "",
    color_field: str | None = None,
    height: int = 500,
) -> go.Figure:
    """Treemap for niche / category distribution."""
    if not data:
        return _empty_figure(title, height)

    kwargs: dict[str, Any] = {
        "names": names,
        "values": values,
        "color_discrete_sequence": COLOR_SEQUENCE,
    }
    if color_field:
        kwargs["color"] = color_field
        kwargs["color_continuous_scale"] = [
            [0, COLORS["negative"]],
            [0.5, COLORS["warning"]],
            [1, COLORS["positive"]],
        ]

    fig = px.treemap(data, **kwargs)
    fig.update_traces(
        textinfo="label+value+percent parent",
        textfont=dict(family=CHART_FONT_FAMILY, size=13),
        marker=dict(line=dict(width=1, color=COLORS["bg"])),
        hovertemplate="<b>%{label}</b><br>Downloads: %{value:,.0f}<br>Share: %{percentParent:.1%}<extra></extra>",
    )
    return apply_common_layout(fig, title=title, height=height)


def create_line_chart(
    data: list[dict[str, Any]],
    x: str,
    y: str,
    title: str = "",
    color: str | None = None,
    height: int = 400,
) -> go.Figure:
    """Simple line chart."""
    if not data:
        return _empty_figure(title, height)

    fig = px.line(
        data,
        x=x,
        y=y,
        color=color,
        color_discrete_sequence=COLOR_SEQUENCE,
        markers=True,
    )
    fig.update_traces(line=dict(width=2))
    return apply_common_layout(fig, title=title, height=height)


def create_heatmap(
    data: list[list[float]],
    x_labels: list[str],
    y_labels: list[str],
    title: str = "",
    height: int = 400,
) -> go.Figure:
    """Heatmap for research / trend matrices."""
    if not data:
        return _empty_figure(title, height)

    fig = go.Figure(
        data=go.Heatmap(
            z=data,
            x=x_labels,
            y=y_labels,
            colorscale=[
                [0, COLORS["bg"]],
                [0.5, "#1A3A5C"],
                [1, COLORS["primary"]],
            ],
            hoverongaps=False,
            hovertemplate="<b>%{y}</b> / %{x}<br>Value: %{z:.0f}<extra></extra>",
        )
    )
    return apply_common_layout(fig, title=title, height=height)


def create_donut_chart(
    data: list[dict[str, Any]],
    names: str,
    values: str,
    title: str = "",
    height: int = 350,
) -> go.Figure:
    """Donut / pie chart."""
    if not data:
        return _empty_figure(title, height)

    fig = px.pie(
        data,
        names=names,
        values=values,
        color_discrete_sequence=COLOR_SEQUENCE,
        hole=0.55,
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        textfont=dict(size=11, family=CHART_FONT_FAMILY),
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Share: %{percent}<extra></extra>",
        marker=dict(line=dict(color=COLORS["bg"], width=2)),
    )
    return apply_common_layout(fig, title=title, height=height)


def create_sparkline(
    values: list[float],
    positive: bool = True,
    width: int = 120,
    height: int = 40,
) -> go.Figure:
    """Tiny inline chart for metric cards. No axes, minimal chrome."""
    color = COLORS["positive"] if positive else COLORS["negative"]

    fig = go.Figure(
        go.Scatter(
            y=values,
            mode="lines",
            line=dict(color=color, width=2, shape="spline"),
            fill="tozeroy",
            fillcolor=f"rgba({_hex_to_rgb(color)}, 0.15)",
            hoverinfo="skip",
        )
    )
    fig.update_layout(
        template=CHART_TEMPLATE,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        width=width,
        height=height,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
    )
    return fig


def create_gauge(
    value: float,
    max_value: float = 100,
    title: str = "",
    suffix: str = "%",
    height: int = 200,
) -> go.Figure:
    """Gauge / indicator chart for single KPIs."""
    color = COLORS["positive"] if value >= 50 else COLORS["warning"] if value >= 25 else COLORS["negative"]

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number=dict(suffix=suffix, font=dict(size=28, color="#FFFFFF")),
            gauge=dict(
                axis=dict(range=[0, max_value], tickcolor=CHART_FONT_COLOR),
                bar=dict(color=color),
                bgcolor=COLORS["card"],
                borderwidth=0,
                steps=[
                    dict(range=[0, max_value * 0.25], color="rgba(255,68,68,0.15)"),
                    dict(range=[max_value * 0.25, max_value * 0.75], color="rgba(255,217,61,0.1)"),
                    dict(range=[max_value * 0.75, max_value], color="rgba(0,255,136,0.1)"),
                ],
            ),
            title=dict(text=title, font=dict(size=14, color=CHART_FONT_COLOR)),
        )
    )
    fig.update_layout(
        template=CHART_TEMPLATE,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=30, r=30, t=40, b=10),
        font=dict(family=CHART_FONT_FAMILY),
    )
    return fig


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _empty_figure(title: str, height: int = 300) -> go.Figure:
    """Return a placeholder figure when there is no data."""
    fig = go.Figure()
    fig.add_annotation(
        text="No data available",
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=16, color=COLORS["neutral"]),
    )
    return apply_common_layout(fig, title=title, height=height)


def _hex_to_rgb(hex_color: str) -> str:
    """Convert '#RRGGBB' to 'R, G, B' string for rgba()."""
    h = hex_color.lstrip("#")
    return ", ".join(str(int(h[i : i + 2], 16)) for i in (0, 2, 4))


def format_number(n: int | float) -> str:
    """Format large numbers for display (1234567 -> '1.23M')."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(int(n))
