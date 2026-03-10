# AI Trend Monitor

**Real-time intelligence platform for tracking the AI/ML ecosystem across HuggingFace, GitHub, and arXiv.**

AI Trend Monitor continuously collects data from the three most important sources in the AI ecosystem, detects trend signals, classifies resources into thematic niches, generates analytical reports with a local LLM, and delivers insights through a Streamlit dashboard and Telegram bot.

---

## Architecture

```
                          +------------------+
                          |   Telegram Bot   |  (aiogram 3)
                          +--------+---------+
                                   |
+------------------+     +---------v---------+     +------------------+
|   Streamlit      +---->|   FastAPI (API)   |<----+   Celery Worker  |
|   Dashboard      |     +---------+---------+     +--------+---------+
+------------------+               |                        |
      :8501                        |  :8000                 |
                          +--------v---------+     +--------v---------+
                          |   PostgreSQL 16   |     |   Redis 7        |
                          +------------------+     +------------------+
                                                           |
                          +------------------+     +-------v----------+
                          |   Ollama (LLM)   |     | Celery Scheduler |
                          +------------------+     +------------------+
                             llama3.1:8b
```

### Data Flow

1. **Collection** -- Celery tasks (or manual triggers) fetch data from HuggingFace Hub, GitHub Search API, and arXiv API on a configurable schedule (default: every 6 hours).
2. **Storage** -- Raw data is upserted into PostgreSQL with full history tracking (current and previous snapshots for growth calculation).
3. **Classification** -- A keyword-based engine assigns every model, repo, and paper to one or more of 15 predefined niches (e.g., *Text Generation / LLMs*, *Image Generation*, *AI Agents*).
4. **Analytics** -- Trend detection algorithms identify download spikes, star surges, new entries, growth accelerations, and niche-level movements. Results are stored as typed signals with severity levels.
5. **Reporting** -- An Ollama-powered LLM (llama3.1:8b by default) generates natural-language daily, weekly, and niche-specific reports in Markdown.
6. **Delivery** -- The Streamlit dashboard and Telegram bot consume the REST API to present charts, tables, signals, and reports to the user.

---

## Features

- **Multi-source data collection** from HuggingFace Hub, GitHub, and arXiv with configurable limits and rate limiting
- **15 predefined AI niches** with automatic keyword-based classification
- **Trend signal detection** with four severity levels (critical / high / medium / low) and five signal types
- **LLM-powered report generation** via a local Ollama instance (no external API keys required)
- **Interactive Streamlit dashboard** with 8 pages: Overview, Niches, Models, Research, GitHub, Signals, Reports, Settings
- **Telegram bot** with full command set: reports, search, signal alerts, niche browsing, and AI Q&A
- **REST API** with OpenAPI docs at `/docs` and ReDoc at `/redoc`
- **Celery task queue** with Redis broker for scheduled and on-demand data collection
- **Docker Compose deployment** -- single `docker compose up` brings up all 8 services
- **Demo data seeder** for an impressive first-launch experience with 500 models, 200 repos, 100 papers
- **Alembic migrations** for production-grade schema management

---

## Requirements

| What | Needed upfront? | `setup.sh` handles? |
|------|:---:|:---:|
| Docker & Docker Compose | Yes | Offers to install |
| Git | Yes | No |
| 4 GB+ free RAM | Yes | No |
| HuggingFace API token | No (optional) | Prompts for it |
| GitHub personal access token | No (optional, higher rate limits) | Prompts for it |
| Telegram bot token | No (optional) | Prompts for it |
| NVIDIA GPU | No (CPU inference works) | Detects and configures |
| Python 3.11+ | Only for local dev | No (runs in Docker) |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/yourorg/ai-trend-monitor.git
cd ai-trend-monitor

# 2. Run the setup wizard (creates .env, checks Docker, pulls images)
make setup          # or: chmod +x setup.sh && ./setup.sh

# 3. Start everything
make up             # or: docker compose up -d
```

After startup completes (about 60-90 seconds for Ollama model pull on first run):

| Service | URL |
|---------|-----|
| Dashboard | [http://localhost:8501](http://localhost:8501) |
| API Docs | [http://localhost:8000/docs](http://localhost:8000/docs) |
| ReDoc | [http://localhost:8000/redoc](http://localhost:8000/redoc) |
| Health | [http://localhost:8000/health](http://localhost:8000/health) |

To load demo data for the first launch:

```bash
make seed           # or: docker compose exec api python -m scripts.seed_demo_data
```

---

## Detailed Setup

### 1. Environment Configuration

Copy the example environment file and edit it:

```bash
cp .env.example .env
```

Key variables to configure:

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_PASSWORD` | `changeme_in_production` | Database password |
| `SECRET_KEY` | `changeme` | Application signing key |
| `HUGGINGFACE_TOKEN` | *(empty)* | HuggingFace API token for higher rate limits |
| `GITHUB_TOKEN` | *(empty)* | GitHub PAT for higher rate limits |
| `TELEGRAM_BOT_TOKEN` | *(empty)* | Telegram bot token from @BotFather |
| `TELEGRAM_ALLOWED_USERS` | *(empty)* | Comma-separated Telegram user IDs |
| `OLLAMA_MODEL` | `llama3.1:8b` | Ollama model for report generation |
| `COLLECTION_SCHEDULE_HOURS` | `6` | Hours between automatic data collection runs |
| `ANALYTICS_SCHEDULE_HOURS` | `12` | Hours between analytics runs |

