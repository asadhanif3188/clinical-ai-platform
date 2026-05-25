# CLAUDE.md — Clinical AI Platform

This file instructs Claude Code on how to work in this repository. Read it completely before writing any code.

---

## What This Project Is

A **monorepo of three agentic AI systems** for clinical and life-sciences workflows:

- **ClinicalTriage AI** — multi-agent pipeline that classifies, extracts, validates, and reports on clinical documents (PDFs)
- **PharmaSafe AI** — multi-agent drug interaction checker using OpenFDA, RAG, and Neo4j knowledge graph
- **ClinFlow AI** — shared workflow orchestration engine (YAML-defined, LangGraph-powered, checkpointed, auditable)

All three projects share a common infrastructure layer (`packages/shared`) and are designed to run as a single deployed platform.

**Read these before doing any non-trivial work:**
- [`PRD.md`](PRD.md) — product requirements, scope, success metrics, open questions
- [`DECISIONS.md`](DECISIONS.md) — **all finalised architecture decisions** (local model choice, storage strategies, service topology). These decisions are locked — do not deviate from them without updating DECISIONS.md first.
- [`implementation-plan-category6-clinical-ai.md`](implementation-plan-category6-clinical-ai.md) — full implementation plan with phases, LangGraph designs, data models, API specs, testing strategy

---

## Monorepo Structure

```
clinical-ai-platform/
├── packages/
│   ├── shared/        # clinical_ai_shared  — Pydantic schemas, DB clients, LLM router, observability
│   ├── clinflow/      # clinical_ai_clinflow — workflow engine (ClinFlow AI)
│   ├── memory/        # clinical_ai_memory  — 5-layer memory system + dreaming consolidation
│   ├── triage/        # clinical_ai_triage  — ClinicalTriage AI agents + LangGraph graph
│   └── pharma/        # clinical_ai_pharma  — PharmaSafe AI agents + LangGraph graph
├── api/               # FastAPI application — mounts all routers
├── ui/                # Chainlit application — handlers, components
├── ui-next/           # (scaffold) Next.js 14 upgrade path
├── tests/             # unit/, integration/, evaluation/, load/
├── scripts/           # seed_neo4j.py, seed_pgvector.py, run_dreaming.py, etc.
├── migrations/        # Alembic migrations
├── k8s/               # Kubernetes manifests
├── data/              # episodic_logs/ (gitignored), procedural_templates/, seed/
└── docs/              # architecture.md, memory-system.md, workflow-definitions.md
```

**Package manager:** `uv` with workspace support. All packages are local workspace members — never published to PyPI.

**Import rule:** Always import from the package name, not from relative paths across package boundaries.
```python
# CORRECT
from clinical_ai_shared.schemas.documents import DocumentInput
from clinical_ai_clinflow.engine import WorkflowEngine

# WRONG — never use relative imports across package boundaries
from ../../packages/shared.schemas import DocumentInput
```

---

## Finalised Decisions — Coding Constraints

These decisions are recorded in [`DECISIONS.md`](DECISIONS.md). They are **locked for this implementation**. Do not substitute alternatives without first updating DECISIONS.md and getting explicit confirmation.

| Decision | What it means when writing code |
|---|---|
| **D-1: PHI model = Phi-3 Mini 3.8B** | `PHI_MODEL=phi3:mini` in `.env.example`. `local.py` targets Ollama with this model. When routing PHI-sensitive requests, use `phi3:mini` — never Llama or any external API. |
| **D-2: LangFuse = self-hosted** | `docker-compose.yml` includes `langfuse` + `langfuse-db` services. `LANGFUSE_HOST=http://localhost:3000` in `.env.example`. Never reference `cloud.langfuse.com` in config or docs. |
| **D-3: Golden sets = synthetic + MTSamples** | `scripts/generate_golden_sets.py` creates synthetic PDFs via reportlab/fpdf2. MTSamples notes go in `tests/evaluation/golden_sets/clinical_notes/open_access/`. No real patient data ever. |
| **D-4: Episodic memory = filesystem Markdown** | `episodic.py` uses `pathlib.Path` + `aiofiles`. Path pattern: `data/episodic_logs/YYYY/MM/DD/session_{run_id}.md`. No PostgreSQL table for episodic logs. |
| **D-5: Neo4j = Community Edition (Docker)** | `docker-compose.yml`: `image: neo4j:5`, `NEO4J_PLUGINS: '["apoc"]'`. APOC procedures can be used in Cypher queries. |
| **D-6: Chainlit = separate service on port 8001** | `docker-compose.yml` has separate `ui` service. `Makefile make dev` runs both processes. Never attempt ASGI sub-mounting of Chainlit inside FastAPI. |
| **D-7: Next.js = full implementation (Phase 7)** | Phase 6 Task 6.3 scaffolds `ui-next/`. After Phase 6, all pages get full implementation. Both UIs coexist — Chainlit is not replaced. |

