"""Format backend data for Telegram messages (HTML parse_mode)."""

from __future__ import annotations

from html import escape
from typing import Any

# Telegram message length ceiling (the API hard limit is 4096 characters).
MAX_TELEGRAM_LENGTH = 4096

# Severity label prefixes used in signal lists.
SEVERITY_ICONS: dict[str, str] = {
    "critical": "!!",
    "high": "!",
    "medium": "*",
    "low": "-",
}


def truncate_for_telegram(text: str, max_length: int = MAX_TELEGRAM_LENGTH) -> str:
    """Truncate *text* so it fits within a single Telegram message.

    If the text exceeds *max_length* it is cut and a trailing
    ``[truncated]`` marker is appended.
    """
    if len(text) <= max_length:
        return text
    suffix = "\n\n<i>[truncated]</i>"
    return text[: max_length - len(suffix)] + suffix


# ------------------------------------------------------------------
# Overview / Quick
# ------------------------------------------------------------------


def format_overview(data: dict[str, Any]) -> str:
    """Format the /api/overview/ response for the /quick command."""
    stats: dict[str, Any] = data.get("stats", {})
    trending: list[dict[str, Any]] = data.get("trending", [])
    recent_signals: list[dict[str, Any]] = data.get("recent_signals", [])

    lines: list[str] = ["<b>AI Trend Monitor -- Quick Overview</b>", ""]

    # Stats block
    if stats:
        lines.append("<b>Stats</b>")
        lines.append(f"  Models tracked: <code>{stats.get('total_models', 'N/A')}</code>")
        lines.append(f"  Niches: <code>{stats.get('total_niches', 'N/A')}</code>")
        lines.append(f"  Signals today: <code>{stats.get('signals_today', 'N/A')}</code>")
        lines.append("")

    # Trending models
    if trending:
        lines.append("<b>Trending Models</b>")
        for idx, model in enumerate(trending[:5], start=1):
            name = escape(str(model.get("model_id", model.get("name", "unknown"))))
            growth = model.get("growth_percent", model.get("avg_growth_percent", 0))
            lines.append(f"  {idx}. <code>{name}</code>  +{_fmt_pct(growth)}")
        lines.append("")

    # Recent signals
    if recent_signals:
        lines.append("<b>Recent Signals</b>")
        for sig in recent_signals[:3]:
            severity = str(sig.get("severity", "low")).lower()
            icon = SEVERITY_ICONS.get(severity, "-")
            title = escape(str(sig.get("title", sig.get("signal_type", "signal"))))
            lines.append(f"  [{icon}] {title}")
        lines.append("")

    return truncate_for_telegram("\n".join(lines))


# ------------------------------------------------------------------
# Niches
# ------------------------------------------------------------------


def format_niche_table(niches: list[dict[str, Any]]) -> str:
    """Render a list of niches as a fixed-width table inside a <pre> block."""
    if not niches:
        return "<i>No niches found.</i>"

    header = f"{'#':<4}{'Niche':<24}{'Models':>7}{'Growth':>9}"
    sep = "-" * len(header)
    rows: list[str] = [header, sep]

    for idx, n in enumerate(niches, start=1):
        name = str(n.get("name", n.get("slug", "---")))[:22]
        models = n.get("model_count", 0)
        growth = n.get("avg_growth_percent", 0)
        rows.append(f"{idx:<4}{name:<24}{models:>7}{_fmt_pct(growth):>9}")

    table = "\n".join(rows)
    return truncate_for_telegram(f"<b>Niche Overview</b>\n\n<pre>{escape(table)}</pre>")


def format_niche_detail(niche: dict[str, Any]) -> str:
    """Render detailed info for a single niche."""
    lines: list[str] = []
    name = escape(str(niche.get("name", "Unknown")))
    lines.append(f"<b>Niche: {name}</b>")
    lines.append("")
    lines.append(f"Models: <code>{niche.get('model_count', 'N/A')}</code>")
    lines.append(f"Total downloads: <code>{_fmt_num(niche.get('total_downloads', 0))}</code>")
    lines.append(f"Avg growth: <code>{_fmt_pct(niche.get('avg_growth_percent', 0))}</code>")
    lines.append("")

    models = niche.get("models", [])
    if models:
        lines.append("<b>Top Models</b>")
        for m in models[:10]:
            mid = escape(str(m.get("model_id", m.get("name", "?"))))
            downloads = _fmt_num(m.get("downloads", 0))
            lines.append(f"  - <code>{mid}</code>  ({downloads} dl)")
        lines.append("")

    repos = niche.get("repos", [])
    if repos:
        lines.append("<b>Related Repos</b>")
        for r in repos[:5]:
            rname = escape(str(r.get("full_name", r.get("name", "?"))))
            stars = r.get("stars", 0)
            lines.append(f"  - <code>{rname}</code>  {stars} stars")

    return truncate_for_telegram("\n".join(lines))


# ------------------------------------------------------------------
# Models
# ------------------------------------------------------------------


