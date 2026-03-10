"""API route aggregation.

Collects all sub-routers and exposes a single ``api_router`` that the
FastAPI application includes at startup.
"""

from fastapi import APIRouter

from app.api.routes import models, niches, overview, reports, settings, signals

api_router = APIRouter()
api_router.include_router(overview.router)
api_router.include_router(niches.router)
api_router.include_router(models.router)
api_router.include_router(signals.router)
api_router.include_router(reports.router)
api_router.include_router(settings.router)
