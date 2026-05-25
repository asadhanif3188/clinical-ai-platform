# BUILD-PLAYBOOK.md — Clinical AI Platform

A sequential prompt guide for building this platform using Claude Code.
Each task contains a ready-to-paste prompt and a checkbox to track progress.

**Reference documents (read before starting):**
- [`CLAUDE.md`](CLAUDE.md) — coding conventions, patterns, what NOT to do
- [`PRD.md`](PRD.md) — product requirements, acceptance criteria, data models
- [`../../18.implementation-plan-category6-clinical-ai.md`](../../18.implementation-plan-category6-clinical-ai.md) — full implementation plan with schemas, graph designs, API specs

**How to use this file:**
1. Work through tasks in order — each phase depends on the previous
2. Paste the prompt into Claude Code at the root of `clinical-ai-platform/`
3. Verify the "Done when" criteria before marking complete
4. Mark done by changing `[ ]` to `[x]`
5. Never skip a task — every task has downstream dependencies

---

## Progress Overview

### Phase 0 — Scaffold & Shared Infrastructure
- [ ] 0.1 Monorepo + uv workspace
- [ ] 0.2 Docker Compose (all services)
- [ ] 0.3 Shared config (Pydantic Settings)
- [ ] 0.4 Database clients (PostgreSQL, pgvector, Neo4j, Redis)
- [ ] 0.5 Alembic migrations (initial schema)
- [ ] 0.6 Shared Pydantic schemas
- [ ] 0.7 Structured logging
- [ ] 0.8 FastAPI skeleton + health endpoints
- [ ] 0.9 Test infrastructure (conftest.py)
- [ ] 0.10 Ruff + mypy + pre-commit

### Phase 1 — ClinFlow AI (Orchestration Engine)
- [ ] 1.1 YAML workflow definition + parser
- [ ] 1.2 Workflow execution engine
- [ ] 1.3 LangGraph graph builder from YAML
- [ ] 1.4 Dynamic routing logic
- [ ] 1.5 Checkpoint persistence (PostgreSQL)
- [ ] 1.6 Recovery from checkpoint
- [ ] 1.7 Human approval gateway
- [ ] 1.8 Audit trail engine
- [ ] 1.9 Workflow analytics
- [ ] 1.10 ClinFlow API endpoints
- [ ] 1.11 ClinFlow tests

### Phase 2 — ClinicalTriage AI (Document Pipeline)
- [ ] 2.1 PDF parsing tool (+ OCR fallback)
- [ ] 2.2 Intake Agent (classification)
- [ ] 2.3 Lab Report Extraction Agent
- [ ] 2.4 Clinical Note Extraction Agent
- [ ] 2.5 Trial Summary Extraction Agent
- [ ] 2.6 Validation Agent (schema + RAG)
- [ ] 2.7 Report Generation Agent
- [ ] 2.8 Clinical knowledge RAG tool
- [ ] 2.9 ICD-10 lookup tool
- [ ] 2.10 LangGraph triage pipeline + state
- [ ] 2.11 Triage workflow YAML (ClinFlow)
- [ ] 2.12 Triage API endpoints
- [ ] 2.13 Golden test sets (synthetic documents)
- [ ] 2.14 Triage unit + integration + eval tests

### Phase 3 — 5-Layer Memory System
- [ ] 3.1 Working memory
- [ ] 3.2 Episodic memory (date-stamped logs)
- [ ] 3.3 Long-term memory — pgvector
- [ ] 3.4 Long-term memory — Neo4j graph
- [ ] 3.5 Procedural memory (extraction templates)
- [ ] 3.6 Index layer (BM25 + vector dual-channel)
- [ ] 3.7 Light Sleep (scan + deduplicate)
- [ ] 3.8 REM Sleep (reflect + extract patterns)
- [ ] 3.9 Deep Sleep (score + promote)
- [ ] 3.10 Forgetting curve
- [ ] 3.11 Dreaming orchestrator
- [ ] 3.12 Dreaming cron script + K8s CronJob
- [ ] 3.13 Memory integration into triage pipeline
- [ ] 3.14 Memory API endpoints
- [ ] 3.15 Memory tests

### Phase 4 — PharmaSafe AI (Drug Interaction Checker)
- [ ] 4.1 RxNorm normalization tool
- [ ] 4.2 OpenFDA API client (+ Redis cache)
- [ ] 4.3 Input Processing Agent
- [ ] 4.4 Drug Interaction Checker Agent
- [ ] 4.5 Literature Retrieval Agent
- [ ] 4.6 Cross-Validation Agent
- [ ] 4.7 Risk Assessment Report Generator
- [ ] 4.8 Neo4j drug knowledge graph seed
- [ ] 4.9 Knowledge graph multi-hop query tool
- [ ] 4.10 LangGraph pharma pipeline + state
- [ ] 4.11 Pharma workflow YAML (ClinFlow)
- [ ] 4.12 Pharma API endpoints
- [ ] 4.13 Golden test sets (drug interaction lists)
- [ ] 4.14 Pharma unit + integration + eval tests

### Phase 5 — Model Routing, Observability, Evaluation
- [ ] 5.1 Model routing layer (Opus / Haiku / local)
- [ ] 5.2 Fallback chain + circuit breaker
- [ ] 5.3 Cost tracking per request/workflow
- [ ] 5.4 LangFuse tracing integration
- [ ] 5.5 Prometheus metrics
- [ ] 5.6 Extraction evaluation (F1 against golden sets)
- [ ] 5.7 Interaction evaluation (accuracy against golden sets)
- [ ] 5.8 Evaluation CI job (GitHub Actions)

### Phase 6 — UI, Deployment, CI/CD
- [ ] 6.1 Chainlit: document upload handler
- [ ] 6.2 Chainlit: extraction review + HITL approval actions
- [ ] 6.3 Chainlit: drug checker handler
- [ ] 6.4 Chainlit: workflow monitor
- [ ] 6.5 Chainlit: audit explorer
- [ ] 6.6 Chainlit: memory inspector
- [ ] 6.7 Chainlit: analytics dashboard
- [ ] 6.8 Next.js upgrade path scaffold (ui-next/)
- [ ] 6.9 Production Dockerfile (multi-stage)
- [ ] 6.10 Kubernetes manifests
- [ ] 6.11 GitHub Actions: CI pipeline (lint + type + unit tests)
- [ ] 6.12 GitHub Actions: integration + eval pipeline
- [ ] 6.13 GitHub Actions: deploy pipeline
- [ ] 6.14 Deployment documentation

---

## Phase 0 — Project Scaffold & Shared Infrastructure

**Goal:** `docker-compose up -d` starts all services. `uv run uvicorn api.main:app` starts the API. `GET /health` returns `{"status": "ok"}`.

---

### Task 0.1 — Monorepo + uv Workspace
- [ ] Done

**Prompt:**
```
Read CLAUDE.md and PRD.md in the current directory first.

Create the complete monorepo scaffold for the clinical-ai-platform project using uv workspace.

Create the following:

1. Root `pyproject.toml` with:
   - uv workspace config listing all 5 packages (shared, clinflow, memory, triage, pharma)
   - uv.sources for local package references
   - All production dependencies with versions from CLAUDE.md tech stack section
   - Dev dependencies: pytest, pytest-asyncio, pytest-cov, pytest-mock, mypy, ruff, pre-commit
   - [tool.ruff] config: line-length=100, target-version="py312", select=["E","F","I","UP","B","SIM","TCH"]
   - [tool.mypy] config: strict=true, python_version="3.12"
   - [tool.pytest.ini_options]: asyncio_mode="auto", testpaths=["tests"]

2. Each package's `pyproject.toml` under packages/{shared,clinflow,memory,triage,pharma}/

3. Empty `__init__.py` files for each package's src layout

4. `.python-version` containing "3.12"

5. `.env.example` with all variables listed in the CLAUDE.md Environment Variables section

6. `.gitignore` covering: .env, __pycache__, .mypy_cache, .ruff_cache, *.pyc, data/episodic_logs/*, *.egg-info, .venv, dist/

7. `README.md` with: project name, one-line description, architecture diagram (ASCII), quickstart (docker compose up, uv sync, uv run uvicorn), and links to PRD.md and CLAUDE.md

After creating files, verify: `uv sync` would succeed by checking that all package references are resolvable.
```

**Done when:**
- `uv sync` installs without errors
- `from clinical_ai_shared.config import Settings` works in a Python REPL
- All 5 packages importable

---

### Task 0.2 — Docker Compose
- [ ] Done

**Prompt:**
```
Read CLAUDE.md in the current directory.

Create `docker-compose.yml` that starts all infrastructure services needed by the clinical-ai-platform:

Services required:
1. **postgres** — PostgreSQL 16 with pgvector extension
   - Image: pgvector/pgvector:pg16
   - Port: 5432
   - Env: POSTGRES_USER=postgres, POSTGRES_PASSWORD=postgres, POSTGRES_DB=clinical_ai
   - Volume: postgres_data:/var/lib/postgresql/data
   - Healthcheck: pg_isready

2. **neo4j** — Neo4j 5
   - Image: neo4j:5
   - Ports: 7474 (HTTP browser), 7687 (Bolt)
   - Env: NEO4J_AUTH=neo4j/password123, NEO4J_PLUGINS=["apoc"]
   - Volume: neo4j_data:/data
   - Healthcheck: cypher-shell ping

3. **redis** — Redis 7
   - Image: redis:7-alpine
   - Port: 6379
   - Volume: redis_data:/data
   - Healthcheck: redis-cli ping

4. **langfuse** — Self-hosted LangFuse
   - Image: langfuse/langfuse:latest
   - Port: 3000
   - Env: DATABASE_URL pointing to postgres service, NEXTAUTH_SECRET, SALT
   - Depends on: postgres

Also create `docker-compose.prod.yml` with production overrides:
- No exposed ports for internal services (only API and UI exposed)
- Resource limits per service
- Restart policies: unless-stopped

Create a `Makefile` with these targets:
- `make up` — docker-compose up -d
- `make down` — docker-compose down
- `make logs` — docker-compose logs -f
- `make dev` — start API + UI in dev mode
- `make test` — run unit tests
- `make test-integration` — run integration tests
- `make check` — ruff + mypy + unit tests (run before every commit)
- `make migrate` — alembic upgrade head
- `make seed` — run all seed scripts
- `make dream` — python scripts/run_dreaming.py
- `make lint` — ruff check . --fix && ruff format .
- `make typecheck` — mypy packages/ api/ --strict
```

