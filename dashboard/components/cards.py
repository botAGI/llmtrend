"""Reusable card components rendered via st.markdown with glassmorphism CSS."""

from __future__ import annotations

from typing import Any

import streamlit as st

from dashboard.components.charts import COLORS, format_number


# ------------------------------------------------------------------
# Metric card
# ------------------------------------------------------------------


def metric_card(
    label: str,
    value: str | int | float,
    delta: str | None = None,
    delta_color: str = "normal",
    icon: str = "",
) -> None:
    """Render a glassmorphism metric card.

    Args:
        label: Metric label text.
        value: Primary display value (will be converted to string).
        delta: Optional delta string (e.g. "+12.3%").
        delta_color: "normal" (green positive / red negative), "inverse", or "off".
        icon: Optional emoji/icon to prefix the label.
    """
    display_value = format_number(value) if isinstance(value, (int, float)) else str(value)

    delta_html = ""
    if delta is not None:
        is_positive = not str(delta).startswith("-")
        if delta_color == "normal":
            color = COLORS["positive"] if is_positive else COLORS["negative"]
        elif delta_color == "inverse":
            color = COLORS["negative"] if is_positive else COLORS["positive"]
        else:
            color = COLORS["neutral"]
        arrow = "\u25B2" if is_positive else "\u25BC"
        delta_html = f'<div class="metric-delta" style="color:{color}">{arrow} {delta}</div>'

    icon_html = f'<span class="metric-icon">{icon}</span> ' if icon else ""

    html = f"""
    <div class="glass-metric-card">
        <div class="metric-label">{icon_html}{label}</div>
        <div class="metric-value">{display_value}</div>
        {delta_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ------------------------------------------------------------------
# Signal card
# ------------------------------------------------------------------

_SEVERITY_STYLES: dict[str, dict[str, str]] = {
    "critical": {"color": "#FF4444", "bg": "rgba(255,68,68,0.08)", "border": "rgba(255,68,68,0.3)", "icon": "\U0001F534"},
    "high": {"color": "#FF8C42", "bg": "rgba(255,140,66,0.08)", "border": "rgba(255,140,66,0.3)", "icon": "\U0001F7E0"},
    "medium": {"color": "#FFD93D", "bg": "rgba(255,217,61,0.08)", "border": "rgba(255,217,61,0.3)", "icon": "\U0001F7E1"},
    "low": {"color": "#00FF88", "bg": "rgba(0,255,136,0.08)", "border": "rgba(0,255,136,0.3)", "icon": "\U0001F7E2"},
    "info": {"color": "#00D4FF", "bg": "rgba(0,212,255,0.08)", "border": "rgba(0,212,255,0.3)", "icon": "\U0001F535"},
}


def signal_card(signal: dict[str, Any]) -> None:
    """Render a signal notification card with severity-based styling."""
    severity = str(signal.get("severity", "info")).lower()
    style = _SEVERITY_STYLES.get(severity, _SEVERITY_STYLES["info"])

    signal_type = signal.get("signal_type", signal.get("type", ""))
    title = signal.get("title", signal.get("message", "Signal"))
    description = signal.get("description", signal.get("detail", ""))
    source = signal.get("source_type", signal.get("source", ""))
    created = signal.get("created_at", signal.get("detected_at", ""))

    meta_parts: list[str] = []
    if signal_type:
        meta_parts.append(f'<span class="signal-type">{signal_type}</span>')
    if source:
        meta_parts.append(f'<span class="signal-source">{source}</span>')
    if created:
        display_date = str(created)[:16].replace("T", " ")
        meta_parts.append(f'<span class="signal-date">{display_date}</span>')

    html = f"""
    <div class="signal-card" style="border-left: 3px solid {style['border']}; background: {style['bg']};">
        <div class="signal-header">
            <span class="signal-severity" style="color:{style['color']}">{style['icon']} {severity.upper()}</span>
            <span class="signal-title">{title}</span>
        </div>
        {"<div class='signal-description'>" + description + "</div>" if description else ""}
        <div class="signal-meta">{" &middot; ".join(meta_parts)}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ------------------------------------------------------------------
# Model card
# ------------------------------------------------------------------


def model_card(model: dict[str, Any]) -> None:
    """Render a horizontal model card with key metrics."""
    model_id = model.get("model_id", model.get("id", "unknown"))
    author = model.get("author", model_id.split("/")[0] if "/" in str(model_id) else "")
    pipeline_tag = model.get("pipeline_tag", "")
    downloads = model.get("downloads", model.get("total_downloads", 0))
    likes = model.get("likes", 0)
    growth = model.get("growth_percent", model.get("trending_score", None))

    growth_html = ""
    if growth is not None:
        color = COLORS["positive"] if float(growth) >= 0 else COLORS["negative"]
        arrow = "\u25B2" if float(growth) >= 0 else "\u25BC"
        growth_html = f'<span class="model-growth" style="color:{color}">{arrow} {growth:.1f}%</span>'

    tag_html = ""
    if pipeline_tag:
        tag_html = f'<span class="model-tag">{pipeline_tag}</span>'

    html = f"""
    <div class="model-card">
        <div class="model-card-header">
            <span class="model-name">{model_id}</span>
            {tag_html}
        </div>
        <div class="model-card-metrics">
            <span class="model-stat">\U0001F4E5 {format_number(downloads)}</span>
            <span class="model-stat">\u2764\uFE0F {format_number(likes)}</span>
            {growth_html}
            {"<span class='model-author'>" + author + "</span>" if author else ""}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ------------------------------------------------------------------
# Status badge
# ------------------------------------------------------------------


def status_badge(label: str, ok: bool) -> None:
    """Small status indicator badge (green dot / red dot)."""
    color = COLORS["positive"] if ok else COLORS["negative"]
    text = "Online" if ok else "Offline"
    html = f"""
    <div class="status-badge">
        <span class="status-dot" style="background:{color}"></span>
        <span class="status-label">{label}: {text}</span>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ------------------------------------------------------------------
# Section header
# ------------------------------------------------------------------


def section_header(title: str, subtitle: str = "") -> None:
    """Render a styled section header."""
    sub_html = f'<p class="section-subtitle">{subtitle}</p>' if subtitle else ""
    html = f"""
    <div class="section-header">
        <h2 class="section-title">{title}</h2>
        {sub_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
