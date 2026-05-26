# API Operations Guide

## Running the API
To start the FastAPI application during development:

```bash
# Ensure infrastructure is running
docker compose up -d

# Run using Python's uvicorn module (preferred on Windows/uv environments)
uv run python -m uvicorn api.main:app --reload --port 8000
```

## API Endpoints
- **Health (Liveness):** `GET /health` — Returns `{"status": "ok", "version": "0.1.0"}`
- **Readiness:** `GET /ready` — Returns 200 if Postgres, Neo4j, and Redis are reachable, else 503.
- **Documentation:** `GET /docs` — Swagger UI (enabled when `DEBUG=True`)

## Development Requirements
- **Environment:** Ensure `.env` is configured (contains `DEBUG=True`, `LOG_LEVEL=DEBUG`, and valid service URIs).
- **PYTHONPATH:** If you encounter import errors, ensure the project root or `packages/shared/src` is in your `PYTHONPATH`.
- **Port:** The service runs on port 8000 by default. Ensure no other process is using this port.