**Done when:**
- `make up` starts all 4 services
- All healthchecks pass within 60 seconds
- Neo4j browser accessible at localhost:7474
- LangFuse UI accessible at localhost:3000

---

### Task 0.3 — Shared Config (Pydantic Settings)
- [ ] Done

**Prompt:**
```
Read CLAUDE.md — specifically the Configuration section and Environment Variables section.

Create `packages/shared/src/clinical_ai_shared/config.py` with a Pydantic Settings class.

Requirements:
- Use pydantic-settings BaseSettings with model_config = {"env_file": ".env"}
- Include all variables from CLAUDE.md Environment Variables section
- Group settings logically with properties: anthropic, database, neo4j, redis, langfuse, local_model, notifications
- Add a computed property `is_phi_safe_configured` that returns True only if PHI_MODEL and OLLAMA_BASE_URL are both set
- Add validators: DATABASE_URL must start with "postgresql+asyncpg://", REDIS_URL must start with "redis://"
- Export a module-level singleton: `settings = Settings()` with a try/except that prints a clear error if .env is missing
- Add a `get_settings()` function for use with FastAPI Depends() for testability (can be overridden in tests)

Also create `packages/shared/src/clinical_ai_shared/__init__.py` that exports `settings` and `get_settings`.

Write a unit test in `tests/unit/test_config.py` that:
- Tests all required fields raise ValidationError when missing
- Tests the is_phi_safe_configured computed property
- Tests URL validators
Use pytest with monkeypatch to set env vars — do not read from .env in tests.
```

**Done when:**
- `from clinical_ai_shared.config import settings` works
- Unit tests pass
- `mypy packages/shared` passes

---

### Task 0.4 — Database Clients
- [ ] Done

**Prompt:**
```
Read CLAUDE.md — specifically the "Database: Always Use Async Sessions" pattern and the Architecture Patterns section.

Create the following async database client modules in `packages/shared/src/clinical_ai_shared/db/`:

1. `postgres.py` — Async SQLAlchemy engine
   - create_async_engine using settings.DATABASE_URL
   - AsyncSessionLocal factory
   - get_async_session() async generator for FastAPI Depends()
   - Base = DeclarativeBase() for all ORM models
   - init_db() function that creates all tables

2. `pgvector.py` — Vector store operations
   - Async functions: embed_and_store(text, metadata) → str (entry_id)
   - search(query_text, top_k=5, filter_metadata=None) → list[VectorSearchResult]
   - delete(entry_id) → bool
   - VectorSearchResult: entry_id, content, score, metadata
   - Use sentence-transformers for local embeddings (model: "all-MiniLM-L6-v2")
   - Never use OpenAI embeddings — data must not leave VPC

3. `neo4j.py` — Neo4j async driver wrapper
   - get_driver() that returns an AsyncDriver singleton
   - execute_query(cypher, params) → list[dict]
   - close_driver()
   - Context manager support: async with neo4j_session() as session

4. `redis.py` — Redis client
   - get_redis() returning a Redis client singleton
   - cache_get(key) / cache_set(key, value, ttl_seconds)
   - publish(channel, message) / subscribe(channel)

Each module must:
- Use settings from clinical_ai_shared.config
- Log connection events with structured logging
- Handle connection errors gracefully with retry logic (tenacity)
- Close connections on app shutdown (register with lifespan events)
```

**Done when:**
- All 4 modules importable
- Each has a smoke test in `tests/unit/` that mocks the external connection and verifies the interface
- `mypy` passes on all 4 files

---

### Task 0.5 — Alembic Migrations
- [ ] Done

**Prompt:**
```
Read PRD.md section 11 (Data Models) for the complete schema.

Set up Alembic for database migrations and create the initial migration set.

1. Initialize Alembic in `migrations/` with async SQLAlchemy support
   - Update `migrations/env.py` to use asyncio + settings.DATABASE_URL
   - Import Base from clinical_ai_shared.db.postgres

2. Create SQLAlchemy ORM models in `packages/shared/src/clinical_ai_shared/db/models.py`:
   - WorkflowRun: id (UUID PK), workflow_name, status, current_node, checkpoint (JSONB), started_at, updated_at
   - AuditLogEntry: id (UUID PK), run_id (FK), agent, node, input_hash, output_summary, model_used, tokens_used, cost_usd, duration_ms, timestamp, human_decision, human_reviewer. Table constraint: no UPDATE or DELETE allowed (enforce via trigger).
   - LongTermMemoryEntry: id (UUID PK), content, embedding (vector(384)), importance_score, created_at, last_accessed, access_count, source_sessions (ARRAY)
   - ProceduralTemplate: id (UUID PK), document_type, format_fingerprint, extraction_hints (JSONB), success_rate, last_updated
   - All timestamps in UTC

3. Create migration versions:
   - 001_initial_schema.py — WorkflowRun table
   - 002_audit_trail.py — AuditLogEntry table + append-only trigger
   - 003_memory_tables.py — LongTermMemoryEntry (with pgvector index), ProceduralTemplate
   - 004_workflow_state.py — indexes on WorkflowRun(status), WorkflowRun(workflow_name)

Run `alembic check` to verify migrations are consistent with models.
```

**Done when:**
- `make migrate` runs all migrations without error on the Docker Compose postgres
- pgvector extension is enabled (migration enables it if not present)
- AuditLogEntry append-only trigger is verified: UPDATE and DELETE raise exceptions

---

### Task 0.6 — Shared Pydantic Schemas
- [ ] Done

**Prompt:**
```
Read PRD.md section 11 (Data Models) completely. Read CLAUDE.md — the Pydantic v2 requirement.

Create all shared Pydantic v2 schemas in `packages/shared/src/clinical_ai_shared/schemas/`:

1. `documents.py` — DocumentType enum, DocumentInput, ExtractionResult, ProvenanceRecord, ConfidenceScore
2. `validation.py` — ValidationStatus enum, ValidationResult, ValidationFeedback
3. `memory.py` — EpisodicEntry, LongTermEntry, ProceduralTemplate, ConsolidationStats, MemorySearchResult
4. `workflow.py` — WorkflowState, WorkflowDefinition, NodeDefinition, EdgeDefinition, NodeResult
5. `audit.py` — AuditLogEntry, AuditQuery, AuditExportRequest
6. `pharma.py` — MedicationInput, NormalizedMedication, DrugInteraction, InteractionSeverity enum (CRITICAL/HIGH/MODERATE/LOW), RiskAssessmentReport
7. `common.py` — AgentIdentity, ProvenanceRecord, ConfidenceScore, PaginatedResponse

Requirements for all schemas:
- Pydantic v2 syntax (model_config, field_validator, model_validator)
- All datetimes timezone-aware UTC
- UUIDs as uuid.UUID type, not str
- Enums as str enums for JSON serialisation
- model_json_schema() must be usable as Claude tool_use input_schema
- Every schema has at least one example in model_config["json_schema_extra"]

Create `packages/shared/src/clinical_ai_shared/schemas/__init__.py` that exports all schemas.

Write `tests/unit/test_schemas.py` that round-trips every schema through serialise/deserialise.
```

**Done when:**
- All schemas importable from `clinical_ai_shared.schemas`
- Round-trip tests pass
- `mypy` passes

---

### Task 0.7 — Structured Logging
- [ ] Done

**Prompt:**
```
Read CLAUDE.md — specifically the Observability Conventions section and the "Never use print()" rule.

Create `packages/shared/src/clinical_ai_shared/observability/logging.py`:

Requirements:
- Use structlog for structured JSON logging
- get_logger(name) returns a bound logger
- Every log entry automatically includes: timestamp (ISO 8601 UTC), level, module, correlation_id
- correlation_id is a UUID set per HTTP request via middleware and stored in contextvars
- Log levels configurable via settings.LOG_LEVEL (default: INFO)
- In development (settings.DEBUG=True): pretty-print with colours
- In production: JSON output only

Create `packages/shared/src/clinical_ai_shared/observability/middleware.py`:
- CorrelationIdMiddleware for FastAPI — generates UUID per request, stores in contextvar, adds X-Correlation-ID response header
- RequestLoggingMiddleware — logs method, path, status_code, duration_ms for every request

Write one unit test in `tests/unit/test_logging.py` that verifies:
- get_logger() returns a logger
- Log output includes correlation_id when set
- JSON format is valid JSON
```

**Done when:**
- `from clinical_ai_shared.observability.logging import get_logger` works
- Middleware importable
- Unit test passes

---

### Task 0.8 — FastAPI Skeleton + Health Endpoints
- [ ] Done

**Prompt:**
```
Read CLAUDE.md and PRD.md section 10 (API Surface) — specifically the /health and /ready endpoints.

Create the FastAPI application in `api/`:

1. `api/main.py` — app factory
   - FastAPI app with title, description, version from settings
   - Lifespan context manager: init DB on startup, close connections on shutdown
   - Mount all routers (health for now, others added later)
   - Add CorrelationIdMiddleware and RequestLoggingMiddleware
   - Add CORS middleware (configurable origins from settings)
   - OpenAPI docs at /docs (disable in production via settings)

2. `api/routers/health.py`
   - GET /health → {"status": "ok", "version": "0.1.0"} — always 200, no DB checks
   - GET /ready → checks all connections (PostgreSQL, Neo4j, Redis) — 200 if all healthy, 503 if any fail. Include per-service status in response body.

3. `api/dependencies.py`
   - get_session: AsyncSession via get_async_session()
   - get_settings: Settings via get_settings()
   - Pagination: PageParams(page: int = 1, page_size: int = 20)

4. `api/middleware.py`
   - Re-export CorrelationIdMiddleware and RequestLoggingMiddleware from shared

Verify: `uv run uvicorn api.main:app --reload` starts without errors. `curl localhost:8000/health` returns 200.
```

**Done when:**
- `GET /health` → 200
- `GET /ready` → 200 when Docker services are running, 503 when they are not
- `/docs` shows Swagger UI
- No mypy errors

---

### Task 0.9 — Test Infrastructure
- [ ] Done

