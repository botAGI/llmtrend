"""Report generation service for the AI Trend Monitor.

Produces daily, weekly, and niche-specific markdown reports by aggregating
analytics data and (optionally) enriching them with LLM-generated insights
via :class:`LLMAnalyzer`.  Reports are persisted both as database rows
(:class:`Report`) and as ``.md`` files on disk.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiofiles
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.llm_analyzer import LLMAnalyzer
from app.analytics.niches import get_niche_detail, get_niche_summary
from app.analytics.signals import get_recent_signals
from app.analytics.trends import compute_growth_rates, get_overview_stats, get_top_trending
from app.config import get_settings
from app.models.report import Report
from app.utils.helpers import format_number, format_percent, utc_now

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ReportGenerator:
    """Generates markdown reports from analytics data.

    All methods are static and receive an :class:`AsyncSession` so that
    callers control transactional scope.  Generated reports are both
    committed as :class:`Report` rows and written to the configured
    ``REPORTS_OUTPUT_DIR``.
    """

    # ------------------------------------------------------------------
    # Daily report
    # ------------------------------------------------------------------

    @staticmethod
    async def generate_daily_report(session: AsyncSession) -> Report:
        """Generate a daily summary report.

        Gathers overview stats, top-5 trending items, the 10 most recent
        signals, and niche summaries.  When Ollama is available the
        executive summary is AI-generated; otherwise a template is used.

        Args:
            session: An active async database session.

        Returns:
            The persisted :class:`Report` instance.
        """
        log.info("report_generator.daily.started")
        start_time = time.monotonic()
        now = utc_now()

        # -- Gather data ---------------------------------------------------
        stats = await get_overview_stats(session)
        trending = await get_top_trending(session, limit=5)
        signals = await get_recent_signals(session, limit=10)
        niches = await get_niche_summary(session)

        # -- AI executive summary ------------------------------------------
        ai_summary = ""
        settings = get_settings()
        llm_model_used: str | None = None

        if settings.OLLAMA_ENABLED:
            try:
                analyzer = LLMAnalyzer()
                if await analyzer.is_available():
                    llm_model_used = analyzer.model
                    summary_data = (
                        f"Total models: {stats['total_models']}, "
                        f"Total repos: {stats['total_repos']}, "
                        f"Total papers: {stats['total_papers']}, "
                        f"Active signals: {stats['active_signals']}, "
                        f"Total downloads: {format_number(stats['total_downloads'])}. "
                    )
                    if trending:
                        summary_data += "Top trending: " + ", ".join(
                            f"{t['identifier']} ({format_percent(t['growth_percent'])})"
                            for t in trending[:3]
                        )
                    ai_summary = await analyzer.answer_question(
                        "Write a 3-4 sentence executive summary of today's AI trend data.",
                        summary_data,
                    )
            except Exception as exc:
                log.warning("report_generator.daily.llm_error", error=str(exc))

        # -- Render markdown -----------------------------------------------
        markdown = ReportGenerator._render_daily_markdown(
            stats=stats,
            trending=trending,
            signals=signals,
            niches=niches,
            ai_summary=ai_summary,
        )

        elapsed = round(time.monotonic() - start_time, 2)

        # -- Persist report ------------------------------------------------
        report = Report(
            title=f"Daily Report -- {now.strftime('%Y-%m-%d')}",
            report_type="daily",
            content_markdown=markdown,
            signals_count=len(signals),
            period_start=now.replace(hour=0, minute=0, second=0, microsecond=0),
            period_end=now,
            generated_at=now,
            generation_time_seconds=elapsed,
            llm_model_used=llm_model_used,
        )

        session.add(report)
        await session.flush()

        # -- Save to filesystem -------------------------------------------
        file_path = await ReportGenerator._save_report_file(report)
        report.file_path = file_path
        await session.flush()

        log.info(
            "report_generator.daily.completed",
            report_id=report.id,
            duration_seconds=elapsed,
            file_path=file_path,
        )

        return report

    # ------------------------------------------------------------------
    # Weekly report
    # ------------------------------------------------------------------

    @staticmethod
    async def generate_weekly_report(session: AsyncSession) -> Report:
        """Generate a weekly report with AI insights.

        More detailed than daily: includes growth rates, new high-traction
        models, declining trends, arXiv activity, and a full AI-generated
        insights section via :meth:`LLMAnalyzer.generate_weekly_insights`.

        Args:
            session: An active async database session.

        Returns:
            The persisted :class:`Report` instance.
        """
        log.info("report_generator.weekly.started")
        start_time = time.monotonic()
        now = utc_now()
        week_start = now - timedelta(days=7)

        # -- Gather data ---------------------------------------------------
        stats = await get_overview_stats(session)
        growth = await compute_growth_rates(session)
        trending = await get_top_trending(session, limit=10)
        signals = await get_recent_signals(session, limit=20)
        niches = await get_niche_summary(session)

        # Identify new high-traction models (positive growth, sorted desc).
        new_models: list[dict[str, Any]] = [
            m for m in growth.get("hf_models", [])
            if m["growth_percent"] > 0
        ][:10]

        # Identify declining items (negative growth).
        declining: list[dict[str, Any]] = [
            m for m in growth.get("hf_models", [])
            if m["growth_percent"] < 0
        ][:10]

        # Placeholder for arXiv spikes -- could be expanded with dedicated
        # arXiv analytics in a future iteration.
        arxiv_spikes: list[dict[str, Any]] = []

        # -- AI insights ---------------------------------------------------
        ai_insights = ""
        settings = get_settings()
        llm_model_used: str | None = None

        if settings.OLLAMA_ENABLED:
            try:
                analyzer = LLMAnalyzer()
                if await analyzer.is_available():
                    llm_model_used = analyzer.model
                    ai_insights = await analyzer.generate_weekly_insights(
                        niches_data=niches,
                        new_models=new_models,
                        declining=declining,
                        arxiv_spikes=arxiv_spikes,
                    )
            except Exception as exc:
                log.warning("report_generator.weekly.llm_error", error=str(exc))

        # -- Render markdown -----------------------------------------------
        markdown = ReportGenerator._render_weekly_markdown(
            stats=stats,
            growth=growth,
            trending=trending,
            signals=signals,
            niches=niches,
            ai_insights=ai_insights,
        )

        elapsed = round(time.monotonic() - start_time, 2)

        # -- Persist report ------------------------------------------------
        report = Report(
            title=f"Weekly Report -- {week_start.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}",
            report_type="weekly",
            content_markdown=markdown,
            signals_count=len(signals),
            period_start=week_start,
            period_end=now,
            generated_at=now,
            generation_time_seconds=elapsed,
            llm_model_used=llm_model_used,
        )

        session.add(report)
        await session.flush()

        file_path = await ReportGenerator._save_report_file(report)
        report.file_path = file_path
        await session.flush()

        log.info(
            "report_generator.weekly.completed",
            report_id=report.id,
            duration_seconds=elapsed,
            file_path=file_path,
        )

        return report

    # ------------------------------------------------------------------
    # Niche deep-dive report
    # ------------------------------------------------------------------

    @staticmethod
    async def generate_niche_report(
        session: AsyncSession,
        niche_id: int,
    ) -> Report:
        """Generate a deep-dive report for a specific niche.

        Args:
            session: An active async database session.
            niche_id: Primary key of the target niche.

        Returns:
            The persisted :class:`Report` instance.

        Raises:
            ValueError: If no niche with the given ID exists.
        """
        log.info("report_generator.niche.started", niche_id=niche_id)
        start_time = time.monotonic()
        now = utc_now()

        detail = await get_niche_detail(session, niche_id)
        niche_info: dict[str, Any] = detail["niche"]

        # -- Render markdown -----------------------------------------------
        lines: list[str] = [
            f"# Niche Deep-Dive: {niche_info['name']}",
            f"**Generated**: {now.strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            f"**Keywords**: {', '.join(niche_info.get('keywords', []))}",
            "",
        ]

        # Top models
        lines.append("## Top Models")
        lines.append("")
        top_models: list[dict[str, Any]] = detail.get("top_models", [])
        if top_models:
            lines.append("| Rank | Model | Downloads | Growth |")
            lines.append("|------|-------|-----------|--------|")
            for idx, m in enumerate(top_models, 1):
                growth_str = format_percent(m["growth_percent"]) if m.get("growth_percent") is not None else "N/A"
                lines.append(
                    f"| {idx} | {m['model_id']} | {format_number(m['downloads'])} | {growth_str} |"
                )
        else:
            lines.append("No models assigned to this niche yet.")
        lines.append("")

        # Top repos
        lines.append("## Top Repositories")
        lines.append("")
        top_repos: list[dict[str, Any]] = detail.get("top_repos", [])
        if top_repos:
            lines.append("| Rank | Repository | Stars | Language | Growth |")
            lines.append("|------|-----------|-------|----------|--------|")
            for idx, r in enumerate(top_repos, 1):
                growth_str = format_percent(r["growth_percent"]) if r.get("growth_percent") is not None else "N/A"
                lines.append(
                    f"| {idx} | {r['full_name']} | {format_number(r['stars'])} | {r.get('language', 'N/A')} | {growth_str} |"
                )
        else:
            lines.append("No repositories assigned to this niche yet.")
        lines.append("")

        # Recent papers
        lines.append("## Recent Papers")
        lines.append("")
        papers: list[dict[str, Any]] = detail.get("recent_papers", [])
        if papers:
            for p in papers:
                lines.append(f"- **{p['title']}** ({p['arxiv_id']}) -- {p['primary_category']}, published {p['published_at']}")
        else:
            lines.append("No papers assigned to this niche yet.")
        lines.append("")

        # Recent signals
        lines.append("## Recent Signals")
        lines.append("")
        recent_signals: list[dict[str, Any]] = detail.get("recent_signals", [])
        if recent_signals:
            for s in recent_signals:
                lines.append(f"- [{s['severity'].upper()}] {s['signal_type']}: {s['description']}")
        else:
            lines.append("No recent signals for this niche.")
        lines.append("")

        lines.append("---")
        lines.append("*Generated by AI Trend Monitor*")

        markdown = "\n".join(lines)
        elapsed = round(time.monotonic() - start_time, 2)

        report = Report(
            title=f"Niche Report -- {niche_info['name']}",
            report_type="niche",
            content_markdown=markdown,
            niche_id=niche_id,
            signals_count=len(recent_signals),
            period_start=now - timedelta(days=30),
            period_end=now,
            generated_at=now,
            generation_time_seconds=elapsed,
        )

        session.add(report)
        await session.flush()

        file_path = await ReportGenerator._save_report_file(report)
        report.file_path = file_path
        await session.flush()

        log.info(
            "report_generator.niche.completed",
            report_id=report.id,
            niche_id=niche_id,
            duration_seconds=elapsed,
            file_path=file_path,
        )

        return report

    # ------------------------------------------------------------------
    # Markdown renderers
    # ------------------------------------------------------------------

    @staticmethod
    def _render_daily_markdown(
        stats: dict[str, Any],
        trending: list[dict[str, Any]],
        signals: list[Any],
        niches: list[dict[str, Any]],
        ai_summary: str,
    ) -> str:
        """Render a daily report as a markdown string.

        Args:
            stats: Overview statistics from :func:`get_overview_stats`.
            trending: Top trending items from :func:`get_top_trending`.
            signals: Recent :class:`TrendSignal` instances.
            niches: Niche summary dicts from :func:`get_niche_summary`.
            ai_summary: AI-generated executive summary (may be empty).

        Returns:
            The complete markdown report as a string.
        """
        now = utc_now()
        lines: list[str] = [
            "# AI Trend Monitor -- Daily Report",
            f"**Date**: {now.strftime('%Y-%m-%d')}",
            f"**Generated**: {now.strftime('%Y-%m-%d %H:%M UTC')}",
            "",
        ]

        # Executive summary
        lines.append("## Executive Summary")
        lines.append("")
        if ai_summary:
            lines.append(ai_summary)
        else:
            lines.append(
                f"Today we are tracking **{format_number(stats['total_models'])}** models, "
                f"**{format_number(stats['total_repos'])}** repositories, and "
                f"**{format_number(stats['total_papers'])}** papers across "
                f"**{stats['total_niches']}** niches. "
                f"There are **{stats['active_signals']}** unread signals and "
                f"**{format_number(stats['total_downloads'])}** total downloads tracked."
            )
        lines.append("")

        # Overview stats
        lines.append("## Overview")
        lines.append("")
        lines.append(f"- **Models tracked**: {format_number(stats['total_models'])}")
        lines.append(f"- **Repositories tracked**: {format_number(stats['total_repos'])}")
        lines.append(f"- **Papers indexed**: {format_number(stats['total_papers'])}")
        lines.append(f"- **Active niches**: {stats['total_niches']}")
        lines.append(f"- **Unread signals**: {stats['active_signals']}")
        lines.append(f"- **Total downloads**: {format_number(stats['total_downloads'])}")
        lines.append("")

        # Top trending
        lines.append("## Top Trending")
        lines.append("")
        if trending:
            lines.append("| Rank | Source | Item | Metric | Growth |")
            lines.append("|------|--------|------|--------|--------|")
            for idx, t in enumerate(trending, 1):
                lines.append(
                    f"| {idx} | {t['source_type']} | {t['identifier']} | "
                    f"{format_number(t['metric_value'])} | {format_percent(t['growth_percent'])} |"
                )
        else:
            lines.append("No trending data available yet.")
        lines.append("")

        # Signals detected
        lines.append("## Signals Detected")
        lines.append("")
        if signals:
            for s in signals:
                severity_tag = s.severity.upper()
                lines.append(f"- [{severity_tag}] **{s.signal_type}**: {s.description}")
        else:
            lines.append("No recent signals detected.")
        lines.append("")

        # Niche overview
        lines.append("## Niche Overview")
        lines.append("")
        if niches:
            lines.append("| Niche | Models | Downloads | Avg Growth |")
            lines.append("|-------|--------|-----------|------------|")
            for n in niches:
                lines.append(
                    f"| {n['name']} | {n['model_count']} | "
                    f"{format_number(n['total_downloads'])} | "
                    f"{format_percent(n['avg_growth_percent'])} |"
                )
        else:
            lines.append("No niche data available yet.")
        lines.append("")

        lines.append("---")
        lines.append("*Generated by AI Trend Monitor*")

        return "\n".join(lines)

    @staticmethod
    def _render_weekly_markdown(
        stats: dict[str, Any],
        growth: dict[str, list[dict[str, Any]]],
        trending: list[dict[str, Any]],
        signals: list[Any],
        niches: list[dict[str, Any]],
        ai_insights: str,
    ) -> str:
        """Render a weekly report as a markdown string.

        Args:
            stats: Overview statistics.
            growth: Growth rate data from :func:`compute_growth_rates`.
            trending: Top trending items.
            signals: Recent :class:`TrendSignal` instances.
            niches: Niche summary dicts.
            ai_insights: AI-generated insights section (may be empty).

        Returns:
            The complete weekly markdown report as a string.
        """
        now = utc_now()
        week_start = now - timedelta(days=7)

        lines: list[str] = [
            "# AI Trend Monitor -- Weekly Report",
            f"**Period**: {week_start.strftime('%Y-%m-%d')} - {now.strftime('%Y-%m-%d')}",
            f"**Generated**: {now.strftime('%Y-%m-%d %H:%M UTC')}",
            "",
        ]

        # Executive summary
        lines.append("## Executive Summary")
        lines.append("")
        if ai_insights:
            # Use the first paragraph of AI insights as the executive summary.
            first_section_end = ai_insights.find("\n## ")
            if first_section_end > 0:
                lines.append(ai_insights[:first_section_end].strip())
            else:
                lines.append(
                    f"This week we tracked **{format_number(stats['total_models'])}** models "
                    f"and **{format_number(stats['total_repos'])}** repositories with "
                    f"**{format_number(stats['total_downloads'])}** total downloads."
                )
        else:
            lines.append(
                f"This week we tracked **{format_number(stats['total_models'])}** models, "
                f"**{format_number(stats['total_repos'])}** repositories, and "
                f"**{format_number(stats['total_papers'])}** papers. "
                f"There were **{len(signals)}** signals detected."
            )
        lines.append("")

        # Top growing models
        lines.append("## Top Growing Models")
        lines.append("")
        hf_growth = growth.get("hf_models", [])
        top_growing = [m for m in hf_growth if m["growth_percent"] > 0][:10]
        if top_growing:
            lines.append("| Rank | Model | Downloads | Growth |")
            lines.append("|------|-------|-----------|--------|")
            for idx, m in enumerate(top_growing, 1):
                lines.append(
                    f"| {idx} | {m['identifier']} | "
                    f"{format_number(m['metric_current'])} | "
                    f"{format_percent(m['growth_percent'])} |"
                )
        else:
            lines.append("No growth data available yet.")
        lines.append("")

        # Top growing repos
        lines.append("## Top Growing Repositories")
        lines.append("")
        gh_growth = growth.get("github_repos", [])
        top_repos = [r for r in gh_growth if r["growth_percent"] > 0][:10]
        if top_repos:
            lines.append("| Rank | Repository | Stars | Growth |")
            lines.append("|------|-----------|-------|--------|")
            for idx, r in enumerate(top_repos, 1):
                lines.append(
                    f"| {idx} | {r['identifier']} | "
                    f"{format_number(r['metric_current'])} | "
                    f"{format_percent(r['growth_percent'])} |"
                )
        else:
            lines.append("No repository growth data available yet.")
        lines.append("")

        # Signals detected
        lines.append("## Signals Detected")
        lines.append("")
        if signals:
            for s in signals:
                severity_tag = s.severity.upper()
                lines.append(f"- [{severity_tag}] **{s.signal_type}**: {s.description}")
        else:
            lines.append("No signals detected this week.")
        lines.append("")

        # Niche overview
        lines.append("## Niche Overview")
        lines.append("")
        if niches:
            lines.append("| Niche | Models | Downloads | Growth |")
            lines.append("|-------|--------|-----------|--------|")
            for n in niches:
                lines.append(
                    f"| {n['name']} | {n['model_count']} | "
                    f"{format_number(n['total_downloads'])} | "
                    f"{format_percent(n['avg_growth_percent'])} |"
                )
        else:
            lines.append("No niche data available yet.")
        lines.append("")

        # AI insights section
        lines.append("## AI Insights")
        lines.append("")
        if ai_insights:
            lines.append(ai_insights)
        else:
            lines.append(
                "*AI-powered analysis is currently unavailable. "
                "Enable Ollama for enriched weekly insights.*"
            )
        lines.append("")

        lines.append("---")
        lines.append("*Generated by AI Trend Monitor*")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # File persistence
    # ------------------------------------------------------------------

    @staticmethod
    async def _save_report_file(report: Report) -> str:
        """Save report markdown to the filesystem.

        Creates the output directory if it does not exist.  The filename
        is derived from the report type, date, and database ID to ensure
        uniqueness.

        Args:
            report: The :class:`Report` instance (must have ``id`` set).

        Returns:
            The absolute file path where the report was written.
        """
        settings = get_settings()
        output_dir = Path(settings.REPORTS_OUTPUT_DIR)

        # Ensure the directory tree exists.
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = report.generated_at.strftime("%Y-%m-%d")
        safe_type = report.report_type.replace(" ", "_").lower()
        filename = f"{safe_type}_{date_str}_{report.id}.md"
        file_path = output_dir / filename

        async with aiofiles.open(file_path, mode="w", encoding="utf-8") as f:
            await f.write(report.content_markdown)

        log.info(
            "report_generator.file_saved",
            file_path=str(file_path),
            size_bytes=len(report.content_markdown.encode("utf-8")),
        )

        return str(file_path)