def format_model_card(model: dict[str, Any]) -> str:
    """Render a single model detail card."""
    lines: list[str] = []
    model_id = escape(str(model.get("model_id", model.get("name", "Unknown"))))
    lines.append(f"<b>{model_id}</b>")
    lines.append("")

    pipeline = model.get("pipeline_tag", "")
    if pipeline:
        lines.append(f"Pipeline: <code>{escape(str(pipeline))}</code>")

    downloads = model.get("downloads", 0)
    lines.append(f"Downloads: <code>{_fmt_num(downloads)}</code>")

    likes = model.get("likes", 0)
    if likes:
        lines.append(f"Likes: <code>{_fmt_num(likes)}</code>")

    growth = model.get("growth_percent", model.get("avg_growth_percent"))
    if growth is not None:
        lines.append(f"Growth: <code>{_fmt_pct(growth)}</code>")

    tags = model.get("tags", [])
    if tags:
        tag_str = ", ".join(escape(str(t)) for t in tags[:8])
        lines.append(f"Tags: {tag_str}")

    last_modified = model.get("last_modified", model.get("updated_at"))
    if last_modified:
        lines.append(f"Updated: <code>{escape(str(last_modified)[:19])}</code>")

    return truncate_for_telegram("\n".join(lines))


def format_model_list(models: list[dict[str, Any]], title: str = "Models") -> str:
    """Format a list of models as a numbered list."""
    if not models:
        return "<i>No models found.</i>"

    lines: list[str] = [f"<b>{escape(title)}</b>", ""]
    for idx, m in enumerate(models, start=1):
        mid = escape(str(m.get("model_id", m.get("name", "?"))))
        downloads = _fmt_num(m.get("downloads", 0))
        growth = m.get("growth_percent", m.get("avg_growth_percent"))
        growth_str = f"  +{_fmt_pct(growth)}" if growth is not None else ""
        lines.append(f"{idx}. <code>{mid}</code>  ({downloads} dl){growth_str}")

    return truncate_for_telegram("\n".join(lines))


# ------------------------------------------------------------------
# Signals
# ------------------------------------------------------------------


def format_signal_list(signals: list[dict[str, Any]]) -> str:
    """Format signals with severity icons."""
    if not signals:
        return "<i>No signals found.</i>"

    lines: list[str] = ["<b>Signals</b>", ""]
    for sig in signals:
        severity = str(sig.get("severity", "low")).lower()
        icon = SEVERITY_ICONS.get(severity, "-")
        title = escape(str(sig.get("title", sig.get("signal_type", "signal"))))
        sig_type = sig.get("signal_type", "")
        created = str(sig.get("created_at", ""))[:16]
        line = f"[{icon}] <b>{title}</b>"
        if sig_type:
            line += f"  <i>({escape(str(sig_type))})</i>"
        if created:
            line += f"  {created}"
        lines.append(line)

        description = sig.get("description", "")
        if description:
            lines.append(f"    {escape(str(description)[:120])}")
        lines.append("")

    return truncate_for_telegram("\n".join(lines))


def format_signal_stats(stats: dict[str, Any]) -> str:
    """Format signal statistics."""
    lines: list[str] = ["<b>Signal Statistics</b>", ""]
    lines.append(f"Today: <code>{stats.get('today', 0)}</code>")
    lines.append(f"This week: <code>{stats.get('this_week', 0)}</code>")
    lines.append(f"This month: <code>{stats.get('this_month', 0)}</code>")
    lines.append("")

    by_severity = stats.get("by_severity", {})
    if by_severity:
        lines.append("<b>By Severity</b>")
        for sev in ("critical", "high", "medium", "low"):
            count = by_severity.get(sev, 0)
            if count:
                icon = SEVERITY_ICONS.get(sev, "-")
                lines.append(f"  [{icon}] {sev}: <code>{count}</code>")
        lines.append("")

    by_type = stats.get("by_type", {})
    if by_type:
        lines.append("<b>By Type</b>")
        for sig_type, count in by_type.items():
            lines.append(f"  {escape(str(sig_type))}: <code>{count}</code>")

    return truncate_for_telegram("\n".join(lines))


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------


def format_status(status: dict[str, Any]) -> str:
    """Format the system status response."""
    lines: list[str] = ["<b>System Status</b>", ""]

    for section_key in ("collections", "database", "ollama", "environment"):
        section = status.get(section_key)
        if section is None:
            continue
        lines.append(f"<b>{escape(section_key.title())}</b>")
        if isinstance(section, dict):
            for k, v in section.items():
                lines.append(f"  {escape(str(k))}: <code>{escape(str(v))}</code>")
        else:
            lines.append(f"  {escape(str(section))}")
        lines.append("")

    return truncate_for_telegram("\n".join(lines))


# ------------------------------------------------------------------
# Reports
# ------------------------------------------------------------------


def format_report_preview(report: dict[str, Any]) -> str:
    """Format a report for inline display (may be truncated)."""
    lines: list[str] = []
    title = escape(str(report.get("title", report.get("report_type", "Report"))))
    lines.append(f"<b>{title}</b>")
    created = str(report.get("created_at", ""))[:19]
    if created:
        lines.append(f"<i>Generated: {created}</i>")
    lines.append("")

    content = report.get("content_markdown", "")
    if content:
        # Show the markdown as plain text (escape HTML entities).
        lines.append(escape(str(content)))

    return truncate_for_telegram("\n".join(lines))


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _fmt_pct(value: Any) -> str:
    """Format a numeric value as a percentage string."""
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "N/A"


def _fmt_num(value: Any) -> str:
    """Format a number with thousands separators."""
    try:
        num = int(value)
        if num >= 1_000_000:
            return f"{num / 1_000_000:.1f}M"
        if num >= 1_000:
            return f"{num / 1_000:.1f}K"
        return str(num)
    except (TypeError, ValueError):
        return "N/A"