**Prompt:**
```
Read CLAUDE.md — specifically the Testing Rules section and the unit test mock pattern.

Create `tests/conftest.py` with shared pytest fixtures:

1. `event_loop` — session-scoped asyncio event loop
2. `mock_anthropic` — patches anthropic.AsyncAnthropic to return configurable mock responses. Include a helper `build_mock_tool_response(tool_name, tool_input)` that builds a valid Anthropic tool_use response dict.
3. `mock_settings` — overrides settings with test values (test DB URL, fake API keys)
4. `db_session` — async SQLAlchemy session connected to a test database (use a separate test DB or SQLite for unit tests)
5. `redis_mock` — in-memory fakeredis instance
6. `sample_lab_report_state` — returns a populated TriageState-like dict for testing extraction agents
7. `sample_medication_list` — returns a list of MedicationInput for testing pharma agents

Create `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/evaluation/__init__.py`

Create `tests/unit/test_conftest.py` with a smoke test that verifies all fixtures work without error.

Add to pyproject.toml [tool.pytest.ini_options]:
- markers for slow, integration, evaluation tests
- filterwarnings to suppress known deprecation warnings
```

**Done when:**
- `uv run pytest tests/unit/test_conftest.py -v` passes
- All fixtures are importable and functional
- No asyncio warnings

---

### Task 0.10 — Ruff + mypy + pre-commit
- [ ] Done

**Prompt:**
```
Set up code quality tooling for the clinical-ai-platform monorepo.

1. Create `.pre-commit-config.yaml` with hooks:
   - ruff (lint + format) — runs on staged Python files
   - mypy — runs on staged Python files in packages/ and api/
   - trailing-whitespace, end-of-file-fixer, check-yaml, check-toml

2. Verify `pyproject.toml` has correct [tool.ruff] and [tool.mypy] config (from Task 0.1).
   Add to mypy config:
   - per-module ignores for packages that lack stubs (neo4j, langfuse)
   - plugins = ["pydantic.mypy"]

3. Create `Makefile` target `make check` that runs in sequence:
   ruff check . → ruff format --check . → mypy packages/ api/ --strict → pytest tests/unit/ -q

4. Run `pre-commit install` instructions in README.md setup section.

5. Fix any existing mypy or ruff errors in the files created so far.

Run `make check` and verify it passes cleanly on the current codebase.
```

**Done when:**
- `make check` exits 0
- `pre-commit run --all-files` passes
- No ruff errors, no mypy errors in packages/ and api/

---

## Phase 1 — ClinFlow AI (Orchestration Engine)

**Goal:** A workflow defined in YAML can be executed with checkpointing, human approval gates, and an immutable audit trail.

---

### Task 1.1 — YAML Workflow Definition + Parser
- [ ] Done

**Prompt:**
```
Read CLAUDE.md and the workflow YAML format in 18.implementation-plan-category6-clinical-ai.md (Section 5, Phase 1).

Create the workflow definition system in `packages/clinflow/src/clinical_ai_clinflow/`:

1. `definitions.py` — Pydantic v2 models:
   - NodeType: Literal["agent", "human_gateway"]
   - RetryConfig(max_attempts: int, backoff_seconds: int)
   - NotificationConfig(channel: str, message: str)
   - NodeDefinition(id, agent, type, timeout_seconds, retry, notification)
   - EdgeDefinition(from_node, to_node, condition: str | None, max_loops: int = 3)
   - StateFieldDefinition(name, type_hint: str, nullable: bool)
   - WorkflowDefinition(name, version, description, state_schema, nodes, edges)
   - Validator: node IDs referenced in edges must exist in nodes list
   - Validator: no dangling edges, at least one terminal node (no outgoing edges)

2. `loader.py` — YAML loading:
   - load_workflow(path: Path) → WorkflowDefinition
   - load_workflow_from_string(yaml_str: str) → WorkflowDefinition
   - list_workflows(directory: Path) → list[WorkflowDefinition]

3. Create `packages/clinflow/src/clinical_ai_clinflow/workflows/_template.yml` — the template from the implementation plan

4. Write `tests/unit/test_workflow_parser.py`:
   - Test valid YAML parses correctly
   - Test missing required fields raises ValidationError
   - Test dangling edge raises ValidationError
   - Test circular dependency detected
```

**Done when:**
- Template YAML parses without error
- Validation tests pass
- `mypy` passes

---

### Task 1.2 — Workflow Execution Engine
- [ ] Done

**Prompt:**
```
Read CLAUDE.md — the LangGraph Conventions section. Read the WorkflowDefinition schema from Task 1.1.

Create `packages/clinflow/src/clinical_ai_clinflow/engine.py`:

The WorkflowEngine class:
- `__init__(self, workflow_def: WorkflowDefinition, agent_registry: dict[str, Callable], checkpointer)`
  - agent_registry maps agent name (str) → async callable that takes state dict and returns state dict
- `async run(initial_state: dict, run_id: str | None = None) → WorkflowResult`
  - Generates a run_id (UUID) if not provided
  - Executes nodes in workflow order
  - At each node: call the agent, evaluate outgoing edge conditions, route to next node
  - Persists checkpoint after every node (delegates to checkpointer)
  - Pauses at human_gateway nodes (raises HumanGatewayPause exception with run_id + context)
  - Writes audit entry after every node
  - Returns WorkflowResult(run_id, final_state, audit_entries, total_cost_usd, duration_ms)
- `async resume(run_id: str, decision: HumanDecision) → WorkflowResult`
  - Load checkpoint for run_id
  - Apply human decision (approved/rejected + optional edits to state)
  - Continue execution from the human_gateway node's outgoing edges

Also create:
- `WorkflowResult` dataclass
- `HumanGatewayPause` exception with run_id, node_id, context_for_reviewer
- `HumanDecision` dataclass with decision ("approved"/"rejected"), reviewer_id, edits (optional state overrides)

The engine must NOT know about specific agents — it only calls whatever is in agent_registry.
```

**Done when:**
- Unit test: 3-node workflow with mocked agents executes in correct order
- Unit test: HumanGatewayPause raised at correct node
- Unit test: resume() continues from correct node after approval
- `mypy --strict` passes

---

### Task 1.3 — LangGraph Graph Builder from YAML
- [ ] Done

**Prompt:**
```
Read CLAUDE.md — the LangGraph Conventions section and the graph.py pattern example.

Create `packages/clinflow/src/clinical_ai_clinflow/graph.py`:

`build_graph(workflow_def: WorkflowDefinition, agent_registry: dict, checkpointer) → CompiledGraph`

This function converts a WorkflowDefinition into a LangGraph StateGraph:

1. Dynamically build a TypedDict class from workflow_def.state_schema fields (use `type()` to construct it at runtime)

2. Create a StateGraph with the dynamic TypedDict

3. For each NodeDefinition in workflow_def.nodes:
   - If type == "agent": add a node that calls agent_registry[node.agent](state)
   - If type == "human_gateway": add a node that is listed in interrupt_before

4. For each EdgeDefinition:
   - If no condition: add_edge(from, to)
   - If condition string: compile the condition into a routing function using a safe expression evaluator
     - Condition format: "state.field == 'value'" or "state.confidence > 0.7"
     - Use a whitelist evaluator — only allow comparisons, boolean ops, attribute access
     - Never use eval() — use ast.literal_eval with a custom node visitor

5. Set entry point to the first node (no incoming edges)

6. Compile with checkpointer and interrupt_before=[human_gateway node ids]

Write a test that builds a graph from the _template.yml workflow and verifies it is a CompiledGraph.
```

**Done when:**
- _template.yml workflow compiles to a runnable LangGraph graph
- Condition evaluator rejects unsafe expressions (test: `"__import__('os')"` raises SecurityError)
- `mypy` passes

---

### Task 1.4 — Checkpoint Persistence
- [ ] Done

**Prompt:**
```
Read CLAUDE.md — the async database pattern. Read the WorkflowRun ORM model from Task 0.5.

Create `packages/clinflow/src/clinical_ai_clinflow/checkpoint.py`:

PostgresCheckpointer class that implements LangGraph's BaseCheckpointSaver interface:

- `async aget(config)` — load checkpoint for run_id from WorkflowRun table. Deserialise JSONB checkpoint column.
- `async aput(config, checkpoint, metadata, new_versions)` — upsert checkpoint state into WorkflowRun table.
- `async alist(config, *, filter, before, limit)` — list checkpoints for a run_id
- Use the async SQLAlchemy session from shared.db.postgres
- Checkpoint payload: full LangGraph state dict serialised to JSON. Store as JSONB.
- Update WorkflowRun.status, current_node, and updated_at on every save.

Create `packages/clinflow/src/clinical_ai_clinflow/recovery.py`:
- `async resume_from_checkpoint(run_id: str, engine: WorkflowEngine) → WorkflowResult`
  - Load checkpoint from PostgresCheckpointer
  - Rebuild workflow engine with saved state
  - Continue execution

Write `tests/integration/test_checkpoint_recovery.py`:
- Start a 5-node workflow
- After node 3, kill the execution (simulate crash with exception)
- Verify checkpoint was saved with current_node = "node_3"
- Call resume_from_checkpoint
- Verify workflow completes from node 4, not node 1
```

**Done when:**
- Integration test passes (requires Docker Compose postgres)
- Checkpoint survives process restart (verified by separate test process)
- `mypy` passes

---

### Task 1.5 — Human Approval Gateway
- [ ] Done