---

## Language & Tooling Standards

- **Python 3.12** — use 3.12 features freely (improved type hints, `tomllib`, etc.)
- **Pydantic v2** throughout — never use v1 syntax. Use `model_validator`, `field_validator`, `model_config`
- **Async by default** — all I/O-bound operations (DB, Redis, Neo4j, API calls) must be async
- **Type hints everywhere** — all function signatures, all class attributes. No `Any` unless genuinely unavoidable
- **Ruff** for linting and formatting (not Black, not flake8). Config in `pyproject.toml`
- **mypy** for type checking — strict mode (`mypy --strict`)
- **pytest** + **pytest-asyncio** for all tests

### Formatting
```toml
# pyproject.toml ruff config (already set — do not change)
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "TCH"]
```

---

## Architecture Patterns — Follow These Exactly

### 1. LangGraph State: Always Use TypedDict
```python
# packages/triage/src/clinical_ai_triage/state.py
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class TriageState(TypedDict):
    document_id: str
    document_type: str | None
    extraction_result: dict | None
    validation_result: dict | None
    retry_count: int
    messages: Annotated[list, add_messages]
```

### 2. Agents: Always Use Claude Tool Use, Never Plain Text Parsing
```python
# CORRECT — structured output via tool use
tools = [{"name": "extract_lab_report", "input_schema": LabReportExtraction.model_json_schema()}]
response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    tools=tools,
    tool_choice={"type": "tool", "name": "extract_lab_report"},
    ...
)

# WRONG — parsing free text
response = client.messages.create(model=..., messages=[...])
result = json.loads(response.content[0].text)  # NEVER do this
```

### 3. Model Routing: Always Go Through the Router
```python
# CORRECT
from clinical_ai_shared.llm.router import route_request

result = await route_request(
    task_complexity="high",        # "low" → Haiku, "medium" → Sonnet, "high" → Opus
    phi_sensitive=document.phi_sensitive,  # True → local model only
    prompt=prompt,
    tools=tools,
)

# WRONG — never instantiate the Anthropic client directly in agent code
client = anthropic.Anthropic(api_key=...)  # Only allowed in packages/shared/llm/claude.py
```

### 4. Database: Always Use Async Sessions via Dependency Injection
```python
# CORRECT — in FastAPI routes
from clinical_ai_shared.db.postgres import get_async_session

@router.post("/submit")
async def submit_document(
    document: DocumentInput,
    session: AsyncSession = Depends(get_async_session),
):
    ...

# WRONG — never create sessions inline in business logic
engine = create_async_engine(...)  # Only allowed in packages/shared/db/postgres.py
```

### 5. Audit Trail: Write at Every Agent Step
```python
# CORRECT — every agent node must write an audit entry
from clinical_ai_shared.audit import write_audit_entry

async def intake_agent_node(state: TriageState) -> TriageState:
    result = await classify_document(state)
    await write_audit_entry(
        run_id=state["run_id"],
        agent="intake_agent",
        node="classify",
        input_hash=hash_input(state["document_id"]),
        output_summary=f"Classified as {result.document_type} (confidence {result.confidence:.2f})",
        model_used=result.model_used,
        tokens_used=result.tokens,
        cost_usd=result.cost,
        duration_ms=result.duration_ms,
    )
    return {**state, "document_type": result.document_type}

# WRONG — agent nodes that do not write audit entries
```

### 6. Error Handling: Structured Exceptions, Never Bare Except
```python
# CORRECT
from clinical_ai_shared.exceptions import ExtractionError, ValidationError

try:
    result = await extract_lab_report(document)
except ExtractionError as e:
    logger.error("Extraction failed", document_id=state["document_id"], error=str(e))
    return {**state, "retry_count": state["retry_count"] + 1, "error": str(e)}

# WRONG
try:
    result = await extract_lab_report(document)
except Exception as e:   # Too broad
    pass                  # Silent failure
```

### 7. Episodic Memory: Log in Every Agent Node
```python
# Every node that produces meaningful output logs to episodic memory
from clinical_ai_memory.episodic import log_episode

await log_episode(
    agent="lab_report_agent",
    action="extract",
    input_summary=f"Lab report document_id={state['document_id']}",
    output_summary=f"Extracted {len(fields)} fields, avg confidence {avg_conf:.2f}",
    outcome="success" if validation_pass else "failure",
    confidence=avg_conf,
)
```

