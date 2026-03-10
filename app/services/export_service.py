"""Data export service for the AI Trend Monitor.

Provides CSV, JSON, and HTML export capabilities for models, signals,
niches, and reports.  All methods return strings (not files) so that
callers can stream them via HTTP responses, write them to disk, or
attach them to messages.
"""

from __future__ import annotations

import csv
import html
import io
import json
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.niches import get_niche_summary
from app.models.hf_model import HFModel
from app.models.trend_signal import TrendSignal
from app.utils.helpers import format_number, format_percent

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ExportService:
    """Export data to various formats.

    All methods are static and receive an :class:`AsyncSession` so that
    callers control transactional scope.  Each method returns a plain
    string ready for serialisation.
    """

    # ------------------------------------------------------------------
    # CSV exports
    # ------------------------------------------------------------------

    @staticmethod
    async def export_models_csv(
        session: AsyncSession,
        filters: dict[str, Any] | None = None,
    ) -> str:
        """Export HuggingFace models to a CSV string.

        Args:
            session: An active async database session.
            filters: Optional filtering criteria.  Supported keys:

                * ``pipeline_tag`` (str) -- filter by pipeline tag.
                * ``author`` (str) -- filter by author.
                * ``min_downloads`` (int) -- minimum download count.

        Returns:
            A CSV-formatted string including header row.
        """
        log.info("export_service.models_csv.started", filters=filters)

        stmt = select(HFModel).order_by(HFModel.downloads.desc())

        if filters:
            if filters.get("pipeline_tag"):
                stmt = stmt.where(HFModel.pipeline_tag == filters["pipeline_tag"])
            if filters.get("author"):
                stmt = stmt.where(HFModel.author == filters["author"])
            if filters.get("min_downloads"):
                stmt = stmt.where(HFModel.downloads >= int(filters["min_downloads"]))

        result = await session.execute(stmt)
        models: list[HFModel] = list(result.scalars().all())

        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # Header
        writer.writerow([
            "model_id",
            "name",
            "author",
            "pipeline_tag",
            "library_name",
            "downloads",
            "downloads_previous",
            "downloads_growth_percent",
            "likes",
            "likes_previous",
            "likes_growth_percent",
            "trending_score",
            "first_seen_at",
            "last_seen_at",
        ])

        # Data rows
        for m in models:
            writer.writerow([
                m.model_id,
                m.name,
                m.author or "",
                m.pipeline_tag or "",
                m.library_name or "",
                m.downloads,
                m.downloads_previous,
                f"{m.downloads_growth_percent:.2f}" if m.downloads_growth_percent is not None else "",
                m.likes,
                m.likes_previous,
                f"{m.likes_growth_percent:.2f}" if m.likes_growth_percent is not None else "",
                f"{m.trending_score:.4f}" if m.trending_score is not None else "",
                m.first_seen_at.isoformat() if m.first_seen_at else "",
                m.last_seen_at.isoformat() if m.last_seen_at else "",
            ])

        csv_str = output.getvalue()
        log.info("export_service.models_csv.completed", row_count=len(models))
        return csv_str

    @staticmethod
    async def export_signals_csv(
        session: AsyncSession,
        filters: dict[str, Any] | None = None,
    ) -> str:
        """Export trend signals to a CSV string.

        Args:
            session: An active async database session.
            filters: Optional filtering criteria.  Supported keys:

                * ``signal_type`` (str) -- filter by signal type.
                * ``severity`` (str) -- filter by severity level.
                * ``source_type`` (str) -- filter by source type.
                * ``limit`` (int) -- maximum number of rows (default 1000).

        Returns:
            A CSV-formatted string including header row.
        """
        log.info("export_service.signals_csv.started", filters=filters)

        stmt = select(TrendSignal).order_by(TrendSignal.detected_at.desc())

        limit = 1000
        if filters:
            if filters.get("signal_type"):
                stmt = stmt.where(TrendSignal.signal_type == filters["signal_type"])
            if filters.get("severity"):
                stmt = stmt.where(TrendSignal.severity == filters["severity"])
            if filters.get("source_type"):
                stmt = stmt.where(TrendSignal.source_type == filters["source_type"])
            if filters.get("limit"):
                limit = int(filters["limit"])

        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        signals: list[TrendSignal] = list(result.scalars().all())

        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # Header
        writer.writerow([
            "id",
            "source_type",
            "source_identifier",
            "signal_type",
            "severity",
            "value",
            "delta",
            "delta_percent",
            "description",
            "detected_at",
            "is_read",
        ])

        # Data rows
        for s in signals:
            writer.writerow([
                s.id,
                s.source_type,
                s.source_identifier,
                s.signal_type,
                s.severity,
                f"{s.value:.2f}",
                f"{s.delta:.2f}" if s.delta is not None else "",
                f"{s.delta_percent:.2f}" if s.delta_percent is not None else "",
                s.description or "",
                s.detected_at.isoformat() if s.detected_at else "",
                s.is_read,
            ])

        csv_str = output.getvalue()
        log.info("export_service.signals_csv.completed", row_count=len(signals))
        return csv_str

    # ------------------------------------------------------------------
    # JSON exports
    # ------------------------------------------------------------------

    @staticmethod
    async def export_niches_json(session: AsyncSession) -> str:
        """Export niche summaries as a JSON string.

        Args:
            session: An active async database session.

        Returns:
            A pretty-printed JSON string containing an array of niche
            summary objects.
        """
        log.info("export_service.niches_json.started")

        summaries = await get_niche_summary(session)

        json_str = json.dumps(
            {"niches": summaries, "count": len(summaries)},
            indent=2,
            default=_json_serializer,
            ensure_ascii=False,
        )

        log.info("export_service.niches_json.completed", niche_count=len(summaries))
        return json_str

    # ------------------------------------------------------------------
    # HTML export
    # ------------------------------------------------------------------

    @staticmethod
    async def report_to_html(markdown_content: str) -> str:
        """Convert a markdown report to styled HTML.

        Uses a lightweight custom renderer that handles the subset of
        markdown used by report templates (headings, tables, lists, bold,
        horizontal rules).  A minimal CSS stylesheet is embedded for
        print-friendly rendering.

        Args:
            markdown_content: The raw markdown string.

        Returns:
            A self-contained HTML document string.
        """
        log.info("export_service.report_to_html.started")

        # Convert markdown to HTML body content.
        body_html = _markdown_to_html(markdown_content)

        document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Trend Monitor Report</title>