**Prompt:**
```
Read CLAUDE.md. Read the HumanGatewayPause and HumanDecision types from Task 1.2.
Read PRD.md FR-5.3 (resume within 60 seconds of approval decision).

Create `packages/clinflow/src/clinical_ai_clinflow/human_gateway.py`:

HumanGatewayService class:
- `async pause(run_id, node_id, context: dict, workflow_name: str)`:
  - Save pending review record to PostgreSQL (table: human_reviews)
  - Send notification via configured channel (Slack webhook or email)
  - Notification includes: run_id, workflow_name, node_id, summary of context, approve/reject URL
  - Return immediately — do NOT block

- `async submit_decision(run_id: str, decision: HumanDecision) → None`:
  - Validate run_id has a pending review
  - Store decision (approved/rejected, reviewer_id, edits, timestamp)
  - Publish to Redis channel "workflow:{run_id}:decision" so the waiting workflow can continue

- `async wait_for_decision(run_id: str, timeout_seconds: int = 3600) → HumanDecision`:
  - Subscribe to Redis channel for this run_id
  - Return decision when received, raise TimeoutError if timeout exceeded

Create migration `005_human_reviews.py`:
- human_reviews table: run_id, node_id, workflow_name, context (JSONB), status (pending/approved/rejected), reviewer_id, decision_at, created_at

Create `api/routers/approvals.py`:
- POST /api/v1/approvals/{run_id}/approve — body: {reviewer_id, edits: dict | null}
- POST /api/v1/approvals/{run_id}/reject — body: {reviewer_id, reason: str}
- GET /api/v1/approvals/pending — list all pending reviews

Write `tests/integration/test_human_gateway.py`:
- Start workflow, hit human_gateway node, verify it pauses
- Call approve endpoint, verify workflow resumes and completes
- Call reject endpoint, verify workflow routes to rejection path
```

**Done when:**
- Integration tests pass
- Slack/email notification fires (verify via webhook mock in tests)
- Pending reviews queryable via API

---

### Task 1.6 — Audit Trail Engine
- [ ] Done

**Prompt:**
```
Read CLAUDE.md — specifically "Never skip audit logging in agent nodes" and the AuditLogEntry schema.
Read PRD.md FR-7 (all 4 audit requirements).

Create `packages/clinflow/src/clinical_ai_clinflow/audit.py`:

AuditTrailWriter class:
- `async write(entry: AuditLogEntry) → None`
  - INSERT into audit_log_entries table (append-only — no UPDATE/DELETE)
  - Use input_hash (SHA-256 of serialised input) not raw input for privacy
  - If write fails: log error at CRITICAL level, do NOT swallow — audit failures must be visible

- `async query(run_id: str | None, agent: str | None, start_dt: datetime | None, end_dt: datetime | None, page: int, page_size: int) → PaginatedResponse[AuditLogEntry]`

- `async export_csv(query_params) → io.StringIO`
  - Stream audit entries as CSV with headers matching AuditLogEntry fields

Also write a standalone `write_audit_entry(...)` coroutine function that agents call directly (convenience wrapper around AuditTrailWriter).

Create `api/routers/audit.py`:
- GET /api/v1/audit — query with filters
- GET /api/v1/audit/{entry_id} — single entry
- GET /api/v1/audit/export — CSV download

Write `tests/unit/test_audit_writer.py`:
- Verify append-only: attempt UPDATE/DELETE raises exception
- Verify input_hash is SHA-256 of input, not raw input stored
- Verify CSV export contains correct headers and row count
```

**Done when:**
- Audit entries written correctly in integration workflow runs
- CSV export works end-to-end
- Append-only constraint verified by test

---

### Task 1.7 — ClinFlow API Endpoints + Tests
- [ ] Done

**Prompt:**
```
Read PRD.md section 10 (API Surface) — ClinFlow AI endpoints.
Read CLAUDE.md — API key auth middleware requirement.

Create `api/routers/workflows.py` with all ClinFlow endpoints:
- GET  /api/v1/workflows — list all workflow definitions (name, version, description)
- GET  /api/v1/workflows/{name} — full workflow definition + JSON schema
- GET  /api/v1/workflows/runs — list active and recent runs (paginated, filter by status)
- GET  /api/v1/workflows/runs/{run_id} — status, current_node, checkpoint summary, elapsed time
- POST /api/v1/workflows/runs/{run_id}/resume — resume paused workflow with HumanDecision body

Add API key authentication middleware to `packages/shared/src/clinical_ai_shared/auth/middleware.py`:
- Reads X-API-Key header
- Validates against settings.API_KEYS (comma-separated list)
- Returns 401 if missing or invalid
- Skip auth for /health and /ready

Mount the middleware in api/main.py.

Write unit tests in `tests/unit/test_workflows_router.py` using FastAPI TestClient:
- GET /workflows returns list of workflow definitions
- GET /workflows/runs/{invalid_id} returns 404
- POST /workflows/runs/{id}/resume with invalid decision returns 422
- Missing API key returns 401

Write `tests/integration/test_clinflow_end_to_end.py`:
- Define a simple 3-node test workflow (no real agents — use mock agents)
- Execute via API
- Verify it completes and audit trail has 3 entries
```

**Done when:**
- All endpoints return correct status codes and response schemas
- Auth middleware rejects requests without valid API key
- Integration test runs full workflow via API

---

## Phase 2 — ClinicalTriage AI (Document Pipeline)

**Goal:** POST a PDF to /api/v1/triage/submit. Receive a structured extraction report with provenance tracking and a full audit trail.

---

### Task 2.1 — PDF Parsing Tool
- [ ] Done

**Prompt:**
```
Create `packages/triage/src/clinical_ai_triage/tools/pdf_parser.py`:

`parse_pdf(file_path: Path | bytes) → ParsedDocument`

ParsedDocument:
- document_id: str
- pages: list[ParsedPage]
- total_pages: int
- metadata: dict (author, created_at, title if available)

ParsedPage:
- page_number: int (1-indexed)
- text: str — extracted text
- tables: list[list[list[str]]] — detected tables as row/cell arrays
- has_images: bool

Requirements:
- Use PyMuPDF (fitz) as primary extractor
- If a page has less than 50 characters of text (likely scanned), fall back to OCR via pytesseract
- Preserve page structure: use page.get_text("blocks") for layout-aware extraction
- Extract tables using pdfplumber (more reliable for tables than PyMuPDF)
- Return clean text: strip headers/footers patterns, normalise whitespace
- Handle encrypted PDFs: return an error ParsedDocument with error_message field

Create `packages/triage/src/clinical_ai_triage/tools/__init__.py`

Write `tests/unit/test_pdf_parser.py`:
- Test with a minimal synthetic PDF (use reportlab or fpdf2 to create in-memory)
- Test OCR fallback path is triggered when text is sparse
- Test encrypted PDF returns error gracefully
```

**Done when:**
- Parses a multi-page PDF and returns structured pages
- OCR fallback works for scanned content
- Unit tests pass

---

### Task 2.2 — Intake Agent (Document Classification)
- [ ] Done

**Prompt:**
```
Read CLAUDE.md — specifically "Agents: Always Use Claude Tool Use, Never Plain Text Parsing" and "Model Routing: Always Go Through the Router".

Create `packages/triage/src/clinical_ai_triage/agents/intake.py` and `packages/triage/src/clinical_ai_triage/prompts/intake.md`.

The intake agent node function:
`async def intake_agent_node(state: TriageState) → TriageState`

What it does:
1. Read parsed document from state (first 2000 chars of each page, max 5 pages)
2. Call Claude via the model router (task_complexity="low" → Haiku) with tool use
3. Tool: `classify_document` with input schema: {document_type: DocumentType, confidence: float, reasoning: str, key_indicators: list[str]}
4. Return updated state with document_type, classification_confidence, classification_reasoning
5. Write audit entry (use write_audit_entry from clinflow.audit)
6. Log to episodic memory

`prompts/intake.md` — system prompt for the intake agent:
- Clear classification criteria for each document type
- Examples of key indicators per type (lab report: "Reference Range", "Result", test names; clinical note: "Chief Complaint", "Assessment", ICD codes; etc.)
- Instruction to return "unknown" with low confidence if genuinely ambiguous

Also create `packages/triage/src/clinical_ai_triage/state.py`:
- TriageState TypedDict with all fields needed by the full pipeline (see implementation plan Section 7)

Write `tests/unit/test_intake_agent.py`:
- Mock the model router to return a lab_report classification
- Verify state is updated correctly
- Verify audit entry is written
- Test "unknown" classification routes correctly (will be verified in graph test)
```

**Done when:**
- Unit test passes with mocked LLM
- State TypedDict covers all pipeline fields
- Audit entry written after classification

---

### Task 2.3 — Lab Report Extraction Agent
- [ ] Done

**Prompt:**
```
Read CLAUDE.md — tool use pattern. Read PRD.md — LabReportExtraction data model.

Create `packages/triage/src/clinical_ai_triage/agents/lab_report.py` and `prompts/lab_report.md`.

`async def lab_report_agent_node(state: TriageState) → TriageState`

Tool: `extract_lab_report` with input schema matching LabReportExtraction:
- patient_id: str | None
- collection_date: str | None
- ordering_physician: str | None
- lab_name: str | None
- test_results: list[TestResult]
  - TestResult: test_name, value, unit, reference_range_low, reference_range_high, abnormal_flag (H/L/C/None), result_status

Requirements:
- Use Claude Haiku (task_complexity="low") — these are structured forms, not complex reasoning
- If PHI sensitive (state.phi_sensitive=True): route to local model
- Include retry_feedback from previous validation attempt in the prompt if state.retry_count > 0
- Return extraction_result + per-field confidence scores + provenance (page_number per test_result)
- Write audit entry including model_used, tokens, cost, duration
- Log episode to episodic memory

System prompt: instruct Claude to extract every test result row, handle multi-page lab reports, normalise units (mg/dL not "milligrams per deciliter"), flag abnormals using standard H/L/C notation.

Write `tests/unit/test_lab_report_agent.py`:
- Test extraction from a synthetic lab report text
- Test that retry_feedback appears in the prompt on second attempt
- Test PHI routing to local model
```

**Done when:**
- Unit test passes
- Retry feedback injected correctly on retry
- PHI routing test passes

---

### Task 2.4 — Clinical Note Extraction Agent
- [ ] Done

**Prompt:**
```
Create `packages/triage/src/clinical_ai_triage/agents/clinical_note.py` and `prompts/clinical_note.md`.

`async def clinical_note_agent_node(state: TriageState) → TriageState`

Tool: `extract_clinical_note` with schema:
- visit_date: str | None
- provider_name: str | None
- diagnoses: list[Diagnosis]
  - Diagnosis: description, icd10_code (str | None), certainty ("confirmed"/"suspected"/"ruled_out")
- medications: list[Medication]
  - Medication: name, dose, unit, frequency, route, start_date, end_date
- procedures: list[str]
- chief_complaint: str | None
- assessment: str | None
- plan: str | None
- follow_up_instructions: str | None

Use Claude Sonnet (task_complexity="medium") — clinical notes have complex structure and abbreviations.

System prompt: handle common clinical abbreviations (HTN=hypertension, DM2=Type 2 Diabetes, etc.), extract ICD-10 codes when explicitly stated or strongly implied, distinguish confirmed vs suspected diagnoses.

Write `tests/unit/test_clinical_note_agent.py` with a synthetic SOAP note.
```