### 8. Configuration: Always Use Pydantic Settings
```python
# CORRECT — in packages/shared/src/clinical_ai_shared/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    database_url: str
    neo4j_uri: str
    redis_url: str
    langfuse_secret_key: str
    phi_model: str = "phi3:mini"  # Default local model for PHI data

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

# WRONG — never read os.environ directly
import os
api_key = os.environ["ANTHROPIC_API_KEY"]  # Use Settings() instead
```

---

## What NOT To Do

- **Never hardcode secrets, API keys, or connection strings** — always read from Settings
- **Never send PHI to external LLM APIs** — check `document.phi_sensitive` and route via local model
- **Never skip audit logging in agent nodes** — every node must write an audit entry
- **Never use synchronous I/O** (requests, psycopg2 sync, etc.) — always use async equivalents
- **Never write SQL directly** — use SQLAlchemy ORM or the shared pgvector/postgres helpers
- **Never use `json.loads(response.content[0].text)`** — use Claude tool use for structured outputs
- **Never modify audit log entries** — audit logs are append-only by design
- **Never use `print()` for logging** — use `structlog` via `from clinical_ai_shared.observability.logging import get_logger`
- **Never create new LangGraph graphs without writing a state TypedDict first**
- **Never import between sibling packages directly** — all cross-package imports go through `clinical_ai_shared`
- **Never deploy `.env` files** — use K8s secrets or environment variables in production

---

## Common Development Commands

```bash
# Start all infrastructure (PostgreSQL, pgvector, Neo4j, Redis, LangFuse)
docker compose up -d

# Install all packages (uv workspace)
uv sync

# Run the API server (development)
uv run uvicorn api.main:app --reload --port 8000

# Run the Chainlit UI
uv run chainlit run ui/app.py --port 8001

# Run all unit tests
uv run pytest tests/unit/ -v

# Run integration tests (requires Docker services running)
uv run pytest tests/integration/ -v

# Run evaluation tests against golden sets
uv run pytest tests/evaluation/ -v

# Run type checking
uv run mypy packages/ api/ --strict

# Run linting and formatting
uv run ruff check . --fix
uv run ruff format .

# Run database migrations
uv run alembic upgrade head

# Seed Neo4j with base drug/condition data
uv run python scripts/seed_neo4j.py

# Seed pgvector with clinical guidelines embeddings
uv run python scripts/seed_pgvector.py

# Manually trigger dreaming consolidation
uv run python scripts/run_dreaming.py

# Export audit logs to CSV
uv run python scripts/export_audit.py --start 2026-01-01 --end 2026-12-31 --output audit.csv

# Run all checks (lint + typecheck + unit tests) — run this before every commit
make check
```

---

## Testing Rules

1. **Unit tests** mock all LLM calls using `pytest-mock`. Never make real API calls in unit tests.
2. **Integration tests** require the full Docker Compose stack. They test real workflows end-to-end.
3. **Evaluation tests** run golden sets through the real pipeline (real LLM calls). They measure extraction quality.
4. **Every new agent** must have a corresponding unit test in `tests/unit/` with mocked LLM responses.
5. **Every new API endpoint** must have an integration test.
6. **Minimum coverage threshold: 80%** — enforced by `pytest --cov --cov-fail-under=80`.

```python
# Unit test pattern — mock LLM calls
@pytest.mark.asyncio
async def test_intake_agent_classifies_lab_report(mock_anthropic):
    mock_anthropic.return_value = build_mock_tool_response(
        tool_name="classify_document",
        tool_input={"document_type": "lab_report", "confidence": 0.95}
    )
    result = await intake_agent(sample_lab_report_state())
    assert result["document_type"] == "lab_report"
```

---

## LangGraph Conventions

- **State TypedDict** lives in `<package>/state.py`
- **Graph definition** lives in `<package>/graph.py`
- **Each node** is an async function: `async def node_name(state: XState) -> XState`
- **Always enable checkpointing** — use `MemorySaver` for tests, `PostgresSaver` for production
- **Conditional edges** use string return values from router functions, not inline lambdas
- **Human-in-the-loop nodes** use `interrupt_before` — never implement custom pause logic

