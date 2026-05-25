.PHONY: up down logs dev test test-integration check migrate seed dream lint typecheck

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

dev:
	uv run uvicorn api.main:app --reload --port 8000 & uv run chainlit run ui/app.py --port 8001

test:
	uv run pytest tests/unit/ -v

test-integration:
	uv run pytest tests/integration/ -v

check: lint typecheck test

migrate:
	uv run alembic upgrade head

seed:
	uv run python scripts/seed_neo4j.py
	uv run python scripts/seed_pgvector.py

dream:
	uv run python scripts/run_dreaming.py

lint:
	uv run ruff check . --fix
	uv run ruff format .

typecheck:
	uv run mypy clinical_ai_shared clinical_ai_clinflow clinical_ai_memory clinical_ai_triage clinical_ai_pharma --strict
