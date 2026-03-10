"""Data collector modules for the AI Trend Monitor.

This package contains Layer 2 collectors that fetch data from external APIs
(Hugging Face Hub, GitHub, arXiv) and upsert it into the local database.

Usage::

    from app.collectors import HuggingFaceCollector, GitHubCollector, ArxivCollector

    async with get_async_session() as session:
        collector = HuggingFaceCollector(session)
        result = await collector.run()
"""

from app.collectors.base import BaseCollector, CollectionResult
from app.collectors.huggingface import HuggingFaceCollector
from app.collectors.github_collector import GitHubCollector
from app.collectors.arxiv_collector import ArxivCollector

__all__ = [
    "BaseCollector",
    "CollectionResult",
    "HuggingFaceCollector",
    "GitHubCollector",
    "ArxivCollector",
]
