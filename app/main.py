"""FastAPI application factory and ASGI entry point.

Creates and configures the FastAPI application with:
- Async lifespan management (DB table creation, default niche seeding, cleanup)
- CORS middleware configured from settings
- All API routes mounted via the aggregated ``api_router``
- A ``/health`` endpoint for liveness probes

Usage (uvicorn)::

    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.config import get_settings
from app.database import close_engine, get_async_session, get_engine
from app.models import Base

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown.

    Startup
    ~~~~~~~
    1. Create all database tables if they do not exist (idempotent).
    2. Seed the default set of niches so the dashboard has content
       categories from the very first launch.

    Shutdown
    ~~~~~~~~
    1. Dispose of the async engine connection pool to release all DB
       connections cleanly.
    """
    log.info("app.startup.begin")

    # -- Create tables ------------------------------------------------------
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("app.startup.tables_ensured")

    # -- Seed default niches ------------------------------------------------
    from app.analytics.niches import ensure_default_niches

    async for session in get_async_session():
        await ensure_default_niches(session)
    log.info("app.startup.niches_seeded")

    log.info("app.startup.complete")
    yield

    # -- Shutdown -----------------------------------------------------------
    log.info("app.shutdown.begin")
    await close_engine()
    log.info("app.shutdown.complete")


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application instance.

    Reads configuration from environment variables / ``.env`` file via
    :func:`get_settings`, then wires up middleware, routes, and the
    lifespan context manager.

    Returns:
        A fully configured :class:`FastAPI` instance ready to serve.
    """
    settings = get_settings()

    app = FastAPI(
        title="AI Trend Monitor API",
        version="1.0.0",
        description=(
            "RESTful API for monitoring AI model trends across HuggingFace, "
            "GitHub, and arXiv. Provides analytics, signal detection, niche "
            "classification, and automated report generation."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # -- CORS ---------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.APP_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- Routes -------------------------------------------------------------
    app.include_router(api_router)

    # -- Health check (outside api_router for simplicity) -------------------
    @app.get(
        "/health",
        tags=["health"],
        summary="Health check",
        description="Simple liveness probe that returns OK when the server is running.",
    )
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
