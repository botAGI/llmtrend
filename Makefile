.PHONY: setup up down logs rebuild collect seed status shell db-shell help dev dev-logs migrate migrate-create test lint

setup:
	chmod +x setup.sh
	./setup.sh

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

rebuild:
	docker compose up -d --build

collect:
	docker compose exec api python -m scripts.run_collection

seed:
	docker compose exec api python -m scripts.seed_demo_data

status:
	docker compose ps

shell:
	docker compose exec api bash

db-shell:
	docker compose exec postgres psql -U $${POSTGRES_USER:-monitor} $${POSTGRES_DB:-ai_trends}

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

dev-logs:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

migrate:
	docker compose exec api alembic upgrade head

migrate-create:
	docker compose exec api alembic revision --autogenerate -m "$(msg)"

test:
	docker compose exec api pytest tests/ -v

lint:
	docker compose exec api ruff check app/ bot/

help:
	@echo "Available targets:"
	@echo "  setup     - Run interactive setup wizard"
	@echo "  up        - Start all services"
	@echo "  down      - Stop all services"
	@echo "  logs      - Follow logs"
	@echo "  rebuild   - Rebuild and restart"
	@echo "  collect   - Run data collection manually"
	@echo "  seed      - Load demo data"
	@echo "  status    - Show service status"
	@echo "  shell     - Open shell in API container"
	@echo "  db-shell  - Open PostgreSQL CLI"
	@echo "  dev       - Start in development mode"
	@echo "  dev-logs  - Follow dev logs"
	@echo "  migrate   - Run database migrations"
	@echo "  test      - Run tests"
	@echo "  lint      - Run linter"