**Done when:**
- Extracts diagnoses, medications, procedures from synthetic note
- Unit test passes

---

### Task 2.5 — Trial Summary Extraction Agent
- [ ] Done

**Prompt:**
```
Create `packages/triage/src/clinical_ai_triage/agents/trial_summary.py` and `prompts/trial_summary.md`.

`async def trial_summary_agent_node(state: TriageState) → TriageState`

Tool: `extract_trial_summary` with schema:
- study_name: str | None
- study_phase: str | None (Phase I/II/III/IV)
- sponsor: str | None
- population: PopulationSummary (n, age_range, inclusion_criteria_summary, exclusion_criteria_summary)
- primary_endpoint: EndpointResult (description, result_value, p_value, confidence_interval, met: bool | None)
- secondary_endpoints: list[EndpointResult]
- safety_summary: str | None
- conclusions: str | None

Use Claude Opus (task_complexity="high") — trial summaries require deep reasoning about statistical results.

System prompt: extract quantitative results precisely, distinguish primary vs secondary endpoints, interpret p-values correctly (< 0.05 = statistically significant), flag when endpoints are not clearly met or not met.

Write `tests/unit/test_trial_summary_agent.py`.
```

**Done when:**
- Unit test passes with synthetic trial abstract

---

### Task 2.6 — Validation Agent
- [ ] Done

**Prompt:**
```
Read PRD.md FR-3 (all 4 validation requirements). Read CLAUDE.md.

Create `packages/triage/src/clinical_ai_triage/agents/validation.py` and `prompts/validation.md`.

`async def validation_agent_node(state: TriageState) → TriageState`

Two-step validation:
1. **Schema validation (no LLM needed):**
   - Validate extraction_result against the appropriate Pydantic schema for the document_type
   - Collect all field-level failures with specific messages

2. **RAG cross-reference (Claude Haiku):**
   - For clinical notes: verify ICD-10 codes exist using icd_lookup tool
   - For lab reports: verify test names are recognizable (search clinical KB)
   - For trial summaries: verify statistical claims are internally consistent
   - Tool: `validate_extraction` with schema: {status: "PASS"|"FAIL"|"HUMAN_REVIEW", confidence: float, field_failures: list[{field, reason}], rag_references: list[str], feedback_for_retry: str}

Decision rules:
- All schema fields valid + confidence ≥ 0.85 → PASS
- Schema failures OR confidence < 0.70 AND retry_count < 2 → FAIL (retry with feedback)
- confidence between 0.70-0.84 → HUMAN_REVIEW
- confidence < 0.70 AND retry_count ≥ 2 → HUMAN_REVIEW (escalate)

Write `tests/unit/test_validation_agent.py`:
- Test PASS path
- Test FAIL → feedback path
- Test HUMAN_REVIEW escalation after 2 retries
- Test schema validation catches missing required fields
```

**Done when:**
- All 4 validation paths tested
- Feedback is specific (not generic "extraction failed") — test verifies feedback mentions the failing field

---

### Task 2.7 — Report Generation Agent
- [ ] Done

**Prompt:**
```
Create `packages/triage/src/clinical_ai_triage/agents/report.py` and `prompts/report.md`.

`async def report_agent_node(state: TriageState) → TriageState`

Generates two outputs:
1. **Structured JSON report** — matches the extraction schema, augmented with:
   - Provenance records for every field (document_id, page_number, extraction_agent)
   - Validation metadata (status, confidence, validated_at)
   - Processing metadata (total_duration_ms, models_used, total_cost_usd, retry_count)

2. **Human-readable Markdown report** using Jinja2 template:
   - Title, document type, processing timestamp
   - Summary section (key findings in plain language)
   - Detailed extraction table (field | value | confidence | source_page)
   - Abnormal/flagged items highlighted
   - Provenance footer

The report agent uses Claude Haiku to generate the plain-language summary section only. All other content is assembled from state — no LLM for data formatting.

Store both outputs in state: state["final_report_json"] and state["final_report_markdown"].

Create Jinja2 templates in `packages/triage/src/clinical_ai_triage/templates/`:
- `lab_report.md.j2`
- `clinical_note.md.j2`
- `trial_summary.md.j2`

Write `tests/unit/test_report_agent.py` that verifies:
- JSON output contains provenance for every field
- Markdown output renders without Jinja2 errors
- All models_used are recorded
```

**Done when:**
- Both report formats generated correctly
- Provenance present for every extracted field

---

### Task 2.8 — Clinical Knowledge RAG Tool + ICD-10 Lookup
- [ ] Done

**Prompt:**
```
Create the knowledge retrieval tools used by the Validation Agent.

1. `packages/triage/src/clinical_ai_triage/tools/knowledge_lookup.py`:
   - `async search_clinical_kb(query: str, top_k: int = 5) → list[KBResult]`
   - KBResult: content, relevance_score, source_document, page_number
   - Searches pgvector using clinical_ai_shared.db.pgvector.search()
   - Falls back gracefully if pgvector is empty (returns [] with a warning log)

2. `packages/triage/src/clinical_ai_triage/tools/icd_lookup.py`:
   - `async validate_icd10(code: str) → ICDValidationResult`
   - ICDValidationResult: is_valid, description, parent_code, suggestions (list of similar codes)
   - Load ICD-10 reference data from `data/seed/icd10_codes.csv` at startup (cache in memory)
   - Fuzzy match for suggestions using difflib

3. `scripts/seed_pgvector.py`:
   - Read PDF files from `data/seed/clinical_guidelines/`
   - Parse each with pdf_parser
   - Embed each page with sentence-transformers
   - Store in pgvector with metadata: {source: filename, page: n, type: "clinical_guideline"}

Write unit tests for both tools. Mock pgvector for knowledge_lookup test.
```

**Done when:**
- Knowledge lookup returns results when pgvector is seeded
- ICD-10 validation correctly identifies valid/invalid codes from the CSV
- Seed script runs without errors against Docker Compose postgres

---

### Task 2.9 — LangGraph Triage Pipeline
- [ ] Done

**Prompt:**
```
Read CLAUDE.md — specifically the LangGraph Conventions section and the graph.py pattern example.
Read the ClinicalTriage AI Graph design in 18.implementation-plan-category6-clinical-ai.md Section 6.

Create `packages/triage/src/clinical_ai_triage/graph.py`:

`build_triage_graph(checkpointer) → CompiledGraph`

Graph structure:
- Entry: intake_agent_node
- Conditional from intake: route_by_document_type() → {lab_report, clinical_note, trial_summary, adverse_event, unknown}
- All specialist agents → validation_agent_node
- Conditional from validation: route_by_validation() → {pass: report_node, fail_retry: back to specialist, fail_human: human_review}
- human_review → (after approval) report_node or (after rejection) back to specialist
- report_node → END
- Max 2 retries (tracked in state.retry_count)

Router functions (separate from nodes):
- `route_by_document_type(state) → str` — reads state["document_type"]
- `route_by_validation(state) → str` — reads state["validation_result"] and state["retry_count"]

Compile with:
- PostgresCheckpointer for production
- interrupt_before=["human_review"]

Create `packages/triage/src/clinical_ai_triage/state.py` final version with all fields:
- document_id, filename, parsed_document
- document_type, classification_confidence
- extraction_result, extraction_confidence_scores
- validation_result, retry_count, retry_feedback
- final_report_json, final_report_markdown
- phi_sensitive, run_id, error_message
- messages (Annotated[list, add_messages])

Write `tests/integration/test_triage_pipeline.py`:
- Run full pipeline with a synthetic lab report (real LLM call — mark as @pytest.mark.integration)
- Verify it produces a final_report_json with all expected fields
- Verify audit trail has entries for every node
```

**Done when:**
- Integration test passes end-to-end
- Human-in-the-loop pause verified: workflow stops at human_review, resumes after approval
- Retry loop verified: validation failure routes back to extraction, not past it

---

### Task 2.10 — Triage API Endpoints + Golden Sets + Tests
- [ ] Done

**Prompt:**
```
Read PRD.md section 10 — ClinicalTriage AI endpoints. Read FR-1 and FR-2 for upload requirements.

1. Create `api/routers/triage.py`:
   - POST /api/v1/triage/submit — multipart/form-data with PDF file upload. Accepts up to 20 files. Returns {job_id, status: "queued"}.
   - Background task: parse PDF, run triage pipeline, store result
   - GET /api/v1/triage/{job_id} — {job_id, status, document_type, current_node, created_at, completed_at}
   - GET /api/v1/triage/{job_id}/result — full extraction result JSON
   - GET /api/v1/triage/{job_id}/report — Markdown report as text/plain
   - POST /api/v1/triage/{job_id}/review — submit HITL decision (approve/reject/edit)

2. Create `tests/evaluation/golden_sets/`:
   - `lab_reports/` — 10 synthetic lab report PDFs + 10 `expected_{n}.json` files
   - `clinical_notes/` — 10 synthetic SOAP notes + expected JSON
   - `trial_summaries/` — 5 synthetic trial abstracts + expected JSON
   - Use reportlab or fpdf2 to generate PDFs programmatically — do NOT use real patient data

3. Create `tests/evaluation/eval_extraction.py`:
   - Run each golden set document through the full pipeline
   - For each field: compare extracted value to expected
   - Calculate precision, recall, F1 per field
   - Print a summary table
   - Return exit code 1 if any field F1 < 0.80

Run eval against your golden sets and iterate on prompts until F1 ≥ 0.80 for all fields.
```

**Done when:**
- POST /submit accepts PDF, returns job_id
- GET /{job_id}/report returns Markdown
- eval_extraction.py reports F1 ≥ 0.80 on all fields across golden sets

---

## Phase 3 — 5-Layer Memory System

**Goal:** Agents read from and write to all memory layers. Dreaming consolidation runs nightly and promotes episodic entries to long-term memory.

---

### Task 3.1 — Working + Episodic Memory
- [ ] Done

