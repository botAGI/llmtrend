"""Application configuration using pydantic-settings v2.

Loads all environment variables with sensible defaults for local development.
Use a .env file or real environment variables in production.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the AI Trend Monitor application.

    All settings are read from environment variables (or a .env file).
    Groups are organized by subsystem: database, redis, FastAPI, Celery,
    external APIs, Telegram, scheduler, and general runtime options.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────────────

    POSTGRES_HOST: str = Field(default="postgres", description="PostgreSQL hostname")
    POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL port")
    POSTGRES_DB: str = Field(default="ai_trends", description="PostgreSQL database name")
    POSTGRES_USER: str = Field(default="monitor", description="PostgreSQL user")
    POSTGRES_PASSWORD: str = Field(
        default="changeme_in_production",
        description="PostgreSQL password -- override in production",
    )

    @property
    def database_url(self) -> str:
        """Async database URL for SQLAlchemy + asyncpg."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def database_url_sync(self) -> str:
        """Synchronous database URL used by Alembic migrations."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Redis ───────────────────────────────────────────────────────────

    REDIS_URL: str = Field(
        default="redis://redis:6379/0",
        description="Redis URL for general caching",
    )

    # ── FastAPI ─────────────────────────────────────────────────────────

    APP_ENV: str = Field(default="development", description="Runtime environment name")
    APP_DEBUG: bool = Field(default=True, description="Enable debug mode")
    APP_HOST: str = Field(default="0.0.0.0", description="Bind address")
    APP_PORT: int = Field(default=8000, description="Bind port")
    APP_LOG_LEVEL: str = Field(default="INFO", description="Application log level")
    APP_API_KEY: str = Field(default="", description="Optional API key for protected endpoints")
    APP_CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:8501"],
        description="Allowed CORS origins",
    )
    APP_WORKERS: int = Field(default=1, description="Number of Uvicorn workers")

    # ── Celery ──────────────────────────────────────────────────────────

    CELERY_BROKER_URL: str = Field(
        default="redis://redis:6379/1",
        description="Celery broker URL",
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://redis:6379/2",
        description="Celery result backend URL",
    )

    # ── HuggingFace ─────────────────────────────────────────────────────

    HUGGINGFACE_TOKEN: str = Field(default="", description="HuggingFace API token")
    HF_MODELS_LIMIT: int = Field(
        default=200,
        description="Maximum number of models to fetch per request",
    )
    HF_REQUEST_TIMEOUT: int = Field(
        default=30,
        description="HTTP request timeout in seconds for the HuggingFace API",
    )

    # ── GitHub ──────────────────────────────────────────────────────────

    GITHUB_TOKEN: str = Field(default="", description="GitHub personal access token")
    GITHUB_MIN_STARS: int = Field(
        default=50,
        description="Minimum star count for repository discovery",
    )
    GITHUB_RESULTS_PER_PAGE: int = Field(
        default=100,
        description="Results per page for GitHub search API",
    )
    GITHUB_MAX_PAGES: int = Field(
        default=5,
        description="Maximum pages to paginate through",
    )
    GITHUB_REQUEST_TIMEOUT: int = Field(
        default=30,
        description="HTTP request timeout in seconds for the GitHub API",
    )

    # ── arXiv ───────────────────────────────────────────────────────────

    ARXIV_MAX_RESULTS: int = Field(
        default=500,
        description="Maximum number of arXiv papers to fetch",
    )
    ARXIV_REQUEST_DELAY: float = Field(
        default=3.0,
        description="Delay between consecutive arXiv API requests (seconds)",
    )
    ARXIV_REQUEST_TIMEOUT: int = Field(
        default=60,
        description="HTTP request timeout in seconds for the arXiv API",
    )
    ARXIV_CATEGORIES: list[str] = Field(
        default=["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.NE"],
        description="arXiv categories to monitor",
    )

    # ── Ollama ──────────────────────────────────────────────────────────

    OLLAMA_BASE_URL: str = Field(
        default="http://ollama:11434",
        description="Base URL for the Ollama inference server",
    )
    OLLAMA_MODEL: str = Field(
        default="llama3.1:8b",
        description="Default Ollama model for analysis tasks",
    )
    OLLAMA_ENABLED: bool = Field(
        default=True,
        description="Enable Ollama-based analysis features",
    )
    OLLAMA_TIMEOUT: int = Field(
        default=120,
        description="HTTP request timeout in seconds for Ollama",
    )
    OLLAMA_TEMPERATURE: float = Field(
        default=0.3,
        description="Sampling temperature for Ollama generation",
    )

    # ── Telegram ────────────────────────────────────────────────────────

    TELEGRAM_BOT_TOKEN: str = Field(default="", description="Telegram bot token")
    TELEGRAM_ALLOWED_USERS: str = Field(
        default="",
        description="Comma-separated list of allowed Telegram user IDs",
    )
    TELEGRAM_ADMIN_USERS: str = Field(
        default="",
        description="Comma-separated list of admin Telegram user IDs",
    )
    TELEGRAM_ENABLED: bool = Field(
        default=True,
        description="Enable the Telegram bot integration",
    )

    # ── Scheduler ───────────────────────────────────────────────────────

    COLLECTION_SCHEDULE_HOURS: int = Field(
        default=6,
        description="Interval in hours between data collection runs",
    )
    ANALYTICS_SCHEDULE_HOURS: int = Field(
        default=12,
        description="Interval in hours between analytics runs",
    )

    # ── General ─────────────────────────────────────────────────────────

    LOG_LEVEL: str = Field(default="INFO", description="Root log level")
    ENVIRONMENT: str = Field(default="production", description="Deployment environment tag")
    SECRET_KEY: str = Field(
        default="changeme",
        description="Secret key for signing -- override in production",
    )

    # ── Reports ─────────────────────────────────────────────────────────

    REPORTS_OUTPUT_DIR: str = Field(
        default="/app/reports",
        description="Directory where generated reports are stored",
    )
    REPORTS_MAX_AGE_DAYS: int = Field(
        default=90,
        description="Retention period for generated reports (days)",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance.

    The first call reads from the environment / .env file; subsequent calls
    return the same object without re-parsing.
    """
    return Settings()
