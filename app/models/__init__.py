"""SQLAlchemy ORM models for the AI Trend Monitor project."""

from app.models.base import Base, TimestampMixin
from app.models.hf_model import HFModel
from app.models.github_repo import GitHubRepo
from app.models.arxiv_paper import ArxivPaper
from app.models.niche import Niche, niche_hf_models, niche_github_repos, niche_arxiv_papers
from app.models.trend_signal import TrendSignal
from app.models.report import Report
from app.models.collection_run import CollectionRun

__all__ = [
    "Base",
    "TimestampMixin",
    "HFModel",
    "GitHubRepo",
    "ArxivPaper",
    "Niche",
    "niche_hf_models",
    "niche_github_repos",
    "niche_arxiv_papers",
    "TrendSignal",
    "Report",
    "CollectionRun",
]