**Prompt:**
```
Read PRD.md section 6.4 (5-Layer Memory System) and the memory layer table completely.
Read CLAUDE.md — Memory System Conventions.

Create in `packages/memory/src/clinical_ai_memory/`:

1. `working.py` — WorkingMemory class:
   - In-memory dict scoped to a workflow run_id
   - get(run_id, key), set(run_id, key, value), clear(run_id)
   - Thread-safe using asyncio.Lock per run_id
   - Auto-clears after workflow completes (register cleanup callback)

2. `episodic.py` — EpisodicMemory class:
   - `async log(entry: EpisodicEntry) → None`
     - Appends to `data/episodic_logs/{YYYY}/{MM}/{DD}/session_{run_id}.md`
     - Format: Markdown with timestamp headers, agent, action, outcome sections
     - Creates directories as needed
   - `async read_session(run_id: str) → list[EpisodicEntry]`
   - `async read_date(date: datetime.date) → list[EpisodicEntry]` — all sessions for a day
   - `async list_dates(start_date, end_date) → list[date]` — dates with log files

File format example:
```
# Session: {run_id}
## {timestamp} — {agent}
**Action:** {action}
**Input:** {input_summary}
**Output:** {output_summary}
**Outcome:** {outcome}
**Confidence:** {confidence}
```

Write unit tests for both classes. Working memory test verifies isolation between run_ids. Episodic test verifies files are created in correct path structure.
```

**Done when:**
- Episodic log files written to correct path with correct Markdown format
- Working memory is isolated per run_id
- Unit tests pass

---

### Task 3.2 — Long-Term Memory (pgvector + Neo4j)
- [ ] Done

**Prompt:**
```
Create `packages/memory/src/clinical_ai_memory/longterm.py`:

LongTermMemory class with two backends:

1. **VectorStore (pgvector):**
   - `async store(content: str, source_episodes: list[str], importance: float) → str` — embed and store
   - `async search(query: str, top_k: int = 5) → list[LongTermEntry]`
   - `async update_access(entry_id: str)` — increment access_count, update last_accessed
   - `async apply_forgetting(older_than_days: int = 30)` — decay importance_score for entries below threshold
   - Uses sentence-transformers "all-MiniLM-L6-v2" for embeddings — same model used at index time

2. **KnowledgeGraph (Neo4j):**
   - `async add_entity(name: str, type: str, properties: dict) → str`
   - `async add_relationship(from_id: str, rel_type: str, to_id: str, properties: dict)`
   - `async traverse(start_entity: str, rel_types: list[str], max_hops: int = 3) → list[dict]`
   - `async find_related(entity: str, entity_type: str) → list[dict]`
   - Used for: drug-condition-enzyme relationships (PharmaSafe) and clinical entity relationships (Triage)

Export a unified `LongTermMemory` instance that composes both backends.

Write `tests/unit/test_longterm_memory.py` mocking both pgvector and Neo4j connections.
```

**Done when:**
- Store + search round-trip works end-to-end with Docker Compose postgres
- Neo4j traverse query returns correct paths
- Forgetting curve reduces importance_score on stale entries

---

### Task 3.3 — Procedural Memory + Index Layer
- [ ] Done

**Prompt:**
```
Create:

1. `packages/memory/src/clinical_ai_memory/procedural.py` — ProceduralMemory class:
   - Stores learned extraction templates as JSON in `data/procedural_templates/`
   - `async get_template(document_type: DocumentType, format_fingerprint: str) → ProceduralTemplate | None`
   - `async save_template(template: ProceduralTemplate) → None`
   - `async update_success_rate(template_id: str, success: bool) → None`
   - `format_fingerprint(parsed_doc: ParsedDocument) → str` — hash of structural features (column headers, section titles, page layout pattern)

2. `packages/memory/src/clinical_ai_memory/index.py` — IndexLayer class:
   - Dual-channel search: BM25 (keyword) + pgvector (semantic)
   - `async search(query: str, top_k: int = 10) → list[MemorySearchResult]`
     - Run both searches in parallel (asyncio.gather)
     - Merge using Reciprocal Rank Fusion: score = Σ 1/(k + rank_i), k=60
     - Return top_k merged results with source layer label
   - BM25 implementation: use rank_bm25 library
   - For BM25: maintain in-memory index of all long-term memory entries (rebuild on startup, update on new entries)

Write unit tests for both. Mock pgvector for index test.
```

**Done when:**
- Procedural templates saved and loaded correctly from JSON files
- Dual-channel search returns merged results with RRF scores
- Unit tests pass

---

### Task 3.4 — Dreaming Consolidation (All 3 Phases)
- [ ] Done

**Prompt:**
```
Read PRD.md section 6.4 — Dreaming memory consolidation, including the 3-phase cycle and importance scoring formula.
Read CLAUDE.md — Memory System Conventions (importance threshold: 0.60).

Create the full dreaming consolidation pipeline in `packages/memory/src/clinical_ai_memory/consolidation/`:

1. `light_sleep.py` — LightSleep class:
   - `async run(since_hours: int = 24) → list[EpisodeCandidate]`
   - Scan episodic log files from the past N hours
   - Parse each into snippet chunks (split on ## headers)
   - Deduplicate: for each pair, compute Jaccard similarity on token sets; if > 0.85, keep most recent
   - Return deduplicated candidates without touching any stored memory

2. `rem_sleep.py` — RemSleep class:
   - `async run(candidates: list[EpisodeCandidate]) → list[ReflectedCandidate]`
   - For each candidate, use Claude Haiku to extract:
     - The durable insight (what was learned, not what happened)
     - Recurrence count (how many times this pattern appeared in candidates)
     - Theme tags (list of strings)
   - Group candidates by theme
   - Return ReflectedCandidate with: content, theme_tags, recurrence_count, source_episodes

3. `deep_sleep.py` + `scoring.py` — DeepSleep class:
   - `async run(reflected: list[ReflectedCandidate]) → ConsolidationStats`
   - For each candidate, compute importance score:
     ```
     base_weight = (relevance * 0.30) + (frequency * 0.24) + (query_diversity * 0.15) + (recency * 0.15) + (other * 0.16)
     recency_factor = exp(-0.1 * days_since_created)
     reference_boost = 1 + (0.1 * times_referenced)
     importance = base_weight * recency_factor * reference_boost
     ```
   - If importance ≥ 0.60: call longterm.store() to promote to long-term memory
   - Apply forgetting curve to existing long-term entries: call longterm.apply_forgetting()
   - Return ConsolidationStats: scanned, deduplicated, reflected, promoted, decayed, run_at

4. `dreaming.py` — DreamingOrchestrator:
   - `async run() → ConsolidationStats`
   - Acquire advisory lock (Redis SETNX "dreaming:lock" with TTL 3600s) — skip if already running
   - Run Light → REM → Deep in sequence
   - Log results to episodic memory (meta!)
   - Release lock
   - Return stats

5. `scripts/run_dreaming.py` — CLI entry point:
   - Run DreamingOrchestrator
   - Print stats summary
   - Exit code 1 if any phase fails

6. `k8s/cronjobs/dreaming.yml` — K8s CronJob:
   - schedule: "0 2 * * *" (02:00 UTC daily)
   - runs `python scripts/run_dreaming.py`

Write `tests/integration/test_memory_consolidation.py`:
- Write 20 synthetic episodic entries with some duplicates and recurring patterns
- Run full dreaming cycle
- Verify: deduplication reduces count, at least 1 entry promoted to long-term, stats returned correctly
```

**Done when:**
- Integration test passes
- Lock prevents concurrent runs (verified by attempting two parallel runs)
- Promoted entries appear in long-term memory search results

---

### Task 3.5 — Memory Integration + API Endpoints
- [ ] Done

**Prompt:**
```
1. Integrate memory into the triage pipeline in `packages/triage/src/clinical_ai_triage/graph.py`:
   - Before intake_agent_node: check ProceduralMemory for a template matching the document's format_fingerprint. If found, pass template hints in the agent's system prompt.
   - After every agent node: log to EpisodicMemory via the log_episode() helper
   - After validation PASS: update ProceduralTemplate success_rate

2. Create `api/routers/memory.py`:
   - GET /api/v1/memory/search?q={query}&top_k=10 — dual-channel search
   - GET /api/v1/memory/episodic?date=YYYY-MM-DD — list sessions for a date
   - GET /api/v1/memory/episodic/{run_id} — get session log
   - GET /api/v1/memory/procedural — list all templates
   - GET /api/v1/memory/consolidation/stats — last 10 dreaming run stats
   - POST /api/v1/memory/consolidation/run — trigger manual dreaming run (async background task)
   - POST /api/v1/memory/{entry_id}/pin — pin a long-term entry (prevents forgetting)

3. Write `tests/unit/test_memory_router.py` using FastAPI TestClient.

4. Write `tests/integration/test_memory_pipeline.py`:
   - Run a triage job
   - Verify episodic log was written for the run_id
   - Run dreaming consolidation
   - Verify at least one entry from the run appears in long-term memory search
```

**Done when:**
- Memory endpoints return correct data
- Episodic logs written automatically during triage pipeline runs
- Dreaming API endpoint triggers background consolidation

---

## Phase 4 — PharmaSafe AI

**Goal:** POST a medication list to /api/v1/pharma/check. Receive a severity-ranked drug interaction report with citations.

---

### Task 4.1 — RxNorm Tool + OpenFDA Client
- [ ] Done

**Prompt:**
```
Create the external data source tools for PharmaSafe AI.

1. `packages/pharma/src/clinical_ai_pharma/tools/rxnorm.py` — RxNorm normalization:
   - `async normalize_drug_name(name: str) → NormalizationResult`
   - NormalizationResult: rxcui (str | None), standard_name, confidence, alternatives (list)
   - Call RxNorm REST API: https://rxnav.nlm.nih.gov/REST/rxcui.json?name={name}
   - If not found: try approximate match endpoint, return top-3 alternatives
   - Cache results in Redis (TTL: 7 days — drug names don't change)

2. `packages/pharma/src/clinical_ai_pharma/tools/openfda.py` — OpenFDA client:
   - `async get_drug_interactions(rxcui_a: str, rxcui_b: str) → list[DrugInteraction]`
   - Query: https://api.fda.gov/drug/label.json?search=drug_interactions:{drug_name}
   - Also query: FDA drug interaction database endpoint
   - Handle 429 rate limits: exponential backoff, max 3 retries
   - Cache results in Redis (TTL: 24 hours)
   - DrugInteraction: drug_a, drug_b, severity, mechanism, clinical_significance, source_url

Write unit tests mocking both HTTP clients. Test rate limit handling (429 → retry → success).
```