```python
# graph.py pattern
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

def build_triage_graph(checkpointer) -> CompiledGraph:
    graph = StateGraph(TriageState)
    graph.add_node("intake", intake_agent_node)
    graph.add_node("lab_report", lab_report_agent_node)
    graph.add_node("validation", validation_agent_node)
    graph.add_node("human_review", human_review_node)  # interrupt_before this node
    graph.add_node("report", report_agent_node)

    graph.set_entry_point("intake")
    graph.add_conditional_edges("intake", route_by_document_type, {
        "lab_report": "lab_report",
        "clinical_note": "clinical_note",
        "unknown": "human_review",
    })
    graph.add_conditional_edges("validation", route_by_validation_result, {
        "pass": "report",
        "fail_retry": "lab_report",      # retry with feedback
        "fail_human": "human_review",    # escalate
    })
    graph.add_edge("report", END)

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review"],
    )
```

---

## Memory System Conventions

- **Episodic logs** are written to `data/episodic_logs/YYYY-MM-DD.md` — one file per day
- **Dreaming consolidation** runs via `scripts/run_dreaming.py` or the K8s CronJob (`k8s/cronjobs/dreaming.yml`)
- **Never read episodic files directly** in agent code — use `clinical_ai_memory.episodic.log_episode()` to write and `clinical_ai_memory.index.search()` to read
- **Procedural templates** are read/updated via `clinical_ai_memory.procedural` — never edit JSON files manually
- **Importance threshold:** 0.60 — entries below this score are not promoted to long-term memory. Do not lower this threshold without strong justification.

---

## Observability Conventions

- **Every LLM call** must be wrapped in a LangFuse trace/span. Use the helpers in `clinical_ai_shared.observability.langfuse`.
- **Structured logging:** always pass context as keyword arguments, never use f-strings in log calls.
```python
logger = get_logger(__name__)
logger.info("document_classified", document_id=doc_id, type=doc_type, confidence=conf)  # CORRECT
logger.info(f"classified {doc_id} as {doc_type}")  # WRONG — unstructured
```
- **Cost tracking:** every agent node must log token usage. The cost per workflow is aggregated from audit log entries — do not track cost separately.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in values. Required:

```bash
# LLM
ANTHROPIC_API_KEY=sk-ant-...

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/clinical_ai
PGVECTOR_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/clinical_ai

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=...

# Redis
REDIS_URL=redis://localhost:6379/0

# Observability
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000   # Self-hosted LangFuse

# Local model (PHI routing)
PHI_MODEL=phi3:mini               # Ollama model name
OLLAMA_BASE_URL=http://localhost:11434

# Notifications (HITL gateway)
SLACK_WEBHOOK_URL=https://hooks.slack.com/...   # Optional
NOTIFICATION_EMAIL=reviewer@example.com          # Optional
```

---

## Git Conventions

Follow **conventional commits**:
```
feat: add clinical note extraction agent
fix: handle missing reference ranges in lab report extraction
test: add golden set for trial summary extraction
docs: update memory-system.md with dreaming algorithm details
refactor: extract common tool definitions to shared package
chore: bump langraph to 0.3.2
```

Branch naming:
```
feature/phase-2-extraction-agents
fix/validation-confidence-threshold
test/golden-set-lab-reports
```

---

## Phase Build Order

**Build in this order — do not skip phases:**

1. **Phase 0** — Monorepo scaffold (pyproject.toml, docker-compose.yml, health endpoints, shared config)
2. **Phase 1** — ClinFlow AI core (workflow engine, YAML parser, checkpoint, HITL gateway, audit trail)
3. **Phase 2** — ClinicalTriage AI (all agents, LangGraph graph, validation loop, report generation)
4. **Phase 3** — Memory system (all 5 layers + dreaming consolidation)
5. **Phase 4** — PharmaSafe AI (all agents, Neo4j queries, cross-validation, risk report)
6. **Phase 5** — Model routing, LangFuse observability, golden set evaluation, CI pipeline
7. **Phase 6** — Chainlit UI, ui-next/ scaffold, Dockerfile, K8s manifests, GitHub Actions

**Minimum Viable Demo:** After Phase 2, the system can accept PDF uploads, classify, extract, validate, and report. This is enough for a technical interview demo.

---

## Package Dependency Rules

```
api/             → depends on: shared, clinflow, memory, triage, pharma
ui/              → calls FastAPI endpoints only (no direct package imports)
triage/          → depends on: shared, memory
pharma/          → depends on: shared, memory
clinflow/        → depends on: shared
memory/          → depends on: shared
shared/          → depends on: nothing internal (leaf package)
```

**No circular dependencies.** If you need to add a dependency that would create a cycle, the logic needs to move to `shared`.

---

*This file is the source of truth for how to work in this codebase. Update it whenever a new convention is established or an existing one changes.*