See `.env.example` for the complete list of configuration options.

### 2. Docker Services

Start all services:

```bash
docker compose up -d
```

For development with hot-reload and debug logging:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
# or simply:
make dev
```

### 3. Database Initialization

Tables are created automatically on first API startup. To manually initialize:

```bash
docker compose exec api python -m scripts.init_db
```

To run Alembic migrations (for schema updates):

```bash
make migrate        # or: docker compose exec api alembic upgrade head
```

### 4. Demo Data

Load realistic demo data to populate the dashboard immediately:

```bash
make seed
```

This creates 500 HuggingFace models, 200 GitHub repos, 100 arXiv papers, 20 trend signals, 3 reports, and niche assignments. The seed script is idempotent -- it skips if the database already has data.

### 5. Manual Data Collection

Trigger a collection run outside the normal schedule:

```bash
make collect                                            # all sources
docker compose exec api python -m scripts.run_collection huggingface  # single source
docker compose exec api python -m scripts.run_collection github
docker compose exec api python -m scripts.run_collection arxiv
```

---

## Docker Services

| Service | Image / Build | Port | Description |
|---------|--------------|------|-------------|
| **postgres** | `postgres:16-alpine` | 5432 (dev) | Primary data store |
| **redis** | `redis:7-alpine` | 6379 (dev) | Celery broker, caching, result backend |
| **api** | `Dockerfile` (target: api) | 8000 | FastAPI REST API |
| **worker** | `Dockerfile` (target: worker) | -- | Celery worker for background tasks |
| **scheduler** | `Dockerfile` (target: scheduler) | -- | Celery Beat periodic task scheduler |
| **dashboard** | `Dockerfile.dashboard` | 8501 | Streamlit interactive dashboard |
| **telegram-bot** | `Dockerfile.bot` | -- | Telegram bot (aiogram 3) |
| **ollama** | `ollama/ollama:latest` | 11434 | Local LLM inference server |

---

## API Documentation

The API is fully documented with OpenAPI 3.0. After starting the services:

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

### Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/overview/stats` | Dashboard overview statistics |
| `GET` | `/api/v1/niches/` | List all niches with summaries |
| `GET` | `/api/v1/niches/{id}` | Niche detail with top models/repos |
| `GET` | `/api/v1/models/` | List/search HuggingFace models |
| `GET` | `/api/v1/models/top` | Top models by downloads or growth |
| `GET` | `/api/v1/signals/` | List trend signals with filters |
| `GET` | `/api/v1/reports/` | List generated reports |
| `GET` | `/api/v1/reports/{id}` | Full report content |
| `GET` | `/health` | Liveness probe |

---

## Dashboard

The Streamlit dashboard provides 8 interactive pages:

| Page | Description |
|------|-------------|
| **Overview** | KPI cards, trend charts, top models, recent signals |
| **Niches** | Niche comparison table, growth heatmap, drill-down |
| **Models** | Searchable model table, download/growth charts, filters |
| **Research** | arXiv paper browser with category filters |
| **GitHub** | Repository tracker with star growth trends |
| **Signals** | Signal feed with severity filtering and acknowledgment |
| **Reports** | Generated report viewer with Markdown rendering |
| **Settings** | System configuration and collection status |

<!-- Screenshots will be added after first deployment -->

---

## Telegram Bot