**Done when:**
- RxNorm normalises "aspirin" → RXCUI 1191 with standard_name "aspirin"
- OpenFDA client handles rate limits without raising to caller
- Caching verified: second call returns cached result without HTTP request

---

### Task 4.2 — PharmaSafe Agent Pipeline
- [ ] Done

**Prompt:**
```
Read the PharmaSafe AI component spec in PRD.md section 6.3.
Read CLAUDE.md — tool use pattern, model routing pattern.

Create all PharmaSafe agents in `packages/pharma/src/clinical_ai_pharma/agents/`:

1. `input_processor.py` — normalize and resolve medication list
   - Tool: `process_medications` — takes raw input (text/JSON/list), returns list[NormalizedMedication]
   - Claude Haiku: handle format variations, resolve brand→generic, flag ambiguous names
   - Use rxnorm tool for normalization

2. `interaction_checker.py` — query OpenFDA for all drug pairs
   - No LLM: pure tool calls
   - For each pair in normalized medication list: call openfda tool
   - Collect all DrugInteraction results

3. `literature_retrieval.py` — RAG over clinical guidelines
   - Claude Haiku: for each interaction found, search clinical guidelines KB
   - Tool: search_clinical_kb (from clinical_ai_triage.tools.knowledge_lookup — import from shared)
   - Return relevant passages with citations

4. `cross_validator.py` — compare API vs literature, assign confidence
   - Claude Opus: complex reasoning about conflicting evidence
   - Tool: `validate_interactions` — takes API findings + literature, returns validated list with confidence scores
   - Flag conflicts (API says moderate, literature says severe → escalate)
   - Assign overall confidence per interaction

5. `risk_reporter.py` — generate final report
   - Claude Sonnet: generate narrative summary
   - Tool: `generate_risk_report` — returns RiskAssessmentReport
   - Severity-rank interactions: CRITICAL first
   - Include recommended actions per interaction
   - Flag any CRITICAL interactions for immediate pharmacist review

Create `packages/pharma/src/clinical_ai_pharma/state.py` — PharmaState TypedDict
Create `packages/pharma/src/clinical_ai_pharma/graph.py` — LangGraph pipeline

Write unit tests for each agent (mocked LLM and tools).
Write `tests/integration/test_pharma_pipeline.py` — run full pipeline with known interaction pair (e.g. warfarin + aspirin).
```

**Done when:**
- Warfarin + aspirin test detects HIGH or CRITICAL interaction
- Integration test produces a RiskAssessmentReport with citations
- CRITICAL interactions flagged for human review

---

### Task 4.3 — Neo4j Drug Knowledge Graph + Pharma API
- [ ] Done

**Prompt:**
```
1. Create `scripts/seed_neo4j.py`:
   - Load `data/seed/drug_interactions.csv` (create this CSV with 50 realistic entries: Drug, AffectsEnzyme, Enzyme, MetabolizesDrug, Drug2, Severity)
   - Create Neo4j nodes: (:Drug {name, rxcui}), (:Enzyme {name}), (:Condition {name, icd10})
   - Create relationships: AFFECTS, METABOLIZED_BY, CONTRAINDICATED_WITH, INTERACTS_WITH {severity, mechanism}
   - Verify graph by running a test traversal

2. Create `packages/pharma/src/clinical_ai_pharma/tools/knowledge_graph.py`:
   - `async find_interactions_via_graph(drug_a: str, drug_b: str) → list[GraphInteractionPath]`
   - GraphInteractionPath: path (list of nodes+relationships), mechanism_description, hop_count
   - Multi-hop Cypher query:
     ```cypher
     MATCH path = (a:Drug {name: $drug_a})-[*1..3]-(b:Drug {name: $drug_b})
     RETURN path, length(path) as hops
     ORDER BY hops ASC LIMIT 5
     ```

3. Create `api/routers/pharma.py`:
   - POST /api/v1/pharma/check — body: {medications: list[MedicationInput], patient_conditions: list[str]}
   - GET /api/v1/pharma/{job_id} — status + result summary
   - GET /api/v1/pharma/{job_id}/report — full RiskAssessmentReport JSON
   - POST /api/v1/pharma/{job_id}/review — pharmacist review decision

4. Create `tests/evaluation/golden_sets/drug_interactions/` — 10 medication lists with known interactions and expected severity ratings
5. Create `tests/evaluation/eval_interaction.py` — accuracy measurement against golden sets

Run eval and verify accuracy ≥ 90% on known CRITICAL/HIGH interactions.
```

**Done when:**
- Neo4j seeded with drug-enzyme-drug relationships
- Multi-hop graph traversal returns interaction paths
- Pharma API endpoints respond correctly
- Eval accuracy ≥ 90% on CRITICAL/HIGH interactions

---

## Phase 5 — Model Routing, Observability, Evaluation

**Goal:** Every LLM call traced in LangFuse. Multi-model routing with fallbacks. CI blocks on eval regression.

---

### Task 5.1 — Model Routing Layer + Fallback Chain
- [ ] Done

**Prompt:**
```
Read CLAUDE.md — "Model Routing: Always Go Through the Router" pattern.

Create `packages/shared/src/clinical_ai_shared/llm/`:

1. `router.py` — ModelRouter:
   - `async route_request(task_complexity: Literal["low","medium","high"], phi_sensitive: bool, prompt: str, tools: list | None, system: str | None) → LLMResponse`
   - Routing table:
     - phi_sensitive=True → always local model regardless of complexity
     - complexity="low" → claude-haiku-4-5-20251001
     - complexity="medium" → claude-sonnet-4-6
     - complexity="high" → claude-opus-4-6
   - LLMResponse: content, tool_use_result, model_used, input_tokens, output_tokens, cost_usd, duration_ms

2. `claude.py` — AnthropicClient wrapper:
   - Wraps anthropic.AsyncAnthropic
   - Single call() method that handles tool_use responses
   - Structured output support: if tools provided with tool_choice="tool", extract tool_use result
   - Retry on rate limits (429) with exponential backoff via tenacity
   - Timeout: 60 seconds default, configurable per call

3. `local.py` — LocalModelClient:
   - Calls Ollama REST API at settings.OLLAMA_BASE_URL
   - Same interface as AnthropicClient
   - Handles Ollama's response format differences

4. `fallback.py` — FallbackChain:
   - Wraps ModelRouter with circuit breaker per model
   - Circuit breaker: trip after 3 failures in 60s, auto-reset after 5min
   - Fallback order: primary_model → fallback_model → local_model → raise
   - Log every fallback event at WARNING level

5. `cost.py` — CostTracker:
   - Token pricing per model (look up current Anthropic pricing)
   - `calculate_cost(model: str, input_tokens: int, output_tokens: int) → float`
   - `async record_cost(run_id: str, model: str, input_tokens: int, output_tokens: int) → None`

Write `tests/unit/test_model_router.py`:
- PHI routing always goes to local model
- Circuit breaker trips after 3 failures
- Fallback chain reaches local model when primary fails
```

**Done when:**
- All agents use router — grep for direct `anthropic.Anthropic()` instantiation outside llm/claude.py (should be zero)
- Circuit breaker test passes
- Cost calculated correctly for each model

---

### Task 5.2 — LangFuse Tracing + Prometheus Metrics
- [ ] Done

**Prompt:**
```
Read PRD.md section 8 (Observability NFRs) and section 11 (Observability & Monitoring Setup).

1. Create `packages/shared/src/clinical_ai_shared/observability/langfuse.py`:
   - LangfuseTracer class
   - `trace(run_id, workflow_name)` → context manager that creates a LangFuse Trace
   - `span(name, input, metadata)` → context manager for agent nodes
   - `generation(model, prompt, completion, tokens, cost)` → records LLM call
   - All traces tagged with workflow_name, run_id, environment
   - Auto-flush on shutdown

2. Wrap every agent node with LangFuse span — update all agents in triage and pharma packages.
   Pattern:
   ```python
   async with tracer.span("intake_agent", input={"document_id": state["document_id"]}):
       result = await claude_call(...)
       tracer.generation(model=result.model_used, ...)
   ```

3. Create `packages/shared/src/clinical_ai_shared/observability/metrics.py`:
   - Using prometheus-client
   - Counters: requests_total (labels: endpoint, status), agent_calls_total (labels: agent, outcome), validation_results_total (labels: status)
   - Histograms: agent_latency_seconds (labels: agent), workflow_duration_seconds (labels: workflow)
   - Gauges: human_review_pending (labels: workflow), model_fallback_total (labels: primary, fallback)
   - Expose /metrics endpoint in api/main.py

4. Add metrics instrumentation to all API routers and agent nodes.

Verify: run a triage job, open LangFuse UI at localhost:3000, confirm trace appears with all spans and costs.
```

**Done when:**
- LangFuse UI shows trace for a triage run with agent spans and LLM generations
- /metrics endpoint returns Prometheus format
- Cost per workflow calculable from LangFuse trace

---

### Task 5.3 — Evaluation CI Job
- [ ] Done

**Prompt:**
```
Create GitHub Actions evaluation pipeline.

1. `.github/workflows/ci.yml` — runs on every PR:
   - checkout, setup Python 3.12, install uv, uv sync
   - make check (ruff + mypy + unit tests)
   - Fail PR if any check fails

2. `.github/workflows/integration.yml` — runs on PR to main:
   - Start Docker Compose services
   - Wait for health checks
   - Run alembic migrations
   - Seed pgvector and Neo4j
   - Run integration tests: pytest tests/integration/ -m "not slow"
   - Run evaluation tests: pytest tests/evaluation/ -v
   - Post evaluation results as PR comment using GitHub Actions bot
   - Fail PR if extraction F1 < 0.80 or interaction accuracy < 0.90

3. `.github/workflows/deploy.yml` — runs on merge to main:
   - Build Docker image: multi-stage, tag with git SHA
   - Push to GitHub Container Registry (ghcr.io)
   - Apply K8s manifests (kubectl apply -f k8s/)

4. Add `.github/pull_request_template.md`:
   - Checklist: [ ] Tests pass, [ ] mypy passes, [ ] eval metrics not regressed, [ ] CLAUDE.md conventions followed, [ ] Audit entries written in new agent nodes
```