<style>
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                     'Helvetica Neue', Arial, sans-serif;
        line-height: 1.6;
        color: #333;
        max-width: 900px;
        margin: 0 auto;
        padding: 2rem;
        background: #fafafa;
    }}
    h1 {{
        color: #1a1a2e;
        border-bottom: 3px solid #4361ee;
        padding-bottom: 0.5rem;
        margin-top: 2rem;
    }}
    h2 {{
        color: #16213e;
        border-bottom: 1px solid #ddd;
        padding-bottom: 0.3rem;
        margin-top: 1.5rem;
    }}
    h3 {{ color: #0f3460; margin-top: 1.2rem; }}
    table {{
        border-collapse: collapse;
        width: 100%;
        margin: 1rem 0;
        background: #fff;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}
    th, td {{
        border: 1px solid #ddd;
        padding: 0.6rem 0.8rem;
        text-align: left;
    }}
    th {{
        background: #4361ee;
        color: #fff;
        font-weight: 600;
    }}
    tr:nth-child(even) {{ background: #f8f9fa; }}
    tr:hover {{ background: #e8ecf1; }}
    ul {{ padding-left: 1.5rem; }}
    li {{ margin-bottom: 0.4rem; }}
    strong {{ color: #1a1a2e; }}
    hr {{
        border: none;
        border-top: 2px solid #ddd;
        margin: 2rem 0;
    }}
    em {{ color: #666; }}
    code {{
        background: #f4f4f4;
        padding: 0.2rem 0.4rem;
        border-radius: 3px;
        font-size: 0.9em;
    }}
    .report-footer {{
        text-align: center;
        color: #999;
        font-size: 0.85em;
        margin-top: 3rem;
    }}
    @media print {{
        body {{ background: #fff; padding: 1rem; }}
        table {{ box-shadow: none; }}
    }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""

        log.info("export_service.report_to_html.completed")
        return document


# ======================================================================
# Private helpers
# ======================================================================


def _json_serializer(obj: Any) -> Any:
    """JSON serializer that handles datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _markdown_to_html(md: str) -> str:
    """Convert a limited markdown subset to HTML.

    Handles: ``#`` headings (h1--h6), markdown tables, unordered lists
    (``-``), bold (``**``), italic (``*``), horizontal rules (``---``),
    and paragraphs.  This is intentionally simple -- the reports use a
    controlled subset of markdown.
    """
    lines = md.split("\n")
    html_parts: list[str] = []
    in_table = False
    in_list = False
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Horizontal rule
        if stripped in ("---", "***", "___"):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            if in_table:
                html_parts.append("</tbody></table>")
                in_table = False
            html_parts.append("<hr>")
            i += 1
            continue

        # Empty line
        if not stripped:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            if in_table:
                html_parts.append("</tbody></table>")
                in_table = False
            i += 1
            continue

        # Headings
        if stripped.startswith("#"):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            if in_table:
                html_parts.append("</tbody></table>")
                in_table = False
            level = 0
            for ch in stripped:
                if ch == "#":
                    level += 1
                else:
                    break
            level = min(level, 6)
            heading_text = _inline_format(stripped[level:].strip())
            html_parts.append(f"<h{level}>{heading_text}</h{level}>")
            i += 1
            continue

        # Table row
        if "|" in stripped and stripped.startswith("|"):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]

            # Check if next line is separator row
            if not in_table:
                # Start new table -- this row is the header
                html_parts.append("<table>")
                html_parts.append("<thead><tr>")
                for cell in cells:
                    html_parts.append(f"<th>{_inline_format(cell)}</th>")
                html_parts.append("</tr></thead>")
                # Skip separator row if it exists
                if i + 1 < len(lines) and _is_table_separator(lines[i + 1].strip()):
                    i += 1
                html_parts.append("<tbody>")
                in_table = True
            elif _is_table_separator(stripped):
                # Separator row inside table -- skip
                pass
            else:
                # Data row
                html_parts.append("<tr>")
                for cell in cells:
                    html_parts.append(f"<td>{_inline_format(cell)}</td>")
                html_parts.append("</tr>")
            i += 1
            continue

        # Unordered list item
        if stripped.startswith("- ") or stripped.startswith("* "):
            if in_table:
                html_parts.append("</tbody></table>")
                in_table = False
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            item_text = _inline_format(stripped[2:])
            html_parts.append(f"<li>{item_text}</li>")
            i += 1
            continue

        # Paragraph
        if in_list:
            html_parts.append("</ul>")
            in_list = False
        if in_table:
            html_parts.append("</tbody></table>")
            in_table = False
        html_parts.append(f"<p>{_inline_format(stripped)}</p>")
        i += 1

    # Close any open containers.
    if in_list:
        html_parts.append("</ul>")
    if in_table:
        html_parts.append("</tbody></table>")

    return "\n".join(html_parts)


def _is_table_separator(line: str) -> bool:
    """Check if a line is a markdown table separator (e.g. ``|---|---|``)."""
    cleaned = line.replace("|", "").replace("-", "").replace(":", "").strip()
    return len(cleaned) == 0 and "-" in line


def _inline_format(text: str) -> str:
    """Apply inline markdown formatting (bold, italic) and escape HTML."""
    # Escape HTML entities first.
    result = html.escape(text)

    # Bold: **text**
    import re
    result = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", result)

    # Italic: *text*
    result = re.sub(r"\*(.+?)\*", r"<em>\1</em>", result)

    # Inline code: `text`
    result = re.sub(r"`(.+?)`", r"<code>\1</code>", result)

    return result
