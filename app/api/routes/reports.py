"""Report management API routes.

Provides listing, generation, detail views, and download endpoints for
daily, weekly, and niche-specific trend reports.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func, select

from app.api.schemas import (
    ReportDetailResponse,
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportItem,
    ReportListResponse,
)
from app.dependencies import DBSession
from app.models.report import Report
from app.services.export_service import ExportService
from app.services.report_generator import ReportGenerator

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get(
    "/",
    response_model=ReportListResponse,
    summary="List reports",
    description="List generated reports with optional filtering by type.",
)
async def list_reports(
    db: DBSession,
    report_type: str | None = Query(
        default=None,
        description="Filter by report type: daily, weekly, niche",
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Max items to return"),
) -> ReportListResponse:
    """List generated reports."""
    # -- Count query --------------------------------------------------------
    count_stmt = select(func.count(Report.id))
    if report_type is not None:
        count_stmt = count_stmt.where(Report.report_type == report_type)
    total: int = (await db.execute(count_stmt)).scalar_one()

    # -- Data query ---------------------------------------------------------
    data_stmt = select(Report).order_by(Report.generated_at.desc()).limit(limit)
    if report_type is not None:
        data_stmt = data_stmt.where(Report.report_type == report_type)

    result = await db.execute(data_stmt)
    reports = result.scalars().all()

    items = [
        ReportItem(
            id=r.id,
            title=r.title,
            report_type=r.report_type,
            niche_id=r.niche_id,
            signals_count=r.signals_count,
            period_start=r.period_start,
            period_end=r.period_end,
            generated_at=r.generated_at,
            generation_time_seconds=r.generation_time_seconds,
            llm_model_used=r.llm_model_used,
            file_path=r.file_path,
            created_at=r.created_at,
        )
        for r in reports
    ]

    return ReportListResponse(items=items, total=total)


@router.post(
    "/generate",
    response_model=ReportGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a report",
    description="Trigger report generation. Supports daily, weekly, and niche report types.",
)
async def generate_report(
    body: ReportGenerateRequest,
    db: DBSession,
) -> ReportGenerateResponse:
    """Trigger report generation. Returns report details."""
    report_type = body.report_type.lower().strip()

    if report_type not in ("daily", "weekly", "niche"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid report_type '{body.report_type}'. Must be one of: daily, weekly, niche",
        )

    if report_type == "niche" and body.niche_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="niche_id is required when report_type is 'niche'",
        )

    try:
        if report_type == "daily":
            report = await ReportGenerator.generate_daily_report(db)
        elif report_type == "weekly":
            report = await ReportGenerator.generate_weekly_report(db)
        else:
            report = await ReportGenerator.generate_niche_report(db, body.niche_id)  # type: ignore[arg-type]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return ReportGenerateResponse(
        id=report.id,
        title=report.title,
        report_type=report.report_type,
        generated_at=report.generated_at,
        generation_time_seconds=report.generation_time_seconds,
        file_path=report.file_path,
    )


@router.get(
    "/{report_id}",
    response_model=ReportDetailResponse,
    summary="Get report detail",
    description="Get the full report including markdown content.",
)
async def get_report(report_id: int, db: DBSession) -> ReportDetailResponse:
    """Get full report content."""
    stmt = select(Report).where(Report.id == report_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with id={report_id} not found",
        )

    return ReportDetailResponse(
        id=report.id,
        title=report.title,
        report_type=report.report_type,
        content_markdown=report.content_markdown,
        content_html=report.content_html,
        niche_id=report.niche_id,
        signals_count=report.signals_count,
        period_start=report.period_start,
        period_end=report.period_end,
        generated_at=report.generated_at,
        generation_time_seconds=report.generation_time_seconds,
        llm_model_used=report.llm_model_used,
        file_path=report.file_path,
        created_at=report.created_at,
    )


@router.get(
    "/{report_id}/download",
    summary="Download report",
    description="Download a report as a .md or .html file.",
    responses={
        200: {
            "description": "Report file download",
            "content": {
                "text/markdown": {},
                "text/html": {},
            },
        },
    },
)
async def download_report(
    report_id: int,
    db: DBSession,
    format: str = Query(
        default="md",
        description="Download format: md or html",
        regex="^(md|html)$",
    ),
) -> Response:
    """Download report as .md or .html file."""
    stmt = select(Report).where(Report.id == report_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with id={report_id} not found",
        )

    # Sanitize title for use as filename
    safe_title = (
        report.title.replace(" ", "_")
        .replace("/", "-")
        .replace("\\", "-")
        .replace(":", "-")
    )
    date_str = report.generated_at.strftime("%Y%m%d")

    if format == "html":
        html_content = await ExportService.report_to_html(report.content_markdown)
        filename = f"{safe_title}_{date_str}.html"
        return Response(
            content=html_content,
            media_type="text/html; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    # Default: markdown
    filename = f"{safe_title}_{date_str}.md"
    return Response(
        content=report.content_markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