**Done when:**
- CI pipeline runs on push (test with a dummy commit)
- Integration pipeline posts eval results as PR comment
- PR template appears on new PRs

---

## Phase 6 — UI, Deployment, CI/CD

**Goal:** Chainlit app running locally. Live demo possible from: upload PDF → see extraction → approve → download report.

---

### Task 6.1 — Chainlit App + Document Upload Handler
- [ ] Done

**Prompt:**
```
Read PRD.md section 6.5 (UI). Read Chainlit documentation patterns for @cl.on_message, cl.Step, and cl.Action.

Create the Chainlit application in `ui/`:

1. `ui/app.py` — main entry point:
   - @cl.on_chat_start: display welcome message and available commands
   - @cl.on_message: route to correct handler based on message content or attached file
   - Command router: "/check [medication list]" → drug_checker, "/audit" → audit_explorer, "/memory" → memory_inspector, "/analytics" → analytics
   - File attachment detected → document_upload handler

2. `ui/chainlit.md` — welcome screen:
   - Platform name and description
   - Quick-start instructions
   - Available commands list

3. `ui/handlers/document_upload.py`:
   - Detect PDF file attachment
   - Show `cl.Step("Uploading document...")` 
   - POST to FastAPI /api/v1/triage/submit
   - Poll /api/v1/triage/{job_id} with cl.Step updates per node:
     - "Classifying document type..."
     - "Extracting [document_type] data..."
     - "Validating extraction..."
     - "Generating report..."
   - On completion: display extraction summary as formatted cl.Message
   - If HUMAN_REVIEW needed: show cl.Action buttons (APPROVE / REJECT / EDIT)
   - On APPROVE: call /api/v1/triage/{job_id}/review, resume polling
   - On completion: offer "Download report" cl.Action that fetches Markdown report

4. `ui/components/confidence_badge.py` — cl.CustomElement:
   - Renders as coloured badge: green (≥0.85), yellow (0.70-0.84), red (<0.70)
   - Used next to each extracted field in the review UI

Configure Chainlit: create `.chainlit/config.toml` with app name, description, and theme settings.
```

**Done when:**
- `chainlit run ui/app.py` starts without errors
- Upload a synthetic PDF → see classification step → see extraction → see confidence badges
- APPROVE button resumes the workflow

---

### Task 6.2 — Remaining Chainlit Handlers
- [ ] Done

**Prompt:**
```
Create the remaining Chainlit handlers in `ui/handlers/`:

1. `drug_checker.py`:
   - Accepts free-text medication list in chat: "/check warfarin 5mg, aspirin 100mg"
   - Shows cl.Step for each pipeline stage (normalizing, checking, retrieving literature, cross-validating)
   - Displays risk report: severity-coloured interaction list (CRITICAL=red, HIGH=orange, MODERATE=yellow, LOW=green)
   - Expandable cl.Message per interaction with: mechanism, evidence citations, recommended action
   - CRITICAL interactions show pharmacist review Action button

2. `workflow_monitor.py`:
   - "/status" command → list all active workflow runs
   - Show run_id, workflow_name, current_node, elapsed time, status
   - "/status {run_id}" → detailed view with step-by-step history from audit trail
   - Pending HITL reviews shown with APPROVE/REJECT Actions

3. `audit_explorer.py`:
   - "/audit {run_id}" → show full audit trail for a run as expandable cl.Steps
   - "/audit date:2026-05-25" → list all runs for a date
   - Each entry shows: agent, node, model_used, cost_usd, duration_ms, outcome

4. `memory_inspector.py`:
   - "/memory search {query}" → dual-channel search, show results with source layer
   - "/memory episodic {date}" → show episodic log for date
   - "/memory stats" → show last dreaming consolidation stats

5. `analytics.py`:
   - "/analytics" → show operations dashboard
   - Fetch metrics from /api/v1 endpoints
   - Display: docs today, active workflows, avg latency, validation pass rate, cost today
   - Memory consolidation: last run time, promoted count, decayed count
```

**Done when:**
- All 5 handlers respond to their commands without errors
- Drug checker shows severity-coloured interactions
- Workflow monitor shows pending reviews with action buttons

---

### Task 6.3 — Next.js Upgrade Path Scaffold
- [ ] Done

**Prompt:**
```
Create the Next.js upgrade path scaffold in `ui-next/`.

This is NOT a full implementation — it is a scaffold that demonstrates the architecture and allows switching from Chainlit to Next.js with no backend changes.

Create:
1. `ui-next/README.md` — explains: same FastAPI backend, set NEXT_PUBLIC_API_URL env var, run `npm run dev`
2. `ui-next/package.json` — Next.js 14, Shadcn/ui, Tailwind CSS, axios or fetch
3. `ui-next/next.config.ts` — API proxy: /api → NEXT_PUBLIC_API_URL
4. `ui-next/app/layout.tsx` — root layout with sidebar navigation
5. `ui-next/app/dashboard/page.tsx` — analytics dashboard placeholder with API call example
6. `ui-next/app/triage/page.tsx` — document upload placeholder
7. `ui-next/app/pharma/page.tsx` — drug checker placeholder
8. `ui-next/app/audit/page.tsx` — audit explorer placeholder
9. `ui-next/app/memory/page.tsx` — memory inspector placeholder
10. `ui-next/components/ui/` — Shadcn/ui base components (button, card, badge, table)

Each page should:
- Have a TODO comment pointing to the equivalent Chainlit handler
- Show a working example of one API call to the FastAPI backend
- Render the response in a basic table or list

`npm run dev` should start without errors.
```

**Done when:**
- `npm install && npm run dev` starts at localhost:3001
- Dashboard page makes a real API call to FastAPI /health and shows response
- README clearly explains how to complete each page

---

### Task 6.4 — Production Dockerfile + K8s Manifests
- [ ] Done

**Prompt:**
```
Read CLAUDE.md. Read PRD.md NFRs for scalability (stateless API + external state stores).

1. Create `Dockerfile` — multi-stage build:
   - Stage 1 (builder): install uv, install all dependencies, final image < 500MB
   - Stage 2 (api): copy installed deps + api/ + packages/ src. CMD: uvicorn api.main:app
   - Stage 3 (ui): copy ui/ only. CMD: chainlit run ui/app.py
   - Use --target flag to build API or UI image

2. Create K8s manifests in `k8s/`:
   - `namespace.yml` — clinical-ai namespace
   - `configmap.yml` — non-secret config (LOG_LEVEL, OLLAMA_BASE_URL, etc.)
   - `secrets.yml` — template only (real values via sealed-secrets or external secrets operator)
   - `deployments/api.yml` — 2 replicas, resource limits, liveness/readiness probes
   - `deployments/ui.yml` — 1 replica, Chainlit deployment
   - `deployments/worker.yml` — 1 replica for background tasks (dreaming worker)
   - `services/` — ClusterIP services for api, ui, worker
   - `ingress.yml` — routes /api → api service, / → ui service
   - `cronjobs/dreaming.yml` — CronJob: schedule "0 2 * * *", runs dreaming script

3. Update `docs/deployment.md`:
   - Local dev: docker compose up + uvicorn
   - Docker build: docker build --target api -t clinical-ai-api .
   - K8s deploy: kubectl apply -f k8s/
   - Environment setup checklist

Build the Docker image and verify it starts correctly: docker run -e ANTHROPIC_API_KEY=... clinical-ai-api
```

**Done when:**
- Docker image builds successfully in < 10 minutes
- Container starts and /health returns 200
- K8s manifests are valid YAML (kubectl apply --dry-run=client -f k8s/ passes)

---

### Task 6.5 — Final Polish + Demo Recording Prep
- [ ] Done

**Prompt:**
```
Prepare the platform for portfolio demo and final review.

1. End-to-end smoke test — run this sequence and verify each step works:
   a. docker-compose up -d → all healthy
   b. make migrate → tables created
   c. make seed → pgvector + Neo4j seeded
   d. chainlit run ui/app.py → UI starts
   e. Upload synthetic lab report PDF → classification → extraction → validation PASS → report downloaded
   f. Upload complex clinical note → triggers HUMAN_REVIEW → approve → report generated
   g. /check warfarin aspirin metformin → interaction report with severity ratings
   h. /memory stats → shows empty consolidation stats
   i. make dream → dreaming consolidation runs
   j. /memory search "warfarin" → returns consolidated entries
   k. /analytics → shows metrics from the runs above
   l. /audit {run_id from step e} → shows full 5-step audit trail

2. Fix any issues found during the smoke test.

3. Update root README.md with:
   - Architecture diagram
   - Feature highlights
   - Full quickstart guide (prerequisites, setup, first run)
   - Link to 90-second demo recording placeholder
   - Portfolio context: "Built as part of 38-week AI Engineering roadmap"

4. Verify `make check` passes cleanly (lint + typecheck + unit tests).

5. Run `pytest tests/evaluation/ -v` and verify F1 ≥ 0.80 for all extraction fields.
```

**Done when:**
- All 11 smoke test steps work without error
- README has complete quickstart that a reviewer can follow
- make check exits 0
- Evaluation tests pass with F1 ≥ 0.80

---

## Quick Reference — Task Count by Phase

| Phase | Tasks | Status |
|---|---|---|
| Phase 0 — Scaffold | 10 | 0/10 |
| Phase 1 — ClinFlow AI | 7 | 0/7 |
| Phase 2 — ClinicalTriage AI | 10 | 0/10 |
| Phase 3 — Memory System | 5 | 0/5 |
| Phase 4 — PharmaSafe AI | 3 | 0/3 |
| Phase 5 — Observability | 3 | 0/3 |
| Phase 6 — UI + Deploy | 5 | 0/5 |
| **Total** | **43** | **0/43** |

---

*Update task counts in the table above as phases complete. Mark each task `[x]` when done.*
*When stuck on a task, re-read CLAUDE.md before asking for help — the answer is usually in the conventions.*
