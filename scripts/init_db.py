"""Database initialization script.

Creates all tables and seeds the default set of niches so the application
is ready for first use.

Usage::

    python -m scripts.init_db
"""

import asyncio

from app.database import get_engine, get_async_session
from app.models import Base
from app.analytics.niches import ensure_default_niches


async def init_db() -> None:
    """Create database tables and seed default niches."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created.")

    # Seed default niches
    async for session in get_async_session():
        await ensure_default_niches(session)
    print("Default niches seeded.")


if __name__ == "__main__":
    asyncio.run(init_db())
