# Project Instructions

## Database Migrations (Alembic)

This project uses Alembic for database migrations with async SQLAlchemy support.

### Prerequisites
- Docker containers must be running (`docker compose up -d`).
- `.env` file must be configured with a valid `DATABASE_URL` (starting with `postgresql+asyncpg://`).

### Running Migrations
To apply all pending migrations to the database:
```bash
uv run python -m alembic upgrade head
```
Or use the Makefile:
```bash
make migrate
```

### Creating New Migrations
When you modify the models in `packages/shared/src/clinical_ai_shared/db/models.py`, create a new migration:

1. **Autogenerate (Recommended):**
   ```bash
   uv run python -m alembic revision --autogenerate -m "description_of_changes"
   ```
   *Note: Always review the generated script in `migrations/versions/` before applying.*

2. **Manual Revision:**
   ```bash
   uv run python -m alembic revision -m "description_of_changes"
   ```

### Verification
To check if your local models are in sync with the database schema:
```bash
uv run python -m alembic check
```

### Troubleshooting
- **Access Denied:** On Windows, if `uv run alembic` fails with "Access is denied", use `uv run python -m alembic` instead.
- **Foreign Tables:** The migration environment is configured to ignore tables not defined in our `Base.metadata` (like LangFuse's internal tables). If you see unexpected "removed table" detections in `alembic check`, ensure the `include_object` function in `migrations/env.py` is correctly configured.