Configure the bot by setting `TELEGRAM_BOT_TOKEN` in `.env` (get one from [@BotFather](https://t.me/BotFather)).

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and command list |
| `/report` | Full daily report |
| `/weekly` | Weekly report with AI insights |
| `/quick` | Quick summary: top models + signals |
| `/niches` | Niche overview table |
| `/niche <name>` | Detailed niche breakdown |
| `/top [N]` | Top N models by growth (default: 10) |
| `/signals` | Recent trend signals |
| `/signals critical` | Critical signals only |
| `/search <query>` | Search models by name or tag |
| `/model <model_id>` | Detailed model information |
| `/ai <question>` | Ask the LLM about trends |
| `/status` | System status and last collection info |
| `/collect` | Force data collection (admin only) |
| `/help` | Show command reference |

### Access Control

- `TELEGRAM_ALLOWED_USERS`: Comma-separated list of Telegram user IDs allowed to use the bot. Leave empty to allow all users.
- `TELEGRAM_ADMIN_USERS`: Comma-separated list of user IDs with admin privileges (e.g., `/collect` command).

---

## Development

### Local Setup (without Docker)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements/dev.txt

# Set up environment
cp .env.example .env
# Edit .env: point POSTGRES_HOST and REDIS to localhost

# Run the API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run the dashboard
streamlit run dashboard/app.py

# Run the Telegram bot
python -m bot.main

# Run Celery worker
celery -A app.tasks worker --loglevel=info
```

### Running Tests

```bash
make test           # or: docker compose exec api pytest tests/ -v
```

### Linting

```bash
make lint           # or: docker compose exec api ruff check app/ bot/
```

### Creating Database Migrations

```bash
make migrate-create msg="add new column"
# or: docker compose exec api alembic revision --autogenerate -m "add new column"
```

### Makefile Reference

| Target | Description |
|--------|-------------|
| `make setup` | Run interactive setup wizard |
| `make up` | Start all services |
| `make down` | Stop all services |
| `make logs` | Follow all logs |
| `make rebuild` | Rebuild and restart |
| `make collect` | Run data collection manually |
| `make seed` | Load demo data |
| `make status` | Show service status |
| `make shell` | Open shell in API container |
| `make db-shell` | Open PostgreSQL CLI |
| `make dev` | Start in development mode |
| `make dev-logs` | Follow dev logs |
| `make migrate` | Run database migrations |
| `make migrate-create` | Create new migration |
| `make test` | Run test suite |
| `make lint` | Run linter |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **API** | Python 3.11, FastAPI, Uvicorn, Pydantic v2 |
| **Database** | PostgreSQL 16, SQLAlchemy 2.0 (async), Alembic |
| **Task Queue** | Celery 5, Redis 7 |
| **Dashboard** | Streamlit, Plotly, Pandas |
| **Telegram Bot** | aiogram 3 |
| **LLM Inference** | Ollama (llama3.1:8b default) |
| **HTTP Clients** | httpx (async) |
| **Logging** | structlog |
| **Configuration** | pydantic-settings v2 |
| **Containerization** | Docker, Docker Compose |
| **Linting** | Ruff |
| **Testing** | pytest, pytest-asyncio |

---

## Project Structure

```
ai-trend-monitor/
├── app/                        # Core application
│   ├── api/                    # FastAPI routes and schemas
│   │   └── routes/             # Route modules (overview, models, niches, ...)
│   ├── analytics/              # Trend detection, niche classification, forecasting
│   ├── collectors/             # Data collectors (HuggingFace, GitHub, arXiv)
│   ├── models/                 # SQLAlchemy ORM models
│   ├── services/               # Business logic (collection, reporting, export)
│   ├── tasks/                  # Celery tasks and scheduler
│   ├── utils/                  # Shared helpers and rate limiter
│   ├── config.py               # pydantic-settings configuration
│   ├── database.py             # Async engine and session management
│   └── main.py                 # FastAPI application factory
├── bot/                        # Telegram bot
│   ├── handlers/               # Command handlers
│   ├── api_client.py           # HTTP client for the API
│   ├── formatters.py           # Message formatting
│   ├── keyboards.py            # Inline keyboard builders
│   └── main.py                 # Bot entry point
├── dashboard/                  # Streamlit dashboard
│   ├── pages/                  # Dashboard pages (01-08)
│   ├── components/             # Reusable chart and card components
│   ├── api_client.py           # HTTP client for the API
│   └── app.py                  # Streamlit entry point
├── scripts/                    # Utility scripts
│   ├── init_db.py              # Database initialization
│   ├── seed_demo_data.py       # Demo data generator
│   ├── run_collection.py       # Manual collection trigger
│   ├── healthcheck.py          # Docker healthcheck
│   └── ollama-entrypoint.sh    # Ollama container setup
├── tests/                      # Test suite
├── alembic/                    # Database migrations
├── requirements/               # Pip requirements files
├── docker-compose.yml          # Production compose file
├── docker-compose.dev.yml      # Development overrides
├── Dockerfile                  # Multi-stage API/worker/scheduler image
├── Dockerfile.bot              # Telegram bot image
├── Dockerfile.dashboard        # Streamlit dashboard image
├── Makefile                    # Developer convenience targets
├── setup.sh                    # Interactive setup wizard
├── .env.example                # Environment variable reference
└── pyproject.toml              # Python project metadata
```

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
