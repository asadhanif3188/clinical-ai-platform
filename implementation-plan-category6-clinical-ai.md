# Implementation Plan: Category 6 — Clinical & Life-Sciences Agentic AI Systems

**Created:** May 25, 2026  
**Author:** Asad Hanif  
**Target:** Portfolio projects for Agentic AI Engineer roles (JD 45-style)  
**Roadmap context:** 38-week Applied AI Engineer program, currently in Phase 2 (Week 7)  
**Estimated build window:** Weeks 27-42 of the roadmap (after Phase 5 foundations are complete)

---

## Table of Contents

1. [Project Overview & Architecture Decision](#1-project-overview--architecture-decision)
2. [Repository Structure](#2-repository-structure)
3. [Technology Stack & Dependencies](#3-technology-stack--dependencies)
4. [Implementation Phases](#4-implementation-phases)
5. [Detailed Task Breakdown per Phase](#5-detailed-task-breakdown-per-phase)
6. [LangGraph Graph Designs](#6-langgraph-graph-designs)
7. [Data Models (Pydantic Schemas)](#7-data-models-pydantic-schemas)
8. [Memory System Implementation Guide](#8-memory-system-implementation-guide)
9. [API Design (FastAPI Endpoints)](#9-api-design-fastapi-endpoints)
10. [Testing Strategy](#10-testing-strategy)
11. [Observability & Monitoring Setup](#11-observability--monitoring-setup)
12. [Build Timeline Estimate](#12-build-timeline-estimate)

---

## 1. Project Overview & Architecture Decision

### How the Three Projects Relate

```
┌──────────────────────────────────────────────────────────────────────┐
│                    clinical-ai-platform (monorepo)                   │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │            ClinFlow AI — Shared Orchestration Layer           │   │
│  │  YAML workflow definitions, checkpoint/recovery, audit trail  │   │
│  │  human approval gateways, analytics dashboard                 │   │
│  └───────────┬──────────────────────────────┬────────────────────┘   │
│              │                              │                        │
│  ┌───────────▼──────────────┐  ┌───────────▼───────────────────┐     │
│  │   ClinicalTriage AI      │  │   PharmaSafe AI               │     │
│  │   (Flagship)             │  │   (Companion)                 │     │
│  │                          │  │                               │     │
│  │   Document ingestion,    │  │   Drug interaction checking,  │     │
│  │   specialist extraction, │  │   literature retrieval,       │     │
│  │   validation loops,      │  │   cross-validation,           │     │
│  │   5-layer memory,        │  │   risk assessment,            │     │
│  │   report generation      │  │   knowledge graph reasoning   │     │
│  └──────────────────────────┘  └───────────────────────────────┘     │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                Shared Infrastructure                         │    │
│  │  Memory system, model routing, observability, auth,          │    │
│  │  Pydantic schemas, Neo4j client, pgvector client             │    │ 
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

**ClinFlow AI** is built first as the orchestration engine. It provides the workflow definition format, checkpoint/recovery, human-in-the-loop gateways, and audit trail that both ClinicalTriage AI and PharmaSafe AI consume. This means ClinFlow is not a standalone product — it is the infrastructure layer that the other two projects instantiate with their domain-specific workflow definitions.

**ClinicalTriage AI** is the flagship. It demonstrates every JD 45 requirement: multi-agent plan-execute-validate loops, tool-using agents, LangGraph orchestration, 5-layer memory, Claude production integration, regulated environment patterns.

**PharmaSafe AI** is the companion. It adds knowledge graph multi-hop reasoning, multi-source cross-validation, and a different domain workflow to show the system generalizes.

### Monorepo Decision: Yes, Single Monorepo

**Rationale:**
- Shared Pydantic schemas, database clients, model routing, and observability code would otherwise be duplicated
- ClinFlow is consumed as a Python package by both projects — easier as a local package reference than a published dependency
- Single CI/CD pipeline, single Docker Compose for local development
- Portfolio reviewers clone one repo and see the entire system

**Package manager:** `uv` with workspace support (Python equivalent of npm workspaces)

---

## 2. Repository Structure

```
clinical-ai-platform/
├── README.md                           # Project overview, architecture diagram, quickstart
├── LICENSE                             # MIT
├── pyproject.toml                      # Root workspace definition (uv workspace)
├── uv.lock                            # Lockfile
├── .env.example                        # Environment variable template
├── .python-version                     # 3.12
├── docker-compose.yml                  # PostgreSQL, pgvector, Neo4j, Redis, LangFuse
├── docker-compose.prod.yml             # Production overrides
├── Dockerfile                          # Multi-stage build for API server
├── Makefile                            # Common commands (dev, test, lint, migrate, dream)
├── .github/
│   └── workflows/
│       ├── ci.yml                      # Lint + type-check + unit tests on PR
│       ├── integration.yml             # Integration tests (needs Docker services)
│       └── deploy.yml                  # Build + push Docker image + K8s deploy
│
├── k8s/                                # Kubernetes manifests
│   ├── namespace.yml
│   ├── configmap.yml
│   ├── secrets.yml                     # Template only — real values via sealed-secrets
│   ├── deployments/
│   │   ├── api.yml
│   │   ├── worker.yml                  # Dreaming consolidation worker
│   │   └── ui.yml
│   ├── services/
│   ├── ingress.yml
│   └── cronjobs/
│       └── dreaming.yml                # Nightly memory consolidation
│
├── migrations/                         # Alembic migrations for PostgreSQL
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
│       ├── 001_initial_schema.py
│       ├── 002_audit_trail.py
│       ├── 003_memory_tables.py
│       ├── 004_workflow_state.py
│       └── 005_pharma_tables.py
│
├── packages/                           # Shared packages (uv workspace members)
│   │
│   ├── shared/                         # clinical_ai_shared
│   │   ├── pyproject.toml
│   │   └── src/
│   │       └── clinical_ai_shared/
│   │           ├── __init__.py
│   │           ├── schemas/            # Pydantic models shared across projects
│   │           │   ├── __init__.py
│   │           │   ├── documents.py    # DocumentInput, DocumentType, ExtractionResult
│   │           │   ├── validation.py   # ValidationResult, ValidationFeedback
│   │           │   ├── memory.py       # EpisodicEntry, LongTermEntry, ProceduralEntry
│   │           │   ├── workflow.py     # WorkflowState, WorkflowDefinition, NodeResult
│   │           │   ├── audit.py        # AuditLogEntry, AuditQuery
│   │           │   ├── pharma.py       # DrugInteraction, RiskAssessment, MedicationInput
│   │           │   └── common.py       # ConfidenceScore, ProvenanceRecord, AgentIdentity
│   │           ├── db/
│   │           │   ├── __init__.py
│   │           │   ├── postgres.py     # Async SQLAlchemy engine, session factory
│   │           │   ├── pgvector.py     # Vector store operations (insert, search, delete)
│   │           │   ├── neo4j.py        # Neo4j driver wrapper (create, query, traverse)
│   │           │   └── redis.py        # Redis client (cache, pub/sub, task queue)
│   │           ├── llm/
│   │           │   ├── __init__.py
│   │           │   ├── router.py       # Model routing (Opus/Haiku/local) with fallback
│   │           │   ├── claude.py       # Anthropic client wrapper with tool use
│   │           │   ├── local.py        # Local model client (Ollama/vLLM) for PHI
│   │           │   ├── fallback.py     # Circuit breaker + fallback chain logic
│   │           │   └── cost.py         # Token counting and cost tracking per request
│   │           ├── observability/
│   │           │   ├── __init__.py
│   │           │   ├── langfuse.py     # LangFuse trace/span/generation helpers
│   │           │   ├── metrics.py      # Prometheus metrics (counters, histograms)
│   │           │   └── logging.py      # Structured JSON logging with correlation IDs
│   │           ├── auth/
│   │           │   ├── __init__.py
│   │           │   └── middleware.py   # API key auth middleware for FastAPI
│   │           └── config.py           # Pydantic Settings — loads from .env
│   │
│   ├── clinflow/                       # clinical_ai_clinflow — orchestration engine
│   │   ├── pyproject.toml
│   │   └── src/
│   │       └── clinical_ai_clinflow/
│   │           ├── __init__.py
│   │           ├── engine.py           # Core workflow execution engine
│   │           ├── definitions.py      # YAML/JSON workflow definition parser
│   │           ├── router.py           # Dynamic routing — evaluates conditions at edges
│   │           ├── checkpoint.py       # State persistence at every node transition
│   │           ├── recovery.py         # Resume from checkpoint, replay for debugging
│   │           ├── human_gateway.py    # Pause, notify, wait for approval, resume/reject
│   │           ├── audit.py            # Immutable audit trail writer + query API
│   │           ├── analytics.py        # Workflow metrics aggregation
│   │           ├── graph.py            # LangGraph graph builder from workflow definitions
│   │           └── workflows/          # Built-in workflow YAML definitions
│   │               ├── clinical_triage.yml
│   │               ├── pharma_check.yml
│   │               └── _template.yml   # Starter template for new workflows
│   │
│   ├── memory/                         # clinical_ai_memory — 5-layer memory system
│   │   ├── pyproject.toml
│   │   └── src/
│   │       └── clinical_ai_memory/
│   │           ├── __init__.py
│   │           ├── working.py          # Working memory — current document context
│   │           ├── episodic.py         # Episodic — date-stamped Markdown session logs
│   │           ├── longterm.py         # Long-term — pgvector embeddings + Neo4j graph
│   │           ├── procedural.py       # Procedural — extraction templates & tool patterns
│   │           ├── index.py            # Index layer — BM25 + vector dual-channel search
│   │           ├── consolidation/
│   │           │   ├── __init__.py
│   │           │   ├── dreaming.py     # Main dreaming orchestrator (Light→REM→Deep)
│   │           │   ├── light_sleep.py  # Scan, parse, deduplicate episodic entries
│   │           │   ├── rem_sleep.py    # Reflect, extract patterns, thematic grouping
│   │           │   ├── deep_sleep.py   # Score, promote to long-term, apply forgetting
│   │           │   └── scoring.py      # Importance scoring: base_weight * recency * ref_boost
│   │           └── forgetting.py       # Forgetting curve — time-weighted decay
│   │
│   ├── triage/                         # clinical_ai_triage — ClinicalTriage AI agents
│   │   ├── pyproject.toml
│   │   └── src/
│   │       └── clinical_ai_triage/
│   │           ├── __init__.py
│   │           ├── agents/
│   │           │   ├── __init__.py
│   │           │   ├── intake.py       # Document classification + routing agent
│   │           │   ├── lab_report.py   # Lab report extraction agent
│   │           │   ├── clinical_note.py # Clinical note extraction agent
│   │           │   ├── trial_summary.py # Trial summary extraction agent
│   │           │   ├── adverse_event.py # Adverse event form extraction agent
│   │           │   ├── validation.py   # Schema validation + RAG cross-reference agent
│   │           │   └── report.py       # Report generation agent (JSON + human-readable)
│   │           ├── tools/
│   │           │   ├── __init__.py
│   │           │   ├── pdf_parser.py   # PDF text extraction (PyMuPDF)
│   │           │   ├── ocr.py          # OCR fallback for scanned documents
│   │           │   ├── schema_validator.py # Pydantic schema validation tool
│   │           │   ├── knowledge_lookup.py # RAG retrieval over clinical KB
│   │           │   └── icd_lookup.py   # ICD-10 code lookup/validation tool
│   │           ├── graph.py            # LangGraph graph definition for triage pipeline
│   │           ├── state.py            # TriageState — TypedDict for LangGraph
│   │           └── prompts/
│   │               ├── intake.md       # System prompt for intake classification
│   │               ├── lab_report.md   # System prompt for lab extraction
│   │               ├── clinical_note.md
│   │               ├── trial_summary.md
│   │               ├── validation.md
│   │               └── report.md
│   │
│   └── pharma/                         # clinical_ai_pharma — PharmaSafe AI agents
│       ├── pyproject.toml
│       └── src/
│           └── clinical_ai_pharma/
│               ├── __init__.py
│               ├── agents/
│               │   ├── __init__.py
│               │   ├── input_processor.py   # Normalize medications, resolve ambiguities
│               │   ├── interaction_checker.py # Query OpenFDA API for interactions
│               │   ├── literature_retrieval.py # RAG over clinical guidelines
│               │   ├── cross_validator.py   # Compare API vs literature findings
│               │   └── risk_reporter.py     # Generate severity-ranked risk report
│               ├── tools/
│               │   ├── __init__.py
│               │   ├── openfda.py           # OpenFDA API client with caching
│               │   ├── rxnorm.py            # RxNorm drug name normalization
│               │   ├── knowledge_graph.py   # Neo4j drug-condition-enzyme queries
│               │   └── literature_search.py # Hybrid retrieval over guidelines KB
│               ├── graph.py                 # LangGraph graph for pharma pipeline
│               ├── state.py                 # PharmaState — TypedDict for LangGraph
│               └── prompts/
│                   ├── input_processor.md
│                   ├── interaction_checker.md
│                   ├── literature_retrieval.md
│                   ├── cross_validator.md
│                   └── risk_reporter.md
│
├── api/                                # FastAPI application
│   ├── __init__.py
│   ├── main.py                         # FastAPI app factory, router mounting
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── triage.py                   # /api/v1/triage/* endpoints
│   │   ├── pharma.py                   # /api/v1/pharma/* endpoints
│   │   ├── workflows.py                # /api/v1/workflows/* endpoints (ClinFlow)
│   │   ├── memory.py                   # /api/v1/memory/* endpoints (query, inspect)
│   │   ├── audit.py                    # /api/v1/audit/* endpoints (query logs)
│   │   └── health.py                   # /health, /ready
│   ├── dependencies.py                 # FastAPI dependency injection (DB sessions, etc.)
│   └── middleware.py                    # CORS, request ID, timing, auth
│
├── ui/                                 # Chainlit application (Next.js upgrade path available — see Section 6)
│   ├── app.py                          # Main Chainlit entry point (chainlit run app.py)
│   ├── handlers/
│   │   ├── document_upload.py          # @cl.on_message handler: Upload + triage flow
│   │   ├── extraction_review.py        # Human-in-the-loop approval step UI
│   │   ├── drug_checker.py             # PharmaSafe conversational interface
│   │   ├── workflow_monitor.py         # Live workflow status via Chainlit steps
│   │   ├── audit_explorer.py           # Audit trail query interface
│   │   ├── memory_inspector.py         # Browse episodic, long-term, procedural memory
│   │   └── analytics.py               # Metrics + consolidation stats dashboard
│   ├── components/
│   │   ├── confidence_badge.py         # Custom Chainlit element: confidence score display
│   │   ├── provenance_tree.py          # Custom element: source → extraction traceability
│   │   └── approval_action.py          # Chainlit Action buttons for APPROVE/REJECT/EDIT
│   └── chainlit.md                     # Welcome screen shown on app load
│
│   # ── Next.js upgrade path ────────────────────────────────────────
│   # ui-next/                          # (optional) Next.js 14 app — same FastAPI backend
│   #   ├── app/                        # App router pages
│   #   │   ├── dashboard/page.tsx      # Analytics + workflow monitor
│   #   │   ├── triage/page.tsx         # Document upload + extraction review
│   #   │   ├── pharma/page.tsx         # Drug interaction checker
│   #   │   ├── audit/page.tsx          # Audit trail explorer
│   #   │   └── memory/page.tsx         # Memory system inspector
│   #   └── components/                 # Shadcn/ui + custom React components
│   # Switch by pointing VITE_API_URL at the same FastAPI backend — no backend changes needed.
│
├── tests/
│   ├── conftest.py                     # Shared fixtures (DB, Redis, Neo4j test containers)
│   ├── unit/
│   │   ├── test_schemas.py             # Pydantic model validation
│   │   ├── test_model_router.py        # Model routing logic
│   │   ├── test_forgetting_curve.py    # Scoring and decay math
│   │   ├── test_workflow_parser.py     # YAML definition parsing
│   │   ├── test_intake_agent.py        # Classification logic (mocked LLM)
│   │   ├── test_validation_agent.py    # Schema validation + feedback
│   │   ├── test_input_processor.py     # Drug name normalization
│   │   └── test_audit_writer.py        # Audit log immutability
│   ├── integration/
│   │   ├── test_triage_pipeline.py     # Full triage graph end-to-end
│   │   ├── test_pharma_pipeline.py     # Full pharma graph end-to-end
│   │   ├── test_checkpoint_recovery.py # Kill mid-workflow, resume from checkpoint
│   │   ├── test_human_gateway.py       # Approval/rejection flow
│   │   ├── test_memory_consolidation.py # Dreaming cycle end-to-end
│   │   └── test_neo4j_queries.py       # Knowledge graph multi-hop queries
│   ├── evaluation/
│   │   ├── golden_sets/                # Ground-truth test documents
│   │   │   ├── lab_reports/            # 10 sample lab report PDFs + expected JSON
│   │   │   ├── clinical_notes/         # 10 sample clinical notes + expected JSON
│   │   │   ├── trial_summaries/        # 5 sample trial summaries + expected JSON
│   │   │   └── drug_interactions/      # 10 medication lists + expected interactions
│   │   ├── eval_extraction.py          # Precision/recall/F1 for extraction fields
│   │   └── eval_interaction.py         # Accuracy for drug interaction detection
│   └── load/
│       └── locustfile.py               # Load test: concurrent document submissions
│
├── scripts/
│   ├── seed_neo4j.py                   # Populate Neo4j with base drug/condition graph
│   ├── seed_pgvector.py                # Embed and load clinical guidelines into pgvector
│   ├── generate_golden_sets.py         # Helper to create synthetic test documents
│   ├── run_dreaming.py                 # Manual trigger for memory consolidation
│   └── export_audit.py                 # Export audit trail to CSV for compliance review
│
├── docs/
│   ├── architecture.md                 # System architecture deep dive
│   ├── memory-system.md                # 5-layer memory system documentation
│   ├── workflow-definitions.md         # How to write ClinFlow YAML workflows
│   ├── model-routing.md                # Model selection logic documentation
│   ├── deployment.md                   # Docker + K8s deployment guide
│   └── api-reference.md               # Auto-generated from FastAPI OpenAPI spec
│
└── data/
    ├── episodic_logs/                  # Episodic memory Markdown files (gitignored)
    │   └── .gitkeep
    ├── procedural_templates/           # Extraction templates learned over time
    │   ├── lab_report_v1.json
    │   └── clinical_note_v1.json
    └── seed/
        ├── drug_interactions.csv       # Base drug interaction data for Neo4j
        ├── icd10_codes.csv             # ICD-10 reference data
        └── clinical_guidelines/        # PDF guidelines for RAG knowledge base
            └── .gitkeep
```

---

## 3. Technology Stack & Dependencies

### Root `pyproject.toml`

```toml
[project]
name = "clinical-ai-platform"
version = "0.1.0"
description = "Clinical & Life-Sciences Agentic AI Systems — Portfolio"
requires-python = ">=3.12"
readme = "README.md"
license = { text = "MIT" }

[tool.uv.workspace]
members = [
    "packages/shared",
    "packages/clinflow",
    "packages/memory",
    "packages/triage",
    "packages/pharma",
]

[tool.uv.sources]
clinical-ai-shared = { workspace = true }
clinical-ai-clinflow = { workspace = true }
clinical-ai-memory = { workspace = true }
clinical-ai-triage = { workspace = true }
clinical-ai-pharma = { workspace = true }

[project.dependencies]
# --- Core Framework ---
fastapi = ">=0.115.0,<1.0"
uvicorn = { version = ">=0.34.0", extras = ["standard"] }
pydantic = ">=2.10.0,<3.0"
pydantic-settings = ">=2.7.0"

# --- LLM & Agents ---
anthropic = ">=0.42.0"            # Claude API client
langgraph = ">=0.3.0"             # LangGraph orchestration
langchain-core = ">=0.3.0"        # Base abstractions
langchain-anthropic = ">=0.3.0"   # Claude integration for LangChain/LangGraph

# --- Vector Store & Embeddings ---
pgvector = ">=0.3.6"              # pgvector Python bindings
sqlalchemy = { version = ">=2.0.36", extras = ["asyncio"] }
asyncpg = ">=0.30.0"             # Async PostgreSQL driver
sentence-transformers = ">=3.3.0" # Local embedding model

# --- Knowledge Graph ---
neo4j = ">=5.27.0"               # Neo4j Python driver

# --- Cache & Queue ---
redis = { version = ">=5.2.0", extras = ["hiredis"] }

# --- Document Processing ---
pymupdf = ">=1.25.0"             # PDF text extraction (PyMuPDF/fitz)
python-multipart = ">=0.0.18"    # File uploads in FastAPI

# --- Observability ---
langfuse = ">=2.60.0"            # LangFuse Python SDK
prometheus-client = ">=0.21.0"   # Prometheus metrics

# --- Utilities ---
pyyaml = ">=6.0.2"               # YAML workflow definitions
httpx = ">=0.28.0"               # Async HTTP client (OpenFDA, etc.)
tenacity = ">=9.0.0"             # Retry logic with backoff
structlog = ">=24.4.0"           # Structured JSON logging
python-dotenv = ">=1.0.1"        # .env loading
jinja2 = ">=3.1.5"               # Report templating

# --- UI (Chainlit) ---
chainlit = ">=1.3.0"
# Next.js upgrade path: add ui-next/ directory using Node.js — no Python dependency needed.
# Frontend calls the same FastAPI backend via REST. Switch by running: cd ui-next && npm run dev

[project.optional-dependencies]
dev = [
    "pytest = >=8.3.0",
    "pytest-asyncio = >=0.25.0",
    "pytest-cov = >=6.0",
    "pytest-mock = >=3.14.0",
    "mypy = >=1.14.0",
    "ruff = >=0.8.0",
    "pre-commit = >=4.0.0",
    "locust = >=2.32.0",          # Load testing
]
local-llm = [
    "ollama = >=0.4.0",           # Ollama client for local PHI-safe models
]
```

### Key Version Pins & Rationale

| Dependency | Version | Why |
|---|---|---|
| Python | 3.12 | Latest stable, required for modern type hints and `asyncio.TaskGroup` |
| LangGraph | 0.3+ | Stable checkpoint API, `StateGraph` with `TypedDict` |
| Anthropic SDK | 0.42+ | Tool use, extended thinking, batch API |
| pgvector | 0.3.6+ | HNSW index support, halfvec for storage efficiency |
| Neo4j driver | 5.27+ | Async support, improved Bolt protocol |
| PyMuPDF | 1.25+ | Fast PDF extraction, table detection |
| LangFuse | 2.60+ | Decorator-based tracing, cost tracking |

### `docker-compose.yml` (Development)

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg17
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: clinical_ai
      POSTGRES_USER: clinical_ai
      POSTGRES_PASSWORD: dev_password
    volumes:
      - pgdata:/var/lib/postgresql/data

  neo4j:
    image: neo4j:5.26-community
    ports: ["7474:7474", "7687:7687"]
    environment:
      NEO4J_AUTH: neo4j/dev_password
      NEO4J_PLUGINS: '["apoc"]'
    volumes:
      - neo4jdata:/data

  redis:
    image: redis:7.4-alpine
    ports: ["6379:6379"]

  langfuse:
    image: langfuse/langfuse:2
    ports: ["3000:3000"]
    environment:
      DATABASE_URL: postgresql://clinical_ai:dev_password@postgres:5432/langfuse
      NEXTAUTH_SECRET: dev_secret
      NEXTAUTH_URL: http://localhost:3000
    depends_on: [postgres]

volumes:
  pgdata:
  neo4jdata:
```

---

## 4. Implementation Phases

### Phase Overview

| Phase | Name | Duration | Dependencies | Deliverable |
|---|---|---|---|---|
| 0 | Project scaffold & shared infrastructure | 3 days | None | Runnable skeleton with DB connections, health endpoint |
| 1 | ClinFlow AI core | 5 days | Phase 0 | Workflow engine that executes YAML-defined workflows |
| 2 | ClinicalTriage AI | 8 days | Phases 0, 1 | Document triage pipeline with extraction + validation |
| 3 | Memory system (5-layer) | 5 days | Phase 0, 2 | Full memory architecture including dreaming consolidation |
| 4 | PharmaSafe AI | 5 days | Phases 0, 1 | Drug interaction pipeline with knowledge graph |
| 5 | Model routing, observability, evaluation | 4 days | Phases 2, 4 | Multi-model routing, LangFuse traces, golden set evals |
| 6 | UI, deployment, CI/CD | 5 days | All above | Chainlit UI, Docker/K8s deployment, GitHub Actions (Next.js upgrade path documented) |

**Total: ~35 days of focused work (~7 weeks at 5 days/week, or 9 weeks at 4 days/week)**

---

## 5. Detailed Task Breakdown per Phase

### Phase 0: Project Scaffold & Shared Infrastructure (3 days)

**Goal:** Runnable project skeleton. `docker-compose up`, run API, hit `/health`, get 200.

| # | Task | Key Files | Acceptance Criteria |
|---|---|---|---|
| 0.1 | Initialize monorepo with uv workspace | `pyproject.toml`, all package `pyproject.toml` files | `uv sync` installs all packages, imports work across packages |
| 0.2 | Set up Docker Compose | `docker-compose.yml` | `docker-compose up -d` starts Postgres+pgvector, Neo4j, Redis, LangFuse |
| 0.3 | Create shared config module | `packages/shared/src/clinical_ai_shared/config.py` | `Settings()` loads from `.env`, validates all required vars |
| 0.4 | Create DB connection modules | `packages/shared/src/clinical_ai_shared/db/postgres.py`, `neo4j.py`, `redis.py`, `pgvector.py` | Async session factory works, can execute a test query |
| 0.5 | Create Alembic migrations | `migrations/` — initial schema + audit table + memory tables | `alembic upgrade head` creates all tables without error |
| 0.6 | Create FastAPI skeleton | `api/main.py`, `api/routers/health.py` | `GET /health` returns `{"status": "ok"}`, `GET /ready` checks DB connections |
| 0.7 | Create shared Pydantic schemas | `packages/shared/src/clinical_ai_shared/schemas/*.py` | All models in Section 7 exist, import cleanly, serialize/deserialize |
| 0.8 | Set up structured logging | `packages/shared/src/clinical_ai_shared/observability/logging.py` | JSON logs with correlation_id, timestamp, level, module |
| 0.9 | Set up pre-commit + ruff + mypy | `.pre-commit-config.yaml`, `pyproject.toml` [tool.ruff], [tool.mypy] | `pre-commit run --all-files` passes, `mypy packages/` passes |
| 0.10 | Create test infrastructure | `tests/conftest.py` | pytest fixtures for DB sessions, test containers, mock LLM client |

---

### Phase 1: ClinFlow AI Core — Orchestration Engine (5 days)

**Goal:** A working workflow engine that can execute a simple YAML-defined workflow with checkpointing and human approval gates.

| # | Task | Key Files | Acceptance Criteria |
|---|---|---|---|
| 1.1 | Define YAML workflow schema | `packages/clinflow/src/clinical_ai_clinflow/definitions.py`, `workflows/_template.yml` | Parse a YAML file into `WorkflowDefinition` Pydantic model with validation |
| 1.2 | Build workflow execution engine | `packages/clinflow/src/clinical_ai_clinflow/engine.py` | Execute a 3-node workflow: node A → condition → node B or node C |
| 1.3 | Build LangGraph graph from YAML | `packages/clinflow/src/clinical_ai_clinflow/graph.py` | Convert a `WorkflowDefinition` into a runnable LangGraph `StateGraph` |
| 1.4 | Implement dynamic routing | `packages/clinflow/src/clinical_ai_clinflow/router.py` | Routing conditions evaluate against node output (e.g., `output.confidence > 0.8 → pass`) |
| 1.5 | Implement checkpoint persistence | `packages/clinflow/src/clinical_ai_clinflow/checkpoint.py` | Full state saved to PostgreSQL at every node transition. Query by workflow_id. |
| 1.6 | Implement recovery from checkpoint | `packages/clinflow/src/clinical_ai_clinflow/recovery.py` | Kill a workflow mid-execution, restart, verify it resumes from the correct node |
| 1.7 | Implement human approval gateway | `packages/clinflow/src/clinical_ai_clinflow/human_gateway.py` | Workflow pauses at gateway node. API endpoint to approve/reject. Workflow resumes on approval. |
| 1.8 | Implement audit trail engine | `packages/clinflow/src/clinical_ai_clinflow/audit.py` | Every node execution logged: workflow_id, node_id, inputs, outputs, agent, timestamp, model. Immutable (append-only table). |
| 1.9 | Implement workflow analytics | `packages/clinflow/src/clinical_ai_clinflow/analytics.py` | Query average execution time per node, per workflow. Bottleneck identification. |
| 1.10 | Build ClinFlow API endpoints | `api/routers/workflows.py` | POST /workflows/execute, GET /workflows/{id}/status, POST /workflows/{id}/approve, GET /workflows/{id}/audit |
| 1.11 | Write ClinFlow unit + integration tests | `tests/unit/test_workflow_parser.py`, `tests/integration/test_checkpoint_recovery.py`, `tests/integration/test_human_gateway.py` | Parser validates YAML. Checkpoint recovery test passes. Approval flow test passes. |

**Workflow YAML format example:**

```yaml
# workflows/_template.yml
name: example_workflow
version: "1.0"
description: "Template workflow definition"

state_schema:
  input_data: str
  classification: str | null
  extraction_result: dict | null
  validation_result: dict | null
  confidence: float

nodes:
  - id: classify
    agent: intake_agent
    timeout_seconds: 30
    retry:
      max_attempts: 2
      backoff_seconds: 5

  - id: extract
    agent: extraction_agent
    timeout_seconds: 60

  - id: validate
    agent: validation_agent
    timeout_seconds: 30

  - id: human_review
    type: human_gateway
    assignee_role: clinical_reviewer
    notification:
      channel: slack
      message: "Low-confidence extraction needs review"

  - id: report
    agent: report_agent
    timeout_seconds: 30

edges:
  - from: classify
    to: extract

  - from: extract
    to: validate

  - from: validate
    to: report
    condition: "state.validation_result.status == 'PASS'"

  - from: validate
    to: human_review
    condition: "state.validation_result.status == 'FAIL' and state.confidence >= 0.5"

  - from: validate
    to: extract
    condition: "state.validation_result.status == 'FAIL' and state.confidence < 0.5"
    max_loops: 2

  - from: human_review
    to: report
    condition: "approved"

  - from: human_review
    to: extract
    condition: "rejected"
```

---

### Phase 2: ClinicalTriage AI — Document Pipeline (8 days)

**Goal:** Upload a clinical PDF, get it classified, extracted, validated, and reported.

| # | Task | Key Files | Acceptance Criteria |
|---|---|---|---|
| 2.1 | Build PDF parsing tool | `packages/triage/src/clinical_ai_triage/tools/pdf_parser.py` | Extract text from multi-page PDF. Handle scanned docs with OCR fallback. Return structured pages. |
| 2.2 | Build Intake Agent | `packages/triage/src/clinical_ai_triage/agents/intake.py`, `prompts/intake.md` | Classify a document into one of 4 types (lab_report, clinical_note, trial_summary, adverse_event) with >90% accuracy on golden set. Return classification + confidence. |
| 2.3 | Build Lab Report Agent | `packages/triage/src/clinical_ai_triage/agents/lab_report.py`, `prompts/lab_report.md` | Extract: test_name, value, unit, reference_range, abnormal_flag, ordering_physician. Output matches `LabReportExtraction` schema. |
| 2.4 | Build Clinical Note Agent | `packages/triage/src/clinical_ai_triage/agents/clinical_note.py`, `prompts/clinical_note.md` | Extract: diagnoses (with ICD codes), medications (name, dose, frequency), procedures, follow_up. Output matches `ClinicalNoteExtraction` schema. |
| 2.5 | Build Trial Summary Agent | `packages/triage/src/clinical_ai_triage/agents/trial_summary.py`, `prompts/trial_summary.md` | Extract: study_name, endpoints, population, primary_results, secondary_results, statistical_significance. Output matches `TrialSummaryExtraction` schema. |
| 2.6 | Build Validation Agent | `packages/triage/src/clinical_ai_triage/agents/validation.py`, `prompts/validation.md` | Validate extraction against Pydantic schema. Cross-reference entities via RAG (e.g., does this ICD code exist? is this drug name valid?). Return PASS/FAIL + confidence + specific feedback for failures. |
| 2.7 | Build Report Generation Agent | `packages/triage/src/clinical_ai_triage/agents/report.py`, `prompts/report.md` | Generate structured JSON output + human-readable Markdown report. Every data point includes provenance (source document, page number, extraction agent). |
| 2.8 | Build clinical knowledge RAG tool | `packages/triage/src/clinical_ai_triage/tools/knowledge_lookup.py` | Semantic search over clinical guidelines embedded in pgvector. Used by Validation Agent for cross-reference. |
| 2.9 | Build ICD-10 lookup tool | `packages/triage/src/clinical_ai_triage/tools/icd_lookup.py` | Validate ICD-10 codes against reference data. Suggest corrections for invalid codes. |
| 2.10 | Wire LangGraph pipeline | `packages/triage/src/clinical_ai_triage/graph.py`, `state.py` | Full graph: intake → (conditional route to specialist) → validation → (pass → report / fail → re-extract with feedback / low-confidence → human gateway). Max 2 re-extraction loops. |
| 2.11 | Write triage workflow YAML | `packages/clinflow/src/clinical_ai_clinflow/workflows/clinical_triage.yml` | ClinFlow can execute the triage pipeline using the YAML definition |
| 2.12 | Build triage API endpoints | `api/routers/triage.py` | POST /triage/documents (upload PDF), GET /triage/{job_id}/status, GET /triage/{job_id}/result, GET /triage/{job_id}/report |
| 2.13 | Create golden test sets | `tests/evaluation/golden_sets/lab_reports/`, `clinical_notes/`, `trial_summaries/` | 10 lab reports, 10 clinical notes, 5 trial summaries — each with expected extraction JSON |
| 2.14 | Write triage tests | `tests/unit/test_intake_agent.py`, `tests/unit/test_validation_agent.py`, `tests/integration/test_triage_pipeline.py`, `tests/evaluation/eval_extraction.py` | Unit tests mock LLM and verify routing + validation logic. Integration test runs full pipeline. Eval measures F1 per field. |

---

### Phase 3: Memory System — 5-Layer OpenClaw Architecture (5 days)

**Goal:** Full memory system with dreaming consolidation running on a cron schedule.

| # | Task | Key Files | Acceptance Criteria |
|---|---|---|---|
| 3.1 | Implement working memory | `packages/memory/src/clinical_ai_memory/working.py` | In-memory context store for active document. Accessible by all agents in the current workflow. Cleared when workflow completes. |
| 3.2 | Implement episodic memory | `packages/memory/src/clinical_ai_memory/episodic.py` | Write date-stamped Markdown files to `data/episodic_logs/YYYY/MM/DD/session_{id}.md`. Record: documents processed, agent decisions, validation results, human approvals. Query by date range. |
| 3.3 | Implement long-term memory (pgvector) | `packages/memory/src/clinical_ai_memory/longterm.py` | Embed and store promoted entries in pgvector. Semantic search returns top-k with relevance scores. Metadata includes source_session, promoted_at, importance_score. |
| 3.4 | Implement long-term memory (Neo4j) | `packages/memory/src/clinical_ai_memory/longterm.py` (extended) | Store drug-condition-procedure relationships. Support multi-hop queries (Drug → affects → Enzyme → metabolizes → Drug B → contraindicated_with → Condition C). |
| 3.5 | Implement procedural memory | `packages/memory/src/clinical_ai_memory/procedural.py` | Store extraction templates as JSON. Per document type + format. Load best-matching template before extraction. Update template when human corrects an extraction. |
| 3.6 | Implement index layer (dual-channel search) | `packages/memory/src/clinical_ai_memory/index.py` | BM25 keyword search + pgvector semantic search. Reciprocal rank fusion to combine results. Single `memory.search(query)` interface that searches across all layers. |
| 3.7 | Implement Light Sleep | `packages/memory/src/clinical_ai_memory/consolidation/light_sleep.py` | Scan episodic logs from past 24h. Parse into snippet chunks. Deduplicate using Jaccard similarity (threshold 0.85). Output candidate list without modifying core memory. |
| 3.8 | Implement REM Sleep | `packages/memory/src/clinical_ai_memory/consolidation/rem_sleep.py` | Agent reflects on staged candidates using Claude. Extract recurring patterns: "Lab reports from vendor X always have values in column 3." Group thematically. |
| 3.9 | Implement Deep Sleep | `packages/memory/src/clinical_ai_memory/consolidation/deep_sleep.py`, `scoring.py` | Apply importance scoring formula. Promote entries above threshold to long-term memory. Apply forgetting curve to existing long-term entries. |
| 3.10 | Implement forgetting curve | `packages/memory/src/clinical_ai_memory/forgetting.py` | Time-weighted decay: `retention = e^(-t/half_life)`. Access-frequency boost: each retrieval resets recency. Manual pin override for critical entries. |
| 3.11 | Wire dreaming orchestrator | `packages/memory/src/clinical_ai_memory/consolidation/dreaming.py` | Run Light → REM → Deep in sequence. Log consolidation stats (scanned, deduplicated, promoted, decayed). |
| 3.12 | Create dreaming cron/script | `scripts/run_dreaming.py`, `k8s/cronjobs/dreaming.yml` | CLI: `python scripts/run_dreaming.py`. K8s CronJob runs at 02:00 UTC daily. |
| 3.13 | Integrate memory into triage pipeline | Modify `packages/triage/src/clinical_ai_triage/graph.py` | Intake agent checks procedural memory for known templates. Validation agent checks long-term memory for known entity patterns. Report agent writes to episodic memory. |
| 3.14 | Build memory API endpoints | `api/routers/memory.py` | GET /memory/search?q=..., GET /memory/episodic?date=..., GET /memory/stats (consolidation stats), POST /memory/pin/{entry_id} |
| 3.15 | Write memory tests | `tests/unit/test_forgetting_curve.py`, `tests/integration/test_memory_consolidation.py` | Forgetting curve math is correct. Full dreaming cycle processes episodic logs and promotes entries. |

---

### Phase 4: PharmaSafe AI — Drug Interaction Pipeline (5 days)

**Goal:** Input a medication list, get a structured risk assessment with severity-ranked interactions.

| # | Task | Key Files | Acceptance Criteria |
|---|---|---|---|
| 4.1 | Build RxNorm normalization tool | `packages/pharma/src/clinical_ai_pharma/tools/rxnorm.py` | Normalize drug names to RxNorm CUI. Handle brand names → generic. Handle misspellings via fuzzy match. |
| 4.2 | Build OpenFDA API client | `packages/pharma/src/clinical_ai_pharma/tools/openfda.py` | Query drug interactions endpoint. Handle rate limits (429 backoff). Cache results in Redis (TTL 24h). Return severity + mechanism. |
| 4.3 | Build Input Processing Agent | `packages/pharma/src/clinical_ai_pharma/agents/input_processor.py` | Accept JSON, free-text, or EHR format. Normalize all drug names. Resolve ambiguities (ask for clarification or best-guess with confidence). Output: list of `NormalizedMedication`. |
| 4.4 | Build Drug Interaction Checker Agent | `packages/pharma/src/clinical_ai_pharma/agents/interaction_checker.py` | For each medication pair, query OpenFDA. Collate severity ratings + mechanisms. Output structured list of `DrugInteraction`. |
| 4.5 | Build Literature Retrieval Agent | `packages/pharma/src/clinical_ai_pharma/agents/literature_retrieval.py` | Hybrid search (BM25 + vector) over clinical guidelines KB in pgvector. Retrieve relevant warnings, dosage adjustments, contraindication notes per interaction. |
| 4.6 | Build Cross-Validation Agent | `packages/pharma/src/clinical_ai_pharma/agents/cross_validator.py` | Compare API findings vs literature. Flag conflicts. Assign confidence per interaction. Flag high-risk interactions requiring pharmacist review. |
| 4.7 | Build Risk Assessment Report Generator | `packages/pharma/src/clinical_ai_pharma/agents/risk_reporter.py` | Produce severity-ranked report: interactions, evidence, citations, recommended actions (discontinue/adjust/monitor), summary. |
| 4.8 | Seed Neo4j drug knowledge graph | `scripts/seed_neo4j.py` | Load drug-condition-enzyme relationships from seed data. Create nodes: Drug, Condition, Enzyme, Interaction. Create edges: AFFECTS, METABOLIZED_BY, CONTRAINDICATED_WITH, INTERACTS_WITH. |
| 4.9 | Build knowledge graph query tool | `packages/pharma/src/clinical_ai_pharma/tools/knowledge_graph.py` | Multi-hop queries: "Drug A → affects → Enzyme X → metabolizes → Drug B → contraindicated_with → Condition C". Return traversal path as evidence. |
| 4.10 | Wire LangGraph pipeline | `packages/pharma/src/clinical_ai_pharma/graph.py`, `state.py` | Full graph: input_processing → interaction_checking → literature_retrieval → cross_validation → risk_report. |
| 4.11 | Write pharma workflow YAML | `packages/clinflow/src/clinical_ai_clinflow/workflows/pharma_check.yml` | ClinFlow can execute the pharma pipeline using the YAML definition |
| 4.12 | Build pharma API endpoints | `api/routers/pharma.py` | POST /pharma/check (submit medication list), GET /pharma/{job_id}/status, GET /pharma/{job_id}/report |
| 4.13 | Create golden test sets | `tests/evaluation/golden_sets/drug_interactions/` | 10 medication lists with known interactions + expected severity ratings |
| 4.14 | Write pharma tests | `tests/unit/test_input_processor.py`, `tests/integration/test_pharma_pipeline.py`, `tests/evaluation/eval_interaction.py` | Normalization handles brand → generic. Full pipeline detects known interactions. Eval measures accuracy. |

---

### Phase 5: Model Routing, Observability, Evaluation (4 days)

**Goal:** Multi-model routing with fallbacks, full observability traces, automated evaluation.

| # | Task | Key Files | Acceptance Criteria |
|---|---|---|---|
| 5.1 | Build model routing layer | `packages/shared/src/clinical_ai_shared/llm/router.py` | Route by task: complex reasoning → Opus, classification → Haiku, PHI-sensitive → local model. Configurable routing rules. |
| 5.2 | Build fallback chain + circuit breaker | `packages/shared/src/clinical_ai_shared/llm/fallback.py` | If primary model fails 3x in 60s, trip circuit breaker, route to fallback. Auto-reset after 5 min. Log every fallback event. |
| 5.3 | Build cost tracking | `packages/shared/src/clinical_ai_shared/llm/cost.py` | Track input/output tokens per request. Calculate cost per model. Aggregate per workflow run. Store in PostgreSQL. |
| 5.4 | Integrate LangFuse tracing | `packages/shared/src/clinical_ai_shared/observability/langfuse.py` | Every agent call wrapped in LangFuse span. Every LLM call tracked as generation. Traces linked by workflow_id. Visible in LangFuse UI. |
| 5.5 | Add Prometheus metrics | `packages/shared/src/clinical_ai_shared/observability/metrics.py` | Counters: requests_total, agent_calls_total, validation_pass/fail. Histograms: agent_latency_seconds, workflow_duration_seconds. |
| 5.6 | Build extraction evaluation | `tests/evaluation/eval_extraction.py` | Run all golden sets through pipeline. Calculate per-field precision, recall, F1. Output summary table. |
| 5.7 | Build interaction evaluation | `tests/evaluation/eval_interaction.py` | Run all medication lists through pharma pipeline. Calculate detection accuracy. Output confusion matrix. |
| 5.8 | Create evaluation CI job | `.github/workflows/integration.yml` (extend) | Eval runs on every PR. Results posted as PR comment. Fail if F1 drops below threshold (0.80). |

---

### Phase 6: UI, Deployment, CI/CD (5 days)

**Goal:** Chainlit UI, Docker production build, K8s manifests, GitHub Actions CI/CD. Next.js upgrade path scaffolded and documented.

| # | Task | Key Files | Acceptance Criteria |
|---|---|---|---|
| 6.1 | Build document upload handler | `ui/handlers/document_upload.py` | Upload PDF via chat, see classification result as Chainlit Step, link to extraction review action |
| 6.2 | Build extraction review handler + approval actions | `ui/handlers/extraction_review.py`, `ui/components/approval_action.py` | View extracted data as formatted Chainlit message. APPROVE/REJECT/EDIT Action buttons trigger HITL gateway resume. |
| 6.3 | Build drug checker handler | `ui/handlers/drug_checker.py` | Input medications conversationally, view risk assessment with severity-coloured confidence badges, expand to see evidence per interaction |
| 6.4 | Build workflow monitor handler | `ui/handlers/workflow_monitor.py` | Live workflow status via `cl.Step` streaming. See which node is active. View pending human approvals as clickable Actions. |
| 6.5 | Build audit explorer handler | `ui/handlers/audit_explorer.py` | Query audit logs by date/workflow_id/agent via chat. View full trace as expandable Chainlit Steps. |
| 6.6 | Build memory inspector handler | `ui/handlers/memory_inspector.py` | Browse episodic logs by date. Search long-term memory. View procedural templates. See dreaming consolidation stats. |
| 6.7 | Build analytics handler | `ui/handlers/analytics.py` | Workflow throughput, avg latency per node, validation pass rates, cost per workflow, memory consolidation metrics rendered as Chainlit elements. |
| 6.8 | Scaffold Next.js upgrade path | `ui-next/` (README + basic routing) | Empty Next.js 14 app with app router. Pages created for each handler equivalent. README documents: "run this against same FastAPI backend at $API_URL". |
| 6.8 | Create production Dockerfile | `Dockerfile` | Multi-stage build. Stage 1: install deps. Stage 2: copy code. Final image < 500MB. |
| 6.9 | Create K8s manifests | `k8s/` | API deployment, worker deployment (dreaming), UI deployment, services, ingress, CronJob for dreaming |
| 6.10 | Create CI pipeline | `.github/workflows/ci.yml` | On PR: ruff lint + mypy type-check + unit tests. Must pass to merge. |
| 6.11 | Create integration test pipeline | `.github/workflows/integration.yml` | Uses Docker Compose to spin up services. Runs integration + eval tests. |
| 6.12 | Create deploy pipeline | `.github/workflows/deploy.yml` | On merge to main: build Docker image, push to registry, apply K8s manifests. |
| 6.13 | Write deployment documentation | `docs/deployment.md` | Step-by-step: local dev setup, Docker deployment, K8s deployment. |

---

## 6. LangGraph Graph Designs

### ClinicalTriage AI Graph

```
                    ┌─────────────┐
                    │   START     │
                    │ (document   │
                    │  upload)    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   INTAKE    │
                    │   AGENT     │
                    │ (classify)  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┬──────────────┐
              │            │            │              │
              ▼            ▼            ▼              ▼
         ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
         │ LAB      │ │ CLINICAL │ │ TRIAL    │ │ ADVERSE  │
         │ REPORT   │ │ NOTE     │ │ SUMMARY  │ │ EVENT    │
         │ AGENT    │ │ AGENT    │ │ AGENT    │ │ AGENT    │
         └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
              │            │            │              │
              └────────────┼────────────┴──────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ VALIDATION  │◄──────────────────────────┐
                    │ AGENT       │                           │
                    └──────┬──────┘                           │
                           │                                  │
              ┌────────────┼────────────┐                     │
              │            │            │                     │
     confidence >= 0.8     │     confidence < 0.5             │
      status=PASS     0.5 <= conf    status=FAIL              │
              │        < 0.8       (max 2 loops)              │
              │      status=FAIL        │                     │
              │            │            │                     │
              ▼            ▼            │                     │
         ┌──────────┐ ┌──────────┐      │                     │
         │ REPORT   │ │ HUMAN    │      └─────────────────────┘
         │ AGENT    │ │ REVIEW   │        (re-route to specialist
         └────┬─────┘ │ GATEWAY  │         with feedback)
              │       └────┬─────┘
              │            │
              │     ┌──────┼──────┐
              │     │             │
              │  approved     rejected
              │     │             │
              │     ▼             ▼
              │  ┌──────┐    (re-route to
              │  │REPORT│     specialist)
              │  │AGENT │
              │  └──┬───┘
              │     │
              ▼     ▼
           ┌──────────┐
           │   END    │
           │ (save +  │
           │  audit)  │
           └──────────┘
```

**LangGraph `StateGraph` definition:**

```python
# packages/triage/src/clinical_ai_triage/graph.py

from langgraph.graph import StateGraph, END
from clinical_ai_triage.state import TriageState

def build_triage_graph() -> StateGraph:
    graph = StateGraph(TriageState)

    # Add nodes
    graph.add_node("intake", intake_agent)
    graph.add_node("lab_report", lab_report_agent)
    graph.add_node("clinical_note", clinical_note_agent)
    graph.add_node("trial_summary", trial_summary_agent)
    graph.add_node("adverse_event", adverse_event_agent)
    graph.add_node("validation", validation_agent)
    graph.add_node("human_review", human_review_gateway)
    graph.add_node("report", report_agent)
    graph.add_node("save_episodic", save_to_episodic_memory)

    # Entry point
    graph.set_entry_point("intake")

    # Conditional routing from intake
    graph.add_conditional_edges(
        "intake",
        route_by_document_type,
        {
            "lab_report": "lab_report",
            "clinical_note": "clinical_note",
            "trial_summary": "trial_summary",
            "adverse_event": "adverse_event",
        },
    )

    # All specialists route to validation
    for specialist in ["lab_report", "clinical_note", "trial_summary", "adverse_event"]:
        graph.add_edge(specialist, "validation")

    # Conditional routing from validation
    graph.add_conditional_edges(
        "validation",
        route_by_validation_result,
        {
            "pass": "report",
            "human_review": "human_review",
            "re_extract": route_back_to_specialist,  # dynamic: uses state.document_type
        },
    )

    # Human review outcomes
    graph.add_conditional_edges(
        "human_review",
        route_by_human_decision,
        {
            "approved": "report",
            "rejected": route_back_to_specialist,
        },
    )

    # Report → save episodic → END
    graph.add_edge("report", "save_episodic")
    graph.add_edge("save_episodic", END)

    return graph.compile(checkpointer=postgres_checkpointer)
```

---

### PharmaSafe AI Graph

```
              ┌─────────────┐
              │   START     │
              │ (medication │
              │   list)     │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │   INPUT     │
              │ PROCESSING  │
              │ (normalize) │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │ INTERACTION │
              │ CHECKER     │
              │ (OpenFDA)   │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │ LITERATURE  │
              │ RETRIEVAL   │
              │ (RAG)       │
              └──────┬──────┘
                     │
                     ▼
              ┌──────────────┐
              │ KNOWLEDGE    │
              │ GRAPH QUERY  │
              │ (Neo4j       │
              │  multi-hop)  │
              └──────┬───────┘
                     │
                     ▼
              ┌─────────────┐
              │ CROSS       │
              │ VALIDATION  │
              │ (compare    │
              │  sources)   │
              └──────┬──────┘
                     │
            ┌────────┼────────┐
            │                 │
     all confirmed     conflicts found
     confidence > 0.7   or high-risk
            │                 │
            ▼                 ▼
     ┌─────────────┐  ┌─────────────┐
     │ RISK        │  │ PHARMACIST  │
     │ REPORT      │  │ REVIEW      │
     │ GENERATOR   │  │ GATEWAY     │
     └──────┬──────┘  └──────┬──────┘
            │                 │
            │          ┌──────┼──────┐
            │       approved     needs
            │          │       more data
            │          ▼          │
            │    ┌──────────┐     │
            │    │ RISK     │     └──► (re-run
            │    │ REPORT   │         literature
            │    └────┬─────┘         retrieval
            │         │               with expanded
            ▼         ▼               query)
         ┌──────────┐
         │   END    │
         └──────────┘
```

**LangGraph definition:**

```python
# packages/pharma/src/clinical_ai_pharma/graph.py

from langgraph.graph import StateGraph, END
from clinical_ai_pharma.state import PharmaState

def build_pharma_graph() -> StateGraph:
    graph = StateGraph(PharmaState)

    graph.add_node("input_processing", input_processor_agent)
    graph.add_node("interaction_checker", interaction_checker_agent)
    graph.add_node("literature_retrieval", literature_retrieval_agent)
    graph.add_node("knowledge_graph_query", knowledge_graph_agent)
    graph.add_node("cross_validation", cross_validation_agent)
    graph.add_node("pharmacist_review", pharmacist_review_gateway)
    graph.add_node("risk_report", risk_reporter_agent)

    graph.set_entry_point("input_processing")
    graph.add_edge("input_processing", "interaction_checker")
    graph.add_edge("interaction_checker", "literature_retrieval")
    graph.add_edge("literature_retrieval", "knowledge_graph_query")
    graph.add_edge("knowledge_graph_query", "cross_validation")

    graph.add_conditional_edges(
        "cross_validation",
        route_by_risk_level,
        {
            "confirmed": "risk_report",
            "needs_review": "pharmacist_review",
        },
    )

    graph.add_conditional_edges(
        "pharmacist_review",
        route_by_pharmacist_decision,
        {
            "approved": "risk_report",
            "needs_more_data": "literature_retrieval",
        },
    )

    graph.add_edge("risk_report", END)

    return graph.compile(checkpointer=postgres_checkpointer)
```

---

### ClinFlow AI Generic Workflow Graph

```
              ┌─────────────┐
              │   START     │
              │ (parse YAML │
              │  definition)│
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │   NODE N    │◄──── checkpoint saved
              │ (run agent) │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │  EVALUATE   │
              │  ROUTING    │
              │  CONDITIONS │
              └──────┬──────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
    condition A  condition B  condition C
        │            │            │
        ▼            ▼            ▼
   ┌─────────┐ ┌──────────┐ ┌─────────────┐
   │ NODE A  │ │ HUMAN    │ │ LOOP BACK   │
   │         │ │ GATEWAY  │ │ TO NODE M   │
   └────┬────┘ │(pause +  │ │ (max N      │
        │      │ notify)  │ │  iterations)│
        │      └────┬─────┘ └──────┬──────┘
        │           │              │
        │     ┌─────┼─────┐        │
        │  approve  reject         │
        │     │       │            │
        ▼     ▼       ▼            ▼
              ... (next node per definition) ...
                     │
                     ▼
              ┌─────────────┐
              │    END      │
              │ (audit      │
              │  finalized) │
              └─────────────┘
```

---

## 7. Data Models (Pydantic Schemas)

### Document Models

```python
# packages/shared/src/clinical_ai_shared/schemas/documents.py

from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class DocumentType(StrEnum):
    LAB_REPORT = "lab_report"
    CLINICAL_NOTE = "clinical_note"
    TRIAL_SUMMARY = "trial_summary"
    ADVERSE_EVENT = "adverse_event"
    UNKNOWN = "unknown"


class DocumentInput(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    filename: str
    content_type: str  # "application/pdf", "text/plain", etc.
    raw_text: str | None = None  # Populated after PDF parsing
    page_count: int | None = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict)


class ClassificationResult(BaseModel):
    document_type: DocumentType
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str  # Why this classification was chosen


# --- Extraction Results (one per document type) ---

class LabTestResult(BaseModel):
    test_name: str
    value: str
    unit: str | None = None
    reference_range: str | None = None
    is_abnormal: bool | None = None


class LabReportExtraction(BaseModel):
    patient_name: str | None = None
    ordering_physician: str | None = None
    report_date: str | None = None
    lab_results: list[LabTestResult]
    source_pages: list[int]  # Which pages the data came from


class Medication(BaseModel):
    name: str
    dosage: str | None = None
    frequency: str | None = None
    route: str | None = None  # oral, IV, etc.


class Diagnosis(BaseModel):
    description: str
    icd_code: str | None = None
    icd_code_valid: bool | None = None  # Set by validation agent


class ClinicalNoteExtraction(BaseModel):
    patient_name: str | None = None
    visit_date: str | None = None
    diagnoses: list[Diagnosis]
    medications: list[Medication]
    procedures: list[str]
    follow_up_instructions: str | None = None
    source_pages: list[int]


class StudyEndpoint(BaseModel):
    name: str
    result: str
    is_primary: bool
    statistical_significance: str | None = None  # e.g., "p < 0.001"


class TrialSummaryExtraction(BaseModel):
    study_name: str
    sponsor: str | None = None
    phase: str | None = None  # "Phase I", "Phase II", etc.
    population_size: int | None = None
    population_demographics: str | None = None
    endpoints: list[StudyEndpoint]
    conclusion: str | None = None
    source_pages: list[int]


class ExtractionResult(BaseModel):
    """Union wrapper for all extraction types."""
    document_id: UUID
    document_type: DocumentType
    extraction: LabReportExtraction | ClinicalNoteExtraction | TrialSummaryExtraction
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    extraction_agent: str  # Which agent produced this
    model_used: str  # Which LLM model was used
    token_count: int | None = None
```

### Validation Models

```python
# packages/shared/src/clinical_ai_shared/schemas/validation.py

from enum import StrEnum
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


class ValidationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class ValidationIssue(BaseModel):
    field_path: str  # e.g., "diagnoses[0].icd_code"
    issue_type: str  # "missing_required", "invalid_format", "entity_not_found", "schema_mismatch"
    description: str
    suggested_fix: str | None = None


class ValidationResult(BaseModel):
    document_id: UUID
    status: ValidationStatus
    confidence: float = Field(ge=0.0, le=1.0)
    issues: list[ValidationIssue] = Field(default_factory=list)
    cross_reference_checks: list[dict] = Field(default_factory=list)  # RAG verification results
    validated_at: datetime = Field(default_factory=datetime.utcnow)
    validation_agent: str
    attempt_number: int = 1  # Track re-validation attempts


class ValidationFeedback(BaseModel):
    """Sent back to extraction agent on failure."""
    document_id: UUID
    issues: list[ValidationIssue]
    specific_instructions: str  # Natural language guidance for re-extraction
    attempt_number: int
```

### Memory Models

```python
# packages/shared/src/clinical_ai_shared/schemas/memory.py

from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class MemoryLayer(StrEnum):
    WORKING = "working"
    EPISODIC = "episodic"
    LONG_TERM = "long_term"
    PROCEDURAL = "procedural"


class EpisodicEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: str  # "document_processed", "validation_failed", "human_approved"
    summary: str
    details: dict = Field(default_factory=dict)
    agent_id: str
    workflow_id: UUID | None = None


class LongTermEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    content: str  # The distilled knowledge
    embedding: list[float] | None = None  # Vector embedding (set at insert time)
    source_sessions: list[UUID]  # Which episodic sessions this was promoted from
    importance_score: float = Field(ge=0.0, le=1.0)
    access_count: int = 0
    last_accessed: datetime | None = None
    promoted_at: datetime = Field(default_factory=datetime.utcnow)
    category: str  # "extraction_pattern", "validation_rule", "entity_fact"
    is_pinned: bool = False  # Exempt from forgetting curve


class ProceduralEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    document_type: str
    format_signature: str  # Hash of structural features to match similar docs
    extraction_template: dict  # JSON template: which fields, where to find them
    success_rate: float = 0.0  # How often this template produces PASS validations
    times_used: int = 0
    last_used: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ConsolidationStats(BaseModel):
    run_id: UUID = Field(default_factory=uuid4)
    started_at: datetime
    completed_at: datetime | None = None
    episodic_scanned: int = 0
    candidates_after_dedup: int = 0
    patterns_extracted: int = 0  # REM sleep output
    entries_promoted: int = 0  # Deep sleep: promoted to long-term
    entries_decayed: int = 0  # Deep sleep: importance reduced
    entries_forgotten: int = 0  # Deep sleep: removed (below threshold)
```

### Workflow Models

```python
# packages/shared/src/clinical_ai_shared/schemas/workflow.py

from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from typing import Any


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED_FOR_REVIEW = "paused_for_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class NodeDefinition(BaseModel):
    id: str
    agent: str | None = None  # Agent function name (None for human_gateway type)
    type: str = "agent"  # "agent" | "human_gateway"
    timeout_seconds: int = 60
    retry: dict = Field(default_factory=lambda: {"max_attempts": 1, "backoff_seconds": 5})
    assignee_role: str | None = None  # For human_gateway type
    notification: dict | None = None


class EdgeDefinition(BaseModel):
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    condition: str | None = None  # Python expression evaluated against state
    max_loops: int | None = None


class WorkflowDefinition(BaseModel):
    name: str
    version: str
    description: str
    state_schema: dict  # Field names and types
    nodes: list[NodeDefinition]
    edges: list[EdgeDefinition]


class NodeResult(BaseModel):
    node_id: str
    status: NodeStatus
    started_at: datetime
    completed_at: datetime | None = None
    input_data: dict = Field(default_factory=dict)
    output_data: dict = Field(default_factory=dict)
    agent_used: str | None = None
    model_used: str | None = None
    token_count: int | None = None
    cost_usd: float | None = None
    error: str | None = None


class WorkflowState(BaseModel):
    workflow_id: UUID = Field(default_factory=uuid4)
    workflow_name: str
    workflow_version: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_node: str | None = None
    node_results: list[NodeResult] = Field(default_factory=list)
    state_data: dict = Field(default_factory=dict)  # The evolving state passed between nodes
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    triggered_by: str | None = None  # User or system that initiated
    total_cost_usd: float = 0.0
    total_tokens: int = 0
```

### Audit Models

```python
# packages/shared/src/clinical_ai_shared/schemas/audit.py

from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from typing import Any


class AuditLogEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    workflow_id: UUID
    node_id: str
    event_type: str  # "node_started", "node_completed", "node_failed",
                     # "human_approved", "human_rejected", "model_called",
                     # "tool_called", "validation_passed", "validation_failed"
    agent_id: str | None = None
    model_id: str | None = None  # e.g., "claude-opus-4-20250514"
    input_summary: str | None = None  # Truncated input (no PHI in logs)
    output_summary: str | None = None  # Truncated output
    metadata: dict = Field(default_factory=dict)
    # Immutability: no UPDATE allowed on this table — append only


class AuditQuery(BaseModel):
    workflow_id: UUID | None = None
    node_id: str | None = None
    event_type: str | None = None
    agent_id: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    limit: int = 100
    offset: int = 0
```

### PharmaSafe Models

```python
# packages/shared/src/clinical_ai_shared/schemas/pharma.py

from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from datetime import datetime
from enum import StrEnum


class NormalizedMedication(BaseModel):
    original_name: str
    normalized_name: str
    rxnorm_cui: str | None = None  # RxNorm Concept Unique Identifier
    normalization_confidence: float = Field(ge=0.0, le=1.0)


class InteractionSeverity(StrEnum):
    CRITICAL = "critical"      # Life-threatening, contraindicated
    MAJOR = "major"            # Significant harm possible
    MODERATE = "moderate"      # Monitor closely
    MINOR = "minor"            # Minimal clinical significance
    UNKNOWN = "unknown"


class DrugInteraction(BaseModel):
    drug_a: str
    drug_b: str
    severity: InteractionSeverity
    mechanism: str | None = None  # How the interaction works
    clinical_significance: str | None = None
    source: str  # "openfda", "literature", "knowledge_graph"
    evidence_text: str | None = None  # Supporting quote or summary
    confidence: float = Field(ge=0.0, le=1.0)


class KnowledgeGraphPath(BaseModel):
    """A multi-hop path through the drug knowledge graph."""
    nodes: list[dict]  # [{type: "Drug", name: "Warfarin"}, {type: "Enzyme", name: "CYP2C9"}, ...]
    edges: list[dict]  # [{type: "INHIBITS", from: "Fluconazole", to: "CYP2C9"}, ...]
    interpretation: str  # Natural language explanation of the path


class MedicationInput(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    medications: list[str]  # Raw medication names as entered
    conditions: list[str] = Field(default_factory=list)  # Patient conditions
    input_format: str = "json"  # "json", "free_text", "ehr_export"
    raw_text: str | None = None  # For free-text input


class RiskAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    medication_input_id: UUID
    normalized_medications: list[NormalizedMedication]
    interactions: list[DrugInteraction]
    knowledge_graph_paths: list[KnowledgeGraphPath] = Field(default_factory=list)
    critical_count: int = 0
    major_count: int = 0
    moderate_count: int = 0
    recommendations: list[str]  # "Discontinue Drug X", "Reduce dose of Drug Y", "Monitor INR"
    requires_pharmacist_review: bool = False
    overall_risk_level: InteractionSeverity
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    report_markdown: str | None = None  # Human-readable report
```

### Common Models

```python
# packages/shared/src/clinical_ai_shared/schemas/common.py

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


class ConfidenceScore(BaseModel):
    value: float = Field(ge=0.0, le=1.0)
    reasoning: str | None = None


class ProvenanceRecord(BaseModel):
    source_document_id: UUID
    source_page: int | None = None
    extraction_agent: str
    extraction_timestamp: datetime
    model_used: str
    confidence: float


class AgentIdentity(BaseModel):
    agent_id: str  # e.g., "intake_agent", "lab_report_agent"
    agent_version: str = "1.0"
    model_id: str  # e.g., "claude-opus-4-20250514"
    capabilities: list[str] = Field(default_factory=list)
```

---

## 8. Memory System Implementation Guide

### 8.1 Episodic Memory File Structure

```
data/episodic_logs/
├── 2026/
│   ├── 06/
│   │   ├── 01/
│   │   │   ├── session_a1b2c3d4.md
│   │   │   ├── session_e5f6g7h8.md
│   │   │   └── _index.json          # Quick lookup: session_id → summary
│   │   ├── 02/
│   │   │   └── session_i9j0k1l2.md
│   │   └── ...
│   └── 07/
│       └── ...
└── ...
```

**Session log format (Markdown):**

```markdown
# Session: a1b2c3d4-e5f6-7890-abcd-ef1234567890
**Date:** 2026-06-01T14:23:00Z
**Workflow:** clinical_triage v1.0
**Triggered by:** api_upload

## Events

### 14:23:01 — Intake Agent
- **Action:** Classified document as `lab_report` (confidence: 0.94)
- **Model:** claude-haiku-4-20250514
- **Input:** "Complete Blood Count - Memorial Hospital" (3 pages)

### 14:23:05 — Lab Report Agent
- **Action:** Extracted 12 test results
- **Model:** claude-opus-4-20250514
- **Notable:** Abnormal WBC count flagged (value: 15.2, ref: 4.5-11.0)

### 14:23:09 — Validation Agent
- **Action:** PASS (confidence: 0.91)
- **Checks:** 12/12 fields valid, 3 ICD codes verified via RAG
- **Issues:** None

### 14:23:12 — Report Agent
- **Action:** Generated structured report + human-readable summary
- **Output:** report_a1b2c3d4.json, report_a1b2c3d4.md

## Summary
Processed lab report from Memorial Hospital. All extractions passed validation.
Abnormal WBC count noted — flagged in report for clinical attention.
```

### 8.2 pgvector Schema for Long-Term Memory

```sql
-- migrations/versions/003_memory_tables.py

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE long_term_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding vector(1024) NOT NULL,  -- Sentence-transformers all-MiniLM or similar
    source_sessions UUID[] DEFAULT '{}',
    category VARCHAR(50) NOT NULL,  -- 'extraction_pattern', 'validation_rule', 'entity_fact'
    importance_score FLOAT NOT NULL DEFAULT 0.5 CHECK (importance_score >= 0 AND importance_score <= 1),
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ,
    promoted_at TIMESTAMPTZ DEFAULT NOW(),
    is_pinned BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',

    -- Forgetting curve fields
    half_life_days FLOAT DEFAULT 30.0,  -- Base half-life (adjusted by access frequency)
    decay_factor FLOAT DEFAULT 1.0      -- Current retention (recalculated during Deep Sleep)
);

-- HNSW index for fast approximate nearest neighbor search
CREATE INDEX ON long_term_memory USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- BM25 full-text search index (via pg_trgm or tsvector)
ALTER TABLE long_term_memory ADD COLUMN content_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
CREATE INDEX ON long_term_memory USING gin (content_tsv);

-- Category + importance for filtered queries
CREATE INDEX ON long_term_memory (category, importance_score DESC);


CREATE TABLE procedural_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_type VARCHAR(50) NOT NULL,
    format_signature VARCHAR(64) NOT NULL,  -- SHA256 of structural features
    extraction_template JSONB NOT NULL,
    success_rate FLOAT DEFAULT 0.0,
    times_used INTEGER DEFAULT 0,
    last_used TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(document_type, format_signature)
);

CREATE INDEX ON procedural_memory (document_type, success_rate DESC);


CREATE TABLE consolidation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    phase VARCHAR(20),  -- 'light_sleep', 'rem_sleep', 'deep_sleep'
    episodic_scanned INTEGER DEFAULT 0,
    candidates_after_dedup INTEGER DEFAULT 0,
    patterns_extracted INTEGER DEFAULT 0,
    entries_promoted INTEGER DEFAULT 0,
    entries_decayed INTEGER DEFAULT 0,
    entries_forgotten INTEGER DEFAULT 0,
    error TEXT
);
```

### 8.3 Neo4j Schema for Knowledge Graph

```cypher
// --- Node Types ---

// Drug node
CREATE CONSTRAINT drug_name IF NOT EXISTS FOR (d:Drug) REQUIRE d.name IS UNIQUE;
// Properties: name, rxnorm_cui, drug_class, mechanism_of_action

// Condition node
CREATE CONSTRAINT condition_name IF NOT EXISTS FOR (c:Condition) REQUIRE c.name IS UNIQUE;
// Properties: name, icd10_code, category

// Enzyme node
CREATE CONSTRAINT enzyme_name IF NOT EXISTS FOR (e:Enzyme) REQUIRE e.name IS UNIQUE;
// Properties: name, gene, family (e.g., "CYP450")

// Procedure node
CREATE CONSTRAINT procedure_name IF NOT EXISTS FOR (p:Procedure) REQUIRE p.name IS UNIQUE;
// Properties: name, cpt_code, category

// --- Edge Types ---

// Drug interactions
// (d1:Drug)-[:INTERACTS_WITH {severity, mechanism, source}]->(d2:Drug)

// Drug-enzyme relationships
// (d:Drug)-[:METABOLIZED_BY {affinity}]->(e:Enzyme)
// (d:Drug)-[:INHIBITS {potency}]->(e:Enzyme)
// (d:Drug)-[:INDUCES {potency}]->(e:Enzyme)

// Drug-condition relationships
// (d:Drug)-[:TREATS {efficacy, evidence_level}]->(c:Condition)
// (d:Drug)-[:CONTRAINDICATED_WITH {severity, reason}]->(c:Condition)

// Condition-procedure relationships
// (p:Procedure)-[:TREATS]->(c:Condition)

// --- Example Multi-Hop Query ---

// "Find all drugs that interact with Warfarin through CYP2C9 inhibition"
MATCH (d1:Drug {name: 'Warfarin'})-[:METABOLIZED_BY]->(e:Enzyme {name: 'CYP2C9'})<-[:INHIBITS]-(d2:Drug)
RETURN d2.name AS interacting_drug, e.name AS via_enzyme

// "Find drugs contraindicated for a patient with condition X taking drug Y"
MATCH (d:Drug {name: $drug_name})-[:INTERACTS_WITH]->(d2:Drug),
      (d2)-[:CONTRAINDICATED_WITH]->(c:Condition {name: $condition_name})
RETURN d2.name, c.name
```

### 8.4 Dreaming Consolidation Algorithm

```python
# Pseudocode for the full dreaming cycle

def run_dreaming_cycle():
    """
    Nightly memory consolidation: episodic → long-term.
    Three phases modeled after human sleep cycles.
    """
    stats = ConsolidationStats(started_at=now())

    # ═══════════════════════════════════════════
    # PHASE 1: LIGHT SLEEP — Scan & Deduplicate
    # ═══════════════════════════════════════════
    # Goal: Reduce noise. No modifications to core memory.

    recent_episodes = load_episodic_logs(since=now() - timedelta(hours=24))
    stats.episodic_scanned = len(recent_episodes)

    # Parse each episode into snippet chunks
    snippets = []
    for episode in recent_episodes:
        chunks = parse_into_chunks(episode)  # Split by event boundaries
        snippets.extend(chunks)

    # Deduplicate using Jaccard similarity
    # (compare token sets of each pair of snippets)
    JACCARD_THRESHOLD = 0.85
    unique_snippets = []
    for snippet in snippets:
        is_duplicate = False
        for existing in unique_snippets:
            if jaccard_similarity(snippet.tokens, existing.tokens) > JACCARD_THRESHOLD:
                is_duplicate = True
                # Keep the one with more context
                if len(snippet.tokens) > len(existing.tokens):
                    unique_snippets.remove(existing)
                    unique_snippets.append(snippet)
                break
        if not is_duplicate:
            unique_snippets.append(snippet)

    candidates = unique_snippets
    stats.candidates_after_dedup = len(candidates)

    # ═══════════════════════════════════════════
    # PHASE 2: REM SLEEP — Reflect & Extract Patterns
    # ═══════════════════════════════════════════
    # Goal: Understand *why*, not just *what*. Find recurring themes.

    # Use Claude to reflect on the batch of candidates
    reflection_prompt = f"""
    Analyze these {len(candidates)} recent processing events.
    Identify:
    1. Recurring extraction patterns (e.g., "Lab reports from vendor X always format values in column 3")
    2. Common validation failures (e.g., "ICD codes from source Y are frequently invalid")
    3. Emerging entity relationships (e.g., "Drug A and Drug B are frequently mentioned together")
    4. Process improvements (e.g., "Clinical notes with header 'ASSESSMENT' contain the diagnosis list")

    For each pattern, rate its generalizability (0-1): is this a one-off observation or a durable rule?

    Events:
    {format_candidates(candidates)}
    """

    patterns = call_claude(reflection_prompt, model="haiku")
    stats.patterns_extracted = len(patterns)

    # ═══════════════════════════════════════════
    # PHASE 3: DEEP SLEEP — Score, Promote, Forget
    # ═══════════════════════════════════════════
    # Goal: Only truly valuable entries make it to long-term memory.

    # --- Promote new entries ---
    PROMOTION_THRESHOLD = 0.6

    for pattern in patterns:
        score = calculate_importance_score(pattern)
        if score >= PROMOTION_THRESHOLD:
            # Check if similar entry already exists in long-term memory
            existing = search_long_term_memory(pattern.content, threshold=0.90)
            if existing:
                # Merge: boost existing entry's importance
                existing.importance_score = min(1.0, existing.importance_score + 0.1)
                existing.source_sessions.extend(pattern.source_sessions)
                existing.access_count += 1
                update_long_term_entry(existing)
            else:
                # Promote: new entry in long-term memory
                embed = generate_embedding(pattern.content)
                create_long_term_entry(
                    content=pattern.content,
                    embedding=embed,
                    source_sessions=pattern.source_sessions,
                    importance_score=score,
                    category=pattern.category,
                )
                stats.entries_promoted += 1

    # --- Apply forgetting curve to ALL existing long-term entries ---
    FORGETTING_THRESHOLD = 0.1  # Below this, entry is removed

    all_entries = load_all_long_term_entries()
    for entry in all_entries:
        if entry.is_pinned:
            continue  # Pinned entries never decay

        # Calculate new decay factor
        days_since_access = (now() - (entry.last_accessed or entry.promoted_at)).days
        retention = math.exp(-days_since_access / entry.half_life_days)

        # Access frequency boost: each access extends half-life
        frequency_boost = min(2.0, 1.0 + (entry.access_count * 0.1))
        adjusted_retention = retention * frequency_boost

        entry.decay_factor = adjusted_retention
        entry.importance_score = entry.importance_score * adjusted_retention

        if entry.importance_score < FORGETTING_THRESHOLD:
            delete_long_term_entry(entry.id)
            stats.entries_forgotten += 1
        else:
            update_long_term_entry(entry)
            stats.entries_decayed += 1

    stats.completed_at = now()
    save_consolidation_stats(stats)
    return stats
```

### 8.5 Importance Scoring Formula

```python
# packages/memory/src/clinical_ai_memory/consolidation/scoring.py

import math
from datetime import datetime, timedelta


def calculate_importance_score(
    base_weight: float,        # Pattern generalizability (0-1) from REM Sleep
    recency_days: float,       # Days since the pattern was observed
    reference_count: int,      # How many episodes reference this pattern
    recency_half_life: float = 14.0,  # 2-week half-life for recency
) -> float:
    """
    Importance = base_weight * recency_factor * reference_boost

    - base_weight: How generalizable the pattern is (from REM Sleep reflection)
    - recency_factor: Exponential decay based on how recently observed
    - reference_boost: Log-scaled boost for patterns referenced across many sessions

    Returns a score between 0.0 and 1.0.
    """
    # Recency factor: exponential decay
    # 1.0 at day 0, 0.5 at half_life days, approaches 0 over time
    recency_factor = math.exp(-recency_days / recency_half_life)

    # Reference boost: logarithmic (diminishing returns)
    # 1 reference = 1.0, 5 references = ~1.7, 20 references = ~2.0
    reference_boost = 1.0 + math.log(max(1, reference_count)) / math.log(10)

    # Clamp to [0, 1]
    raw_score = base_weight * recency_factor * reference_boost
    return min(1.0, max(0.0, raw_score))


def apply_forgetting_curve(
    current_importance: float,
    days_since_last_access: float,
    half_life_days: float = 30.0,
    access_count: int = 0,
    is_pinned: bool = False,
) -> float:
    """
    Apply forgetting curve to an existing long-term memory entry.

    retention = e^(-t / half_life)
    adjusted_half_life = half_life * (1 + 0.1 * access_count)  (capped at 2x)

    Pinned entries return their current importance unchanged.
    """
    if is_pinned:
        return current_importance

    # Access frequency extends half-life (capped at 2x original)
    frequency_multiplier = min(2.0, 1.0 + 0.1 * access_count)
    adjusted_half_life = half_life_days * frequency_multiplier

    retention = math.exp(-days_since_last_access / adjusted_half_life)
    return current_importance * retention
```

---

## 9. API Design (FastAPI Endpoints)

### ClinicalTriage AI Endpoints

```python
# api/routers/triage.py

@router.post("/triage/documents", response_model=TriageJobResponse, status_code=202)
async def submit_document(
    file: UploadFile,
    priority: str = "normal",  # "urgent" | "normal" | "batch"
):
    """Upload a clinical document for triage processing.
    Returns a job_id for tracking. Processing happens asynchronously."""
    # Accepts: PDF, TXT
    # Returns: {job_id, status: "queued", estimated_time_seconds}

@router.get("/triage/{job_id}/status", response_model=TriageJobStatus)
async def get_triage_status(job_id: UUID):
    """Check processing status of a triage job."""
    # Returns: {job_id, status, current_node, progress_pct, started_at, elapsed_seconds}

@router.get("/triage/{job_id}/result", response_model=ExtractionResult)
async def get_triage_result(job_id: UUID):
    """Get the extraction result for a completed triage job."""
    # Returns: Full ExtractionResult with provenance

@router.get("/triage/{job_id}/report")
async def get_triage_report(job_id: UUID, format: str = "json"):
    """Get the generated report. format: 'json' or 'markdown'."""
    # Returns: Structured JSON or human-readable Markdown

@router.get("/triage/{job_id}/audit", response_model=list[AuditLogEntry])
async def get_triage_audit(job_id: UUID):
    """Get the complete audit trail for a triage job."""

@router.post("/triage/{job_id}/review", response_model=ReviewResponse)
async def submit_human_review(
    job_id: UUID,
    decision: Literal["approve", "reject"],
    comments: str | None = None,
    corrections: dict | None = None,  # Manual field corrections
):
    """Submit human review for a paused triage job."""

@router.post("/triage/batch", response_model=BatchJobResponse, status_code=202)
async def submit_batch(files: list[UploadFile]):
    """Upload multiple documents for batch processing."""
    # Returns: {batch_id, job_ids: [...], status: "queued"}
```

### PharmaSafe AI Endpoints

```python
# api/routers/pharma.py

@router.post("/pharma/check", response_model=PharmaJobResponse, status_code=202)
async def check_drug_interactions(input_data: MedicationInput):
    """Submit a medication list for interaction checking.
    Accepts JSON medication list, free-text, or EHR export format."""

@router.get("/pharma/{job_id}/status", response_model=PharmaJobStatus)
async def get_pharma_status(job_id: UUID):
    """Check processing status of a pharma check job."""

@router.get("/pharma/{job_id}/report", response_model=RiskAssessment)
async def get_risk_assessment(job_id: UUID):
    """Get the risk assessment report for a completed job."""

@router.get("/pharma/{job_id}/graph-paths", response_model=list[KnowledgeGraphPath])
async def get_graph_paths(job_id: UUID):
    """Get the knowledge graph traversal paths used as evidence."""

@router.get("/pharma/{job_id}/audit", response_model=list[AuditLogEntry])
async def get_pharma_audit(job_id: UUID):
    """Get the complete audit trail for a pharma check job."""

@router.post("/pharma/{job_id}/review", response_model=ReviewResponse)
async def submit_pharmacist_review(
    job_id: UUID,
    decision: Literal["approve", "needs_more_data"],
    comments: str | None = None,
):
    """Submit pharmacist review for a paused pharma check."""
```

### ClinFlow AI Endpoints

```python
# api/routers/workflows.py

@router.post("/workflows/execute", response_model=WorkflowJobResponse, status_code=202)
async def execute_workflow(
    workflow_name: str,
    input_data: dict,
    triggered_by: str = "api",
):
    """Execute a named workflow with input data."""

@router.get("/workflows/{workflow_id}/status", response_model=WorkflowState)
async def get_workflow_status(workflow_id: UUID):
    """Get current workflow state including node-level progress."""

@router.post("/workflows/{workflow_id}/approve", response_model=WorkflowState)
async def approve_workflow_step(
    workflow_id: UUID,
    decision: Literal["approve", "reject"],
    reviewer: str,
    comments: str | None = None,
):
    """Approve or reject a workflow paused at a human gateway."""

@router.get("/workflows/{workflow_id}/audit", response_model=list[AuditLogEntry])
async def get_workflow_audit(
    workflow_id: UUID,
    event_type: str | None = None,
):
    """Get audit trail for a workflow. Optionally filter by event_type."""

@router.post("/workflows/{workflow_id}/resume")
async def resume_workflow(workflow_id: UUID):
    """Resume a failed workflow from its last checkpoint."""

@router.post("/workflows/{workflow_id}/replay")
async def replay_workflow(workflow_id: UUID):
    """Replay a completed workflow for debugging (read-only mode)."""

@router.get("/workflows/definitions", response_model=list[WorkflowDefinition])
async def list_workflow_definitions():
    """List all available workflow definitions."""

@router.get("/workflows/analytics", response_model=WorkflowAnalytics)
async def get_workflow_analytics(
    workflow_name: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    """Aggregate workflow analytics: avg duration, bottlenecks, pass rates."""
```

### Memory Endpoints

```python
# api/routers/memory.py

@router.get("/memory/search", response_model=MemorySearchResults)
async def search_memory(
    q: str,
    layers: list[MemoryLayer] | None = None,  # Filter by layer
    limit: int = 10,
):
    """Unified search across all memory layers (dual-channel: BM25 + vector)."""

@router.get("/memory/episodic", response_model=list[EpisodicEntry])
async def get_episodic_logs(
    date: str | None = None,  # "2026-06-01"
    session_id: UUID | None = None,
):
    """Browse episodic memory logs by date or session."""

@router.get("/memory/stats", response_model=MemoryStats)
async def get_memory_stats():
    """Memory system stats: entry counts per layer, last consolidation run, storage usage."""

@router.post("/memory/pin/{entry_id}")
async def pin_memory_entry(entry_id: UUID):
    """Pin a long-term memory entry (exempt from forgetting curve)."""

@router.delete("/memory/pin/{entry_id}")
async def unpin_memory_entry(entry_id: UUID):
    """Unpin a long-term memory entry."""

@router.post("/memory/consolidate", response_model=ConsolidationStats)
async def trigger_consolidation():
    """Manually trigger a dreaming consolidation cycle."""
```

### Shared Middleware

```python
# api/middleware.py

# 1. Request ID middleware: generates UUID per request, adds to headers + logs
# 2. Timing middleware: logs request duration
# 3. CORS middleware: configurable origins
# 4. Auth middleware: API key validation from X-API-Key header
# 5. Error handling: structured JSON error responses with correlation_id
```

---

## 10. Testing Strategy

### 10.1 Unit Tests (Mocked LLM Calls)

| Test File | What It Tests | Mocking Strategy |
|---|---|---|
| `test_schemas.py` | All Pydantic models serialize/deserialize, validation rules work | No mocking needed |
| `test_model_router.py` | Routing logic sends correct tasks to correct models | Mock `anthropic.Client` |
| `test_forgetting_curve.py` | Math is correct: decay, half-life adjustment, pinning | No mocking needed |
| `test_workflow_parser.py` | YAML definitions parse into valid `WorkflowDefinition` | No mocking needed |
| `test_intake_agent.py` | Classification returns correct type for known inputs | Mock LLM response |
| `test_validation_agent.py` | Schema validation catches missing fields, invalid codes | Mock RAG retrieval |
| `test_input_processor.py` | Drug name normalization handles brand→generic, typos | Mock RxNorm API |
| `test_audit_writer.py` | Audit entries are append-only, cannot be modified | Test against real DB |

**Example unit test with mocked LLM:**

```python
# tests/unit/test_intake_agent.py

import pytest
from unittest.mock import AsyncMock, patch
from clinical_ai_triage.agents.intake import classify_document
from clinical_ai_shared.schemas.documents import DocumentType


@pytest.mark.asyncio
async def test_classify_lab_report():
    mock_response = AsyncMock()
    mock_response.content = [
        {"type": "text", "text": '{"document_type": "lab_report", "confidence": 0.95, "reasoning": "Contains test values and reference ranges"}'}
    ]

    with patch("clinical_ai_triage.agents.intake.llm_client.messages.create", return_value=mock_response):
        result = await classify_document("Complete Blood Count\nWBC: 7.2 x10^9/L (4.5-11.0)")

    assert result.document_type == DocumentType.LAB_REPORT
    assert result.confidence >= 0.9


@pytest.mark.asyncio
async def test_classify_unknown_document():
    mock_response = AsyncMock()
    mock_response.content = [
        {"type": "text", "text": '{"document_type": "unknown", "confidence": 0.3, "reasoning": "Cannot determine document type from content"}'}
    ]

    with patch("clinical_ai_triage.agents.intake.llm_client.messages.create", return_value=mock_response):
        result = await classify_document("Lorem ipsum dolor sit amet")

    assert result.document_type == DocumentType.UNKNOWN
    assert result.confidence < 0.5
```

### 10.2 Integration Tests (End-to-End Workflows)

| Test File | What It Tests | Infrastructure Needed |
|---|---|---|
| `test_triage_pipeline.py` | Full document upload → classification → extraction → validation → report | PostgreSQL, pgvector, Claude API (test key) |
| `test_pharma_pipeline.py` | Full medication input → normalization → interaction check → report | PostgreSQL, Neo4j, Redis, OpenFDA API |
| `test_checkpoint_recovery.py` | Kill workflow mid-execution, restart, verify correct resume | PostgreSQL (checkpoint store) |
| `test_human_gateway.py` | Workflow pauses at gateway, API approval resumes it | PostgreSQL, FastAPI test client |
| `test_memory_consolidation.py` | Write episodic logs, run dreaming, verify promotions to long-term | PostgreSQL, pgvector |
| `test_neo4j_queries.py` | Multi-hop drug-enzyme-drug queries return correct paths | Neo4j with seed data |

### 10.3 Evaluation Tests (Quality Measurement)

| Test File | What It Measures | Target |
|---|---|---|
| `eval_extraction.py` | Per-field precision/recall/F1 for lab reports, clinical notes, trial summaries | F1 >= 0.80 per field |
| `eval_interaction.py` | Drug interaction detection accuracy (true positive rate) | Accuracy >= 0.85 |

### 10.4 Golden Test Sets to Create

| Document Type | Count | What Each Contains | Source |
|---|---|---|---|
| Lab reports | 10 | CBC, metabolic panel, lipid panel, urinalysis, thyroid function | Synthetic (LLM-generated with realistic values) |
| Clinical notes | 10 | Primary care visit, ED visit, surgical note, discharge summary, consult | Synthetic |
| Trial summaries | 5 | Phase II and III trials with varying complexity | Adapted from public ClinicalTrials.gov |
| Drug interaction sets | 10 | 3-8 medications per set, known interactions seeded | Based on well-documented interactions (Warfarin+NSAIDs, etc.) |

Each golden set entry includes:
1. The input document (PDF or text)
2. The expected extraction output (JSON matching the Pydantic schema)
3. Any known tricky fields (edge cases annotated)

---

## 11. Observability & Monitoring Setup

### 11.1 LangFuse Integration Points

```python
# Every agent call is wrapped in a LangFuse trace

from langfuse.decorators import observe, langfuse_context

@observe(name="triage_pipeline")
async def run_triage_pipeline(document: DocumentInput):
    langfuse_context.update_current_trace(
        user_id="system",
        metadata={"document_id": str(document.id), "filename": document.filename},
        tags=["triage", "clinical"],
    )

    # Each agent call creates a span
    classification = await classify_document(document)  # @observe(name="intake_agent")
    extraction = await extract_data(document, classification)  # @observe(name="lab_report_agent")
    validation = await validate_extraction(extraction)  # @observe(name="validation_agent")
    report = await generate_report(extraction, validation)  # @observe(name="report_agent")

    return report


# Every LLM call is tracked as a generation
@observe(as_type="generation")
async def call_claude(prompt: str, model: str, tools: list | None = None):
    response = await client.messages.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        tools=tools,
    )
    langfuse_context.update_current_observation(
        model=model,
        input=prompt,
        output=response.content,
        usage={
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
    )
    return response
```

### 11.2 Metrics to Track

| Category | Metric | Type | Labels |
|---|---|---|---|
| **Throughput** | `workflows_total` | Counter | `workflow_name`, `status` |
| **Throughput** | `documents_processed_total` | Counter | `document_type` |
| **Latency** | `agent_latency_seconds` | Histogram | `agent_id`, `model_id` |
| **Latency** | `workflow_duration_seconds` | Histogram | `workflow_name` |
| **Quality** | `validation_results_total` | Counter | `status` (pass/fail), `document_type` |
| **Quality** | `extraction_confidence` | Histogram | `document_type`, `agent_id` |
| **Quality** | `re_extraction_loops_total` | Counter | `document_type` |
| **Cost** | `llm_tokens_total` | Counter | `model_id`, `direction` (input/output) |
| **Cost** | `llm_cost_usd_total` | Counter | `model_id`, `workflow_name` |
| **Cost** | `workflow_cost_usd` | Histogram | `workflow_name` |
| **Memory** | `memory_entries_total` | Gauge | `layer` (episodic/long_term/procedural) |
| **Memory** | `consolidation_duration_seconds` | Histogram | |
| **Memory** | `entries_promoted_total` | Counter | |
| **Memory** | `entries_forgotten_total` | Counter | |
| **Human-in-the-loop** | `human_review_pending` | Gauge | `workflow_name` |
| **Human-in-the-loop** | `human_review_latency_seconds` | Histogram | |
| **Reliability** | `model_fallback_total` | Counter | `primary_model`, `fallback_model` |
| **Reliability** | `circuit_breaker_trips_total` | Counter | `model_id` |
| **Reliability** | `checkpoint_saves_total` | Counter | `workflow_name` |
| **Pharma** | `interactions_detected_total` | Counter | `severity` |
| **Pharma** | `pharmacist_reviews_total` | Counter | `decision` |

### 11.3 Dashboard Layout (Chainlit Analytics Handler — Next.js upgrade path equivalent)

> **Chainlit implementation:** Render metrics as `cl.Text` + `cl.CustomElement` blocks inside the analytics handler.
> **Next.js upgrade:** Same layout becomes a `/dashboard` page using Recharts or Tremor components, calling the same `/api/v1/metrics` endpoint.

```
┌───────────────────────────────────────────────────────────────┐
│  Clinical AI Platform — Operations Dashboard                  │
├──────────┬──────────┬──────────┬───────────┬──────────────────┤
│ Docs     │ Workflows│ Avg      │ Validation│ Cost             │
│ Today    │ Active   │ Latency  │ Pass Rate │ Today            │
│ 47       │ 3        │ 12.4s    │ 89%       │ $4.72            │
├──────────┴──────────┴──────────┴───────────┴──────────────────┤
│                                                               │
│  [Workflow Throughput — 24h line chart]                       │
│                                                               │
├──────────────────────────────────┬────────────────────────────┤
│  [Agent Latency by Type]         │  [Validation Pass/Fail]    │
│  Bar chart: intake 1.2s,         │  Donut chart: 89% pass,    │
│  lab_report 4.1s,                │  7% fail+retry, 4% human   │
│  validation 2.3s, report 3.8s    │  review                    │
├──────────────────────────────────┼────────────────────────────┤
│  [Cost by Model]                 │  [Memory Consolidation]    │
│  Pie: Opus 62%, Haiku 28%,       │  Last run: 02:00 UTC       │
│  Local 10%                       │  Promoted: 12, Decayed: 8  │
│                                  │  Forgotten: 3              │
├──────────────────────────────────┴────────────────────────────┤
│  [Pending Human Reviews]                                      │
│  Job #47a2: Lab report, confidence 0.63 — waiting 4m        │
│  Job #91c8: Trial summary, confidence 0.52 — waiting 12m    │
└───────────────────────────────────────────────────────────────┘
```

---

## 12. Build Timeline Estimate

### Timeline by Phase

| Phase | Name | Estimated Days | Roadmap Weeks | Prerequisites |
|---|---|---|---|---|
| 0 | Project scaffold & shared infra | 3 | Week 27-28 | Roadmap Phases 0-5 complete (Python, FastAPI, RAG, Agents, LangGraph, Eval, Observability) |
| 1 | ClinFlow AI core | 5 | Week 28-29 | Phase 0 |
| 2 | ClinicalTriage AI | 8 | Week 29-31 | Phases 0, 1 |
| 3 | Memory system (5-layer) | 5 | Week 31-32 | Phases 0, 2 |
| 4 | PharmaSafe AI | 5 | Week 33-34 | Phases 0, 1 |
| 5 | Model routing + observability + eval | 4 | Week 34-35 | Phases 2, 4 |
| 6 | UI + deployment + CI/CD | 5 | Week 35-37 | All above |
| **Total** | | **35 days** | **~10 weeks** | |

### Mapping to Roadmap Weeks

```
Roadmap Week 27: Phase 0 (scaffold) ← overlaps with Project 3 week
Roadmap Week 28: Phase 0 (finish) + Phase 1 (ClinFlow start)
Roadmap Week 29: Phase 1 (finish) + Phase 2 (ClinicalTriage start)
Roadmap Week 30: Phase 2 (agents + pipeline)
Roadmap Week 31: Phase 2 (finish) + Phase 3 (memory start)
Roadmap Week 32: Phase 3 (memory + dreaming)
Roadmap Week 33: Phase 4 (PharmaSafe)
Roadmap Week 34: Phase 4 (finish) + Phase 5 (model routing + eval)
Roadmap Week 35: Phase 5 (finish) + Phase 6 (UI start)
Roadmap Week 36: Phase 6 (deployment + CI/CD)
Roadmap Week 37: Phase 6 (finish) + polish + demo recording
```

**Note:** This build window (Weeks 27-37) coincides with Phase 6 (Production AI Infrastructure) and Phase 7 (Fine-Tuning) of the roadmap. The Category 6 projects directly apply the skills being learned in those weeks — model serving, K8s patterns, observability — so there is strong alignment rather than conflict.

### Realistic Pacing

At 20 hrs/week (standard pace):
- Each "day" = ~4 hours of focused work
- 35 days = 140 hours = 7 weeks at 20 hrs/week
- With buffer for debugging and iteration: **9-10 weeks**

At 40 hrs/week (accelerated):
- 35 days = 140 hours = 3.5 weeks at 40 hrs/week
- With buffer: **5 weeks**

### Minimum Viable Demo (Week 31)

After Phases 0-2, you have a deployable system that:
- Accepts PDF uploads via API
- Classifies documents into types
- Extracts structured data with specialist agents
- Validates extractions with feedback loops
- Generates reports with provenance
- Full audit trail
- Checkpoint/recovery

This is enough to demo for an interview. Phases 3-6 add depth (memory, PharmaSafe, observability, UI) that strengthens the portfolio but are not blocking for a first demo.

---

## Appendix A: Key Architecture Decisions

| Decision | Choice | Alternative Considered | Rationale |
|---|---|---|---|
| Monorepo vs multi-repo | Monorepo with uv workspaces | Separate repos per project | Shared schemas, easier local dev, single Docker Compose |
| Orchestration | LangGraph | Custom state machine | LangGraph provides checkpointing, conditional edges, and human-in-the-loop out of the box. ClinFlow wraps it with YAML definitions. |
| Vector store | pgvector (in PostgreSQL) | Qdrant, Pinecone, ChromaDB | Fewer infrastructure dependencies. PostgreSQL already needed for workflow state + audit. pgvector HNSW is production-quality. |
| Knowledge graph | Neo4j | ArangoDB, memgraph | Industry standard for clinical ontologies. Best Cypher query language. APOC plugin for graph algorithms. |
| Embedding model | sentence-transformers (local) | OpenAI embeddings | No data leaves the VPC. Important for PHI sensitivity. |
| Episodic memory storage | Markdown files on filesystem | PostgreSQL | Human-readable for debugging. Easy to browse. Low overhead. Git-trackable if desired. |
| Observability | LangFuse | LangSmith | Self-hostable (important for clinical data). Open source. |

## Appendix B: Risk Register

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Claude API rate limits during high-volume processing | High | Medium | Implement exponential backoff, request queuing, and model fallback to Haiku or local model |
| PDF extraction quality varies wildly across document formats | High | High | OCR fallback, multiple extraction attempts, human-in-the-loop for low-confidence, procedural memory for known formats |
| Neo4j cold start / seed data quality | Medium | Medium | Script seed data from authoritative sources (RxNorm, DrugBank). Validate graph integrity in CI. |
| Dreaming consolidation promotes low-quality entries | Medium | Low | Strict promotion threshold (0.6). Human review of first 5 consolidation runs. Forgetting curve as safety net. |
| LangGraph version breaking changes | Medium | Low | Pin exact version. Integration tests catch regressions. Wrap LangGraph in ClinFlow abstraction layer. |
| Context window limits with large clinical documents | High | Medium | Chunk documents by page/section. Summarize before passing to agents. Use map-reduce pattern for large docs. |
| OpenFDA API downtime | Low | Medium | Cache results in Redis. Graceful degradation: skip API source, note in report that API data is missing. |

---

*This plan is designed to be executed incrementally. Each phase produces a working, testable system. Start with Phase 0, verify it works, then proceed. Do not plan further ahead than you can see clearly.*
```

---

The document above is the complete implementation plan. Here is a summary of the key files and decisions:

**File to save:** `d:\8.AsadHanif-Personal\5.Applied-AI-Engineer-Roadmap-Personal\18.implementation-plan-category6-clinical-ai.md`

**Key architectural decisions in the plan:**
- Single monorepo with `uv` workspaces -- five packages (`shared`, `clinflow`, `memory`, `triage`, `pharma`)
- ClinFlow built first as shared orchestration layer, consumed by both ClinicalTriage and PharmaSafe
- pgvector inside PostgreSQL rather than a separate vector database (fewer infrastructure dependencies)
- Neo4j for knowledge graph with drug-condition-enzyme multi-hop reasoning
- Episodic memory as Markdown files on filesystem (human-readable, debuggable)
- LangFuse self-hosted for observability (clinical data sensitivity)

**Minimum viable demo at Phase 2 completion (~Week 31):** Document upload, classification, extraction with specialist agents, validation with feedback loops, report generation, audit trail, checkpoint/recovery.

**Total estimated effort:** 35 focused days (~140 hours), mapping to roadmap Weeks 27-37.

**Relevant existing files referenced during planning:**
- `d:\8.AsadHanif-Personal\5.Applied-AI-Engineer-Roadmap-Personal\15.Impressive-AI-Engineering-Project-Ideas-for-Your-Portfolio.md` -- Category 6 project descriptions (lines 209-276)
- `d:\8.AsadHanif-Personal\5.Applied-AI-Engineer-Roadmap-Personal\17.interview-prep-jd45-agentic-ai-engineer.md` -- JD 45 requirements mapping and 5-layer memory details
- `d:\8.AsadHanif-Personal\5.Applied-AI-Engineer-Roadmap-Personal\10.PROGRESS.md` -- Roadmap timeline (Phases 6-7 at Weeks 27-36)
- `d:\8.AsadHanif-Personal\5.Applied-AI-Engineer-Roadmap-Personal\01.ai-enginerr-job-descriptions.md` -- JD 45 full text (line 2271)