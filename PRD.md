# Product Requirements Document
# Clinical AI Platform — Agentic AI System for Clinical & Life-Sciences Workflows

**Version:** 1.0  
**Date:** May 25, 2026  
**Author:** Asad Hanif  
**Status:** Approved — Ready for Implementation  
**Implementation Plan:** See [`18.implementation-plan-category6-clinical-ai.md`](../../18.implementation-plan-category6-clinical-ai.md)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [User Personas](#4-user-personas)
5. [System Overview & Architecture](#5-system-overview--architecture)
6. [Product Components](#6-product-components)
   - 6.1 [ClinFlow AI — Workflow Orchestration Engine](#61-clinflow-ai--workflow-orchestration-engine)
   - 6.2 [ClinicalTriage AI — Document Pipeline](#62-clinicaltriage-ai--document-pipeline)
   - 6.3 [PharmaSafe AI — Drug Interaction Checker](#63-pharmasafe-ai--drug-interaction-checker)
   - 6.4 [5-Layer Memory System](#64-5-layer-memory-system)
   - 6.5 [UI — Chainlit (Next.js Upgrade Path)](#65-ui--chainlit-nextjs-upgrade-path)
7. [Functional Requirements](#7-functional-requirements)
8. [Non-Functional Requirements](#8-non-functional-requirements)
9. [Tech Stack](#9-tech-stack)
10. [API Surface](#10-api-surface)
11. [Data Models](#11-data-models)
12. [Success Metrics & Acceptance Criteria](#12-success-metrics--acceptance-criteria)
13. [Out of Scope](#13-out-of-scope)
14. [Risks & Mitigations](#14-risks--mitigations)
15. [Build Timeline](#15-build-timeline)
16. [Open Questions](#16-open-questions)

---

## 1. Executive Summary

The **Clinical AI Platform** is a monorepo of three interconnected agentic AI systems designed for clinical and life-sciences environments. It demonstrates production-grade, regulated-environment AI engineering using multi-agent orchestration, hybrid memory systems, and Anthropic Claude as the primary LLM.

The platform is built as a **portfolio project** targeting Agentic AI Engineer roles (JD 45-style) and secondarily as a generalizable framework for any regulated-environment AI use case.

**Three products, one platform:**

| Product | What It Does | Role in Platform |
|---|---|---|
| **ClinFlow AI** | Configurable workflow orchestration engine | Shared infrastructure layer |
| **ClinicalTriage AI** | Ingests clinical documents, extracts and validates structured data | Flagship product |
| **PharmaSafe AI** | Checks drug interactions using multiple data sources | Companion product |

---

## 2. Problem Statement

Clinical and life-sciences organisations process large volumes of heterogeneous documents — lab reports, clinical notes, trial summaries, adverse event forms — manually or with brittle rule-based systems. Drug interaction checking is fragmented across multiple databases and requires specialist expertise.

**Core pain points this platform addresses:**

1. **Manual document processing** is slow, error-prone, and does not scale. Clinicians spend significant time extracting structured data from unstructured documents.
2. **Lack of auditability** in AI-assisted workflows creates regulatory compliance risk. Existing AI tools do not produce traceable, human-reviewable decision chains.
3. **Drug interaction knowledge is siloed.** Checking against one database misses interactions documented elsewhere. Cross-validation across sources is manual.
4. **No memory continuity.** AI tools today are stateless — they do not learn from past interactions, accumulate domain knowledge over time, or remember what worked for a given document format.
5. **Workflow inflexibility.** Changing a clinical workflow requires code changes. Non-engineers cannot modify routing logic or approval requirements.

---

## 3. Goals & Non-Goals

### Goals

- Build a **production-quality, demo-deployable** multi-agent system that directly demonstrates JD 45 requirements
- Implement **all three agentic design patterns** in one system: planning loops (intake → route), execution loops (extract → validate → retry), and validation loops (schema + RAG cross-reference)
- Demonstrate **5-layer OpenClaw-inspired memory architecture** including automated dreaming consolidation
- Implement **multi-model Claude routing** (Opus / Haiku / local) with fallback chains and PHI-aware routing
- Ship with **full observability** (LangFuse traces, Prometheus metrics, structured logging, per-workflow cost tracking)
- Maintain **complete audit trails** suitable for regulated-environment review
- **Human-in-the-loop** at every low-confidence decision point
- UI in **Chainlit** with a documented **Next.js upgrade path** that requires zero backend changes

### Non-Goals

- This is **not a production clinical product** — it does not claim regulatory certification (HIPAA, CE Mark, FDA clearance)
- This is **not a real-time system** — latency targets are for demo purposes, not clinical SLAs
- **Not a general-purpose AI assistant** — it solves specific document processing and drug interaction use cases
- **No real PHI** will be used in development or testing — all test data is synthetic or de-identified
- **Not multi-tenant** in v1 — single-organisation deployment only
- **No fine-tuning** of Claude models — prompt engineering and RAG only in this version

---

## 4. User Personas

### Primary: Asad (the Builder / Portfolio Reviewer Proxy)
The developer building this system. Needs the codebase to be clean, well-tested, and demonstrable in a 45-minute technical interview. Every design decision should be explainable and defensible.

### Secondary: Clinical Researcher (Demo Persona)
Uses ClinicalTriage AI to process batches of trial documents. Needs to upload PDFs, review extracted data, approve or correct low-confidence extractions, and receive structured reports. Values accuracy and auditability over speed.

### Secondary: Clinical Pharmacist (Demo Persona)
Uses PharmaSafe AI to check medication lists before prescribing. Needs a clear severity-ranked report with evidence citations. Must be able to escalate to human review for high-risk flagged interactions.

### Secondary: Operations Lead (Demo Persona)
Uses the analytics dashboard to monitor AI agent utilisation, workflow throughput, validation pass rates, and cost per workflow. Needs clear visibility into pending human reviews.

---

## 5. System Overview & Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    clinical-ai-platform (monorepo)                  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │            ClinFlow AI — Shared Orchestration Layer          │   │
│  │  YAML workflow definitions · checkpoint/recovery · audit     │   │
│  │  human approval gateways · dynamic routing · analytics       │   │
│  └───────────┬──────────────────────────────┬──────────────────┘   │
│              │                              │                       │
│  ┌───────────▼──────────────┐  ┌───────────▼──────────────────┐   │
│  │   ClinicalTriage AI      │  │   PharmaSafe AI               │   │
│  │   (Flagship)             │  │   (Companion)                 │   │
│  │   Intake → Extract →     │  │   Input → Check → Retrieve →  │   │
│  │   Validate → Report      │  │   Cross-validate → Report     │   │
│  └──────────────────────────┘  └───────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Shared Infrastructure (packages/shared)                     │   │
│  │  5-layer memory · model router · LangFuse · Pydantic schemas │   │
│  │  pgvector client · Neo4j client · Redis · audit writer       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────┐  ┌────────────────────────────────────────────┐  │
│  │  FastAPI     │  │  Chainlit UI                                │  │
│  │  /api/v1/*   │  │  (Next.js upgrade: ui-next/ — zero backend │  │
│  │              │  │   changes required)                         │  │
│  └──────────────┘  └────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘

Infrastructure: PostgreSQL + pgvector · Neo4j · Redis · LangFuse (self-hosted)
Deployment: Docker Compose (local) · Kubernetes (production)
```

**Request flow — ClinicalTriage AI (happy path):**
```
PDF Upload → FastAPI /triage/submit
  → Intake Agent (classify: lab_report)
    → Lab Report Agent (extract: values, ranges, flags)
      → Validation Agent (schema check + RAG cross-ref)
        → PASS: Report Agent (JSON + human-readable report)
        → FAIL (low confidence): Human-in-the-loop gateway
          → Clinician approves/rejects/edits
            → Resume workflow
  → Audit trail written at every step
  → Episodic memory logged
  → LangFuse trace captured
```

---

## 6. Product Components

### 6.1 ClinFlow AI — Workflow Orchestration Engine

**Purpose:** Shared orchestration infrastructure consumed by ClinicalTriage AI and PharmaSafe AI. Provides configurable, auditable, resumable workflow execution.

**Core capabilities:**
- **YAML/JSON workflow definitions** — non-engineers can define workflows by editing config files, no code changes required
- **Dynamic routing** — at each node, evaluates output against configurable rules (threshold scores, field presence, error codes) to choose the next step
- **Checkpoint & recovery** — full workflow state persisted at every node transition; any workflow can be resumed after failure, restart, or deployment
- **Human approval gateway** — pause execution, notify reviewer (email/Slack webhook), surface agent's work and reasoning in UI, resume on approval or route to remediation on rejection
- **Immutable audit trail** — every execution logged: who triggered it, which agents ran, inputs/outputs, human decisions, timestamps, model versions
- **Workflow analytics** — throughput, per-node latency, bottleneck identification, approval rates, failure/retry patterns

**Built-in workflow definitions:**
- `clinical_triage.yml` — document classification, extraction, validation, report generation
- `pharma_check.yml` — medication input, interaction check, literature retrieval, cross-validation, risk report
- `_template.yml` — starter template for new workflows

### 6.2 ClinicalTriage AI — Document Pipeline

**Purpose:** Ingests clinical documents, routes them to specialist extraction agents, validates extractions, and generates auditable structured reports.

**Agent pipeline:**

| Agent | Responsibility | Model |
|---|---|---|
| Intake Agent | Classify document type, route to specialist | Claude Haiku |
| Lab Report Agent | Extract test names, values, reference ranges, abnormal flags | Claude Haiku (structured output) |
| Clinical Note Agent | Extract diagnoses (ICD-10), medications, procedures, follow-up | Claude Sonnet (complex structure) |
| Trial Summary Agent | Extract endpoints, population, results, statistical markers | Claude Opus (complex reasoning) |
| Adverse Event Agent | Extract event description, severity, causality assessment | Claude Sonnet |
| Validation Agent | Schema check (Pydantic) + RAG cross-reference against clinical KB | Claude Haiku |
| Report Agent | Produce structured JSON + human-readable report with provenance | Claude Haiku |

**Key behaviours:**
- Validation failures route back to the extraction agent with specific feedback (retry loop, max 3 attempts)
- Low-confidence extractions (< 0.70) trigger human-in-the-loop review
- PHI-sensitive documents routed to local open-weight model that does not leave the VPC
- Every extraction carries provenance: document ID, page number, bounding box (if available)

**Document types supported (v1):**
- Lab reports (PDF, structured)
- Clinical notes (free text, PDF)
- Clinical trial summaries (PDF)
- Adverse event forms (PDF, structured)

### 6.3 PharmaSafe AI — Drug Interaction Checker

**Purpose:** Takes a patient's medication list and conditions, queries multiple data sources, cross-validates findings, and produces a severity-ranked risk assessment.

**Agent pipeline:**

| Agent | Responsibility | Data Source |
|---|---|---|
| Input Processing Agent | Normalise drug names (RxNorm), resolve ambiguities | RxNorm API |
| Drug Interaction Checker | Query interaction data, retrieve severity ratings | OpenFDA API |
| Literature Retrieval Agent | Retrieve relevant clinical guideline passages | RAG over guidelines KB |
| Cross-Validation Agent | Compare API vs. literature, flag conflicts, assign confidence | Claude Opus |
| Risk Assessment Reporter | Produce severity-ranked report with citations and recommendations | Claude Sonnet |

**Knowledge graph integration:** Neo4j graph stores drug-condition-enzyme relationships. Supports multi-hop reasoning (e.g.: Drug A inhibits CYP3A4 → which metabolises Drug B → leading to elevated Drug B plasma levels in patients with Condition C).

**Output:** Structured JSON report with severity-ranked interactions (CRITICAL / HIGH / MODERATE / LOW), evidence citations, recommended actions (discontinue / adjust dose / monitor), and a narrative summary.

**Escalation:** Interactions rated CRITICAL or HIGH, or where API and literature findings conflict, trigger human pharmacist review.

### 6.4 5-Layer Memory System

**Architecture (OpenClaw-inspired):**

| Layer | Storage | Purpose |
|---|---|---|
| **Working memory** | In-process (LangGraph state) | Active context for current document or query |
| **Episodic memory** | Markdown files on filesystem (`data/episodic_logs/YYYY-MM-DD.md`) | Chronological session logs — what happened, when, which agents made which decisions |
| **Long-term memory** | pgvector (embeddings) + Neo4j (graph) | Curated durable knowledge — document embeddings for retrieval, entity relationships for reasoning |
| **Procedural memory** | JSON files (`data/procedural_templates/`) | Learned extraction templates per document format — e.g. "this lab format always has results in column 3" |
| **Index layer** | BM25 (full-text) + pgvector (semantic) | Dual-channel retrieval over all memory layers |

**Dreaming — Memory Consolidation:**
A nightly background process that consolidates episodic memory into long-term memory using a three-phase bio-inspired cycle:

1. **Light Sleep** — Scan recent episodic logs, parse into snippet chunks, deduplicate using Jaccard similarity, build candidate list without modifying core memory
2. **REM Sleep** — Reflect on staged candidates, extract recurring patterns and themes, understand *why* something was said (not just *what*)
3. **Deep Sleep** — Score candidates using importance formula, promote survivors to long-term memory, apply forgetting curve to decay stale entries

**Importance scoring formula:**
```
importance = base_weight × recency_factor × reference_boost

Where:
  base_weight    = relevance (0.30) + frequency (0.24) + query_diversity (0.15) + other signals
  recency_factor = exp(-λ × days_since_created)    # λ = 0.1 (configurable)
  reference_boost = 1 + (0.1 × times_referenced)

Promotion threshold: importance ≥ 0.60
```

### 6.5 UI — Chainlit (Next.js Upgrade Path)

**Primary UI: Chainlit**

Chainlit is used as the primary UI because it is purpose-built for agentic AI workflows — it natively supports streaming agent steps, tool call visualisation, and action-button-based human-in-the-loop interactions.

**Chainlit views:**
- **Document upload** — chat-based upload flow with real-time classification feedback via `cl.Step`
- **Extraction review** — formatted extraction display with APPROVE / REJECT / EDIT `cl.Action` buttons for HITL approval gateway
- **Drug checker** — conversational medication input, severity-coloured confidence badges, expandable evidence per interaction
- **Workflow monitor** — live node-by-node status via streaming `cl.Step`, pending human approvals as clickable actions
- **Audit explorer** — query logs conversationally, full trace as expandable steps
- **Memory inspector** — browse episodic logs, search long-term memory, view dreaming consolidation stats
- **Analytics** — throughput, per-agent latency, validation pass rates, cost per workflow

**Next.js upgrade path (ui-next/):**
The FastAPI backend is UI-agnostic. Switching to Next.js 14 requires:
1. Create `ui-next/` with Next.js 14 app router
2. Pages: `/dashboard`, `/triage`, `/pharma`, `/audit`, `/memory`
3. Set `NEXT_PUBLIC_API_URL` to the running FastAPI instance
4. Zero backend changes required

---

## 7. Functional Requirements

### FR-1: Document Ingestion (ClinicalTriage AI)
- FR-1.1: Accept PDF uploads via REST API (`POST /api/v1/triage/submit`)
- FR-1.2: Accept batch uploads (up to 20 documents per request)
- FR-1.3: Classify document into one of: `lab_report`, `clinical_note`, `trial_summary`, `adverse_event`, `unknown`
- FR-1.4: Route `unknown` documents to human review, not to extraction agents

### FR-2: Data Extraction (ClinicalTriage AI)
- FR-2.1: Extract all required fields per document type (see Data Models section)
- FR-2.2: Return confidence score (0.0–1.0) per extracted field
- FR-2.3: Retry extraction up to 3 times with validation feedback before escalating to human
- FR-2.4: Track provenance (source document ID, page number) for every extracted value

### FR-3: Validation (ClinicalTriage AI)
- FR-3.1: Validate all extractions against Pydantic schema — reject on schema failure
- FR-3.2: Cross-reference extracted entities against clinical knowledge base (RAG)
- FR-3.3: Return PASS/FAIL/HUMAN_REVIEW status with a confidence score and specific failure reasons
- FR-3.4: Trigger human-in-the-loop for confidence < 0.70

### FR-4: Drug Interaction Checking (PharmaSafe AI)
- FR-4.1: Accept medication list + patient conditions via REST API
- FR-4.2: Normalise all drug names to RxNorm standard identifiers
- FR-4.3: Query OpenFDA for known interactions between all drug pairs
- FR-4.4: Retrieve supporting literature from RAG knowledge base
- FR-4.5: Cross-validate API and literature findings; flag conflicts
- FR-4.6: Produce a severity-ranked report (CRITICAL / HIGH / MODERATE / LOW)
- FR-4.7: Escalate CRITICAL interactions to human pharmacist review

### FR-5: Workflow Orchestration (ClinFlow AI)
- FR-5.1: Execute any workflow defined in YAML format without code changes
- FR-5.2: Persist checkpoint state at every node transition
- FR-5.3: Resume any workflow from its last checkpoint after system restart
- FR-5.4: Support parallel branch execution (fan-out) and merge (fan-in)
- FR-5.5: Notify designated reviewer when a human approval gateway is reached
- FR-5.6: Resume workflow within 60 seconds of receiving an approval/rejection decision

### FR-6: Memory System
- FR-6.1: Log every processing session to episodic memory (date-stamped Markdown file)
- FR-6.2: Run dreaming consolidation nightly (default 02:00 UTC, configurable)
- FR-6.3: Promote entries with importance ≥ 0.60 to long-term memory
- FR-6.4: Apply forgetting curve to entries not accessed for 30+ days
- FR-6.5: Expose memory query API (`GET /api/v1/memory/search?q=...`)

### FR-7: Audit Trail
- FR-7.1: Write an immutable audit entry for every agent execution (input, output, model, timestamp, duration)
- FR-7.2: Write audit entries for all human approval decisions (reviewer, decision, timestamp, justification)
- FR-7.3: Expose audit query API with filtering by date range, workflow ID, agent type
- FR-7.4: Support CSV export of audit logs for compliance review

### FR-8: UI
- FR-8.1: All core workflows accessible via Chainlit interface
- FR-8.2: Human-in-the-loop approvals surfaced as `cl.Action` buttons — no need to use the API directly
- FR-8.3: Real-time workflow status visible via streaming `cl.Step`
- FR-8.4: Next.js upgrade path scaffolded in `ui-next/` with README

---

## 8. Non-Functional Requirements

### Performance
- Document classification (Intake Agent): < 3 seconds p95
- Full triage pipeline (upload to report, no HITL): < 30 seconds p95
- Drug interaction check (5 medications): < 20 seconds p95
- Memory search query: < 500ms p95
- Audit log write: < 100ms (async, non-blocking)

### Reliability
- Workflow checkpoint saved at every node — zero loss on crash
- Any failed workflow can be resumed from last checkpoint
- Model fallback chain: Claude Opus → Claude Haiku → local model → graceful error
- OpenFDA API failure: degrade gracefully (log warning, note missing source in report, continue)

### Security
- API key authentication on all endpoints
- PHI-sensitive documents never sent to external LLM APIs — routed to local model only
- Audit logs are append-only (no UPDATE or DELETE)
- Secrets loaded from environment variables, never hardcoded
- `.env` file gitignored; `.env.example` provided as template

### Observability
- Every LLM call traced in LangFuse (model, tokens, latency, cost)
- Prometheus metrics exposed at `/metrics`
- Structured JSON logs with correlation IDs for every request
- Per-workflow cost tracked and stored in audit log

### Scalability (demo scope)
- Single-instance deployment sufficient for demo
- Architecture supports horizontal scaling via stateless API + external state stores (PostgreSQL, Redis, Neo4j)

### Testability
- Unit test coverage ≥ 80% for all packages
- Integration tests cover happy path + failure paths for all three pipelines
- Evaluation tests run on golden test sets in CI — fail PR if extraction F1 drops below 0.80

---

## 9. Tech Stack

| Layer | Technology | Version | Rationale |
|---|---|---|---|
| Language | Python | 3.12 | Latest stable; required by JD 45 |
| Package manager | uv (workspace) | latest | Fastest Python package manager; workspace support for monorepo |
| Web framework | FastAPI | >=0.115 | Async, Pydantic v2 native, OpenAPI auto-docs |
| LLM orchestration | LangGraph | >=0.3.0 | Stateful graphs, checkpointing, conditional edges, HITL |
| LLM provider | Anthropic Claude | >=0.42.0 | JD 45 explicitly requires Claude production experience |
| LLM routing | Custom (packages/shared/llm/router.py) | — | Opus/Haiku/local selection + fallback chains |
| Vector store | pgvector (PostgreSQL extension) | >=0.3.6 | In PostgreSQL — fewer infra dependencies; HNSW production-quality |
| Knowledge graph | Neo4j | >=5.27.0 | Industry standard for clinical ontologies; Cypher query language |
| Cache & queue | Redis | >=5.2.0 | Task queue for async jobs; result caching; pub/sub |
| Database | PostgreSQL | 16 | Workflow state, audit trail, long-term memory tables |
| Document parsing | PyMuPDF (fitz) | >=1.25.0 | Best Python PDF library; fast; handles complex layouts |
| Embeddings | sentence-transformers | >=3.3.0 | Local — no data leaves VPC; good clinical text quality |
| Observability | LangFuse | >=2.60.0 | Self-hostable (critical for clinical data); open source |
| Metrics | prometheus-client | >=0.21.0 | Standard Prometheus exposition format |
| Validation | Pydantic v2 | >=2.10.0 | Required throughout; v2 for performance |
| UI (primary) | Chainlit | >=1.3.0 | Built for agentic AI; HITL Actions; streaming Steps |
| UI (upgrade path) | Next.js 14 | latest | App router; Shadcn/ui; same FastAPI backend |
| Containerisation | Docker + Docker Compose | — | Local dev environment |
| Orchestration | Kubernetes + Helm | — | Production deployment; leverages existing DevOps background |
| CI/CD | GitHub Actions | — | Lint, test, evaluate, deploy pipeline |

---

## 10. API Surface

### ClinicalTriage AI
```
POST   /api/v1/triage/submit          # Upload document(s) for triage
GET    /api/v1/triage/{job_id}        # Get job status and result
POST   /api/v1/triage/{job_id}/review # Submit human review decision (APPROVE/REJECT/EDIT)
GET    /api/v1/triage/{job_id}/report # Download final structured report
```

### PharmaSafe AI
```
POST   /api/v1/pharma/check           # Submit medication list + conditions
GET    /api/v1/pharma/{job_id}        # Get check status and result
POST   /api/v1/pharma/{job_id}/review # Submit pharmacist review decision
GET    /api/v1/pharma/{job_id}/report # Download risk assessment report
```

### ClinFlow AI (Workflow Engine)
```
GET    /api/v1/workflows              # List workflow definitions
GET    /api/v1/workflows/{name}       # Get workflow definition + schema
GET    /api/v1/workflows/runs         # List active and recent workflow runs
GET    /api/v1/workflows/runs/{id}    # Get run status, current node, checkpoint
POST   /api/v1/workflows/runs/{id}/resume  # Resume a paused HITL workflow
```

### Memory
```
GET    /api/v1/memory/episodic        # List episodic log files by date
GET    /api/v1/memory/episodic/{date} # Get full episodic log for a date
GET    /api/v1/memory/search          # Search long-term memory (semantic + keyword)
GET    /api/v1/memory/procedural      # List learned extraction templates
GET    /api/v1/memory/consolidation   # Get dreaming consolidation stats and history
```

### Audit
```
GET    /api/v1/audit                  # Query audit logs (filter: date, workflow_id, agent)
GET    /api/v1/audit/{entry_id}       # Get single audit entry
GET    /api/v1/audit/export           # Export filtered audit logs as CSV
```

### System
```
GET    /health                        # Liveness probe
GET    /ready                         # Readiness probe (checks DB, Redis, Neo4j)
GET    /metrics                       # Prometheus metrics
```

---

## 11. Data Models

### Core Document Models
```python
class DocumentType(str, Enum):
    LAB_REPORT = "lab_report"
    CLINICAL_NOTE = "clinical_note"
    TRIAL_SUMMARY = "trial_summary"
    ADVERSE_EVENT = "adverse_event"
    UNKNOWN = "unknown"

class DocumentInput(BaseModel):
    document_id: str              # UUID assigned on upload
    filename: str
    content_type: str             # "application/pdf"
    phi_sensitive: bool = False   # If True → route to local model only
    metadata: dict[str, Any] = {}

class ExtractionResult(BaseModel):
    document_id: str
    document_type: DocumentType
    fields: dict[str, Any]        # Type-specific extracted fields
    confidence_scores: dict[str, float]  # Per-field confidence
    provenance: list[ProvenanceRecord]   # Source page/location per field
    model_used: str
    extracted_at: datetime
```

### Validation Models
```python
class ValidationStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    HUMAN_REVIEW = "human_review"

class ValidationResult(BaseModel):
    document_id: str
    status: ValidationStatus
    overall_confidence: float     # 0.0–1.0
    field_results: dict[str, bool]
    failures: list[str]           # Specific failure reasons
    rag_references: list[str]     # Knowledge base entries used for cross-reference
    feedback: str | None          # Feedback to extraction agent on retry
```

### Memory Models
```python
class EpisodicEntry(BaseModel):
    session_id: str
    timestamp: datetime
    agent: str
    action: str
    input_summary: str
    output_summary: str
    outcome: str                  # "success" | "failure" | "human_review"
    confidence: float | None

class LongTermEntry(BaseModel):
    entry_id: str
    content: str
    embedding: list[float]        # pgvector
    importance_score: float
    created_at: datetime
    last_accessed: datetime
    access_count: int
    source_episodes: list[str]    # Episode IDs that contributed to this entry

class ProceduralTemplate(BaseModel):
    template_id: str
    document_type: DocumentType
    format_fingerprint: str       # Hash of document structure pattern
    extraction_hints: dict[str, Any]  # Field → location/pattern mapping
    success_rate: float
    last_updated: datetime
```

### Workflow & Audit Models
```python
class WorkflowState(BaseModel):
    run_id: str
    workflow_name: str
    status: str                   # "running" | "paused" | "completed" | "failed"
    current_node: str
    checkpoint: dict[str, Any]    # Full LangGraph state snapshot
    started_at: datetime
    updated_at: datetime

class AuditLogEntry(BaseModel):
    entry_id: str                 # Immutable UUID
    run_id: str
    agent: str
    node: str
    input_hash: str               # SHA-256 of input (not stored raw — privacy)
    output_summary: str
    model_used: str
    tokens_used: int
    cost_usd: float
    duration_ms: int
    timestamp: datetime           # UTC
    human_decision: str | None    # If HITL node
    human_reviewer: str | None
```

---

## 12. Success Metrics & Acceptance Criteria

### ClinicalTriage AI
| Metric | Target | How Measured |
|---|---|---|
| Document classification accuracy | ≥ 95% | Golden test set (40 documents) |
| Extraction F1 score (per field) | ≥ 0.80 | Golden test set evaluation (`eval_extraction.py`) |
| Validation false positive rate | ≤ 10% | Golden test set |
| End-to-end pipeline latency (p95) | ≤ 30s | Load test (`locustfile.py`) |
| Checkpoint recovery success rate | 100% | Integration test (`test_checkpoint_recovery.py`) |

### PharmaSafe AI
| Metric | Target | How Measured |
|---|---|---|
| Known interaction detection accuracy | ≥ 90% | Golden test set (10 medication lists) |
| CRITICAL/HIGH interaction recall | 100% | Must not miss any high-severity interactions |
| Cross-validation conflict detection | Tested | Manual review of known conflict cases |

### Memory System
| Metric | Target | How Measured |
|---|---|---|
| Dreaming consolidation runs without error | 100% | Integration test (`test_memory_consolidation.py`) |
| Importance scoring promotes correct entries | Verified | Manual review of first 5 consolidation runs |
| Memory search latency (p95) | ≤ 500ms | Unit test with synthetic data |

### Platform
| Metric | Target |
|---|---|
| Unit test coverage | ≥ 80% across all packages |
| All integration tests pass | Required for PR merge |
| Evaluation tests pass (F1 ≥ 0.80) | Required for PR merge |
| Docker Compose brings up all services in ≤ 60s | Verified manually |
| Live Chainlit demo with real PDF | Required before portfolio submission |

---

## 13. Out of Scope

- **Real regulatory compliance** (HIPAA BAA, CE Mark, FDA 510(k)) — this is a portfolio project
- **Real PHI data** — all test documents are synthetic or de-identified
- **Multi-tenancy** — single organisation, single deployment in v1
- **Fine-tuning** — no model fine-tuning; prompt engineering + RAG only
- **Voice interface** — text/file input only in v1
- **Billing / cost management** — cost tracking is for observability, not metering
- **User authentication system** — API key auth only; no user accounts or RBAC in v1
- **FHIR integration** — standard clinical data format; relevant but out of scope for v1
- **Real-time streaming of extraction progress** — batch processing only in v1

---

## 14. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Claude API rate limits during high-volume demo | High | Medium | Exponential backoff, request queuing, model fallback to Haiku or local |
| PDF extraction quality varies wildly across document formats | High | High | OCR fallback (pytesseract), multiple extraction attempts, HITL for low-confidence, procedural memory for known formats |
| Neo4j cold start / seed data quality | Medium | Medium | Seed scripts from authoritative sources (RxNorm, OpenFDA). Validate graph integrity in CI. |
| Dreaming promotes low-quality entries to long-term memory | Medium | Low | Strict threshold (0.60). Human review of first 5 consolidation runs. Forgetting curve as safety net. |
| LangGraph breaking changes between versions | Medium | Low | Pin exact version in `uv.lock`. Integration tests catch regressions. ClinFlow wraps LangGraph — one place to fix. |
| Context window limits with large clinical documents | High | Medium | Chunk by page/section. Summarise before passing to agents. Use map-reduce for large docs. |
| OpenFDA API downtime during demo | Low | Medium | Cache results in Redis (24h TTL). Graceful degradation: note missing source in report, continue. |
| Dreaming cron job conflicts with active workflow runs | Low | Low | Acquire advisory lock before starting consolidation. Skip if lock not available — retry next night. |

---

## 15. Build Timeline

| Phase | What Gets Built | Days | Roadmap Weeks |
|---|---|---|---|
| 0 | Monorepo scaffold, shared infra, Docker Compose, health endpoints | 3 | 27–28 |
| 1 | ClinFlow AI core (workflow engine, YAML parser, checkpoint, HITL gateway, audit) | 5 | 28–29 |
| 2 | ClinicalTriage AI (all agents, LangGraph graph, validation loop, report generation) | 8 | 29–31 |
| 3 | 5-layer memory system including dreaming consolidation | 5 | 31–32 |
| 4 | PharmaSafe AI (all agents, Neo4j integration, cross-validation, risk report) | 5 | 33–34 |
| 5 | Model routing layer, LangFuse observability, golden set evaluation, CI integration | 4 | 34–35 |
| 6 | Chainlit UI, ui-next/ scaffold, Dockerfile, K8s manifests, GitHub Actions | 5 | 35–37 |
| **Total** | | **35 days** | **~10 weeks** |

**Minimum Viable Demo (after Phase 2, Week 31):** PDF upload → classification → extraction → validation → report with audit trail. Sufficient for a technical interview demo.

---

## 16. Open Questions

| # | Question | Owner | Decision Needed By |
|---|---|---|---|
| 1 | Which local open-weight model for PHI routing? (Llama 3.1 8B vs Mistral 7B vs Phi-3 Mini) | Asad | Phase 0 |
| 2 | Self-host LangFuse or use LangFuse Cloud free tier? | Asad | Phase 0 |
| 3 | Use synthetic clinical documents or find open-access de-identified datasets for golden sets? | Asad | Phase 2 |
| 4 | Dreaming consolidation: filesystem Markdown vs PostgreSQL for episodic log storage? | Asad | Phase 3 |
| 5 | Neo4j Community Edition (local Docker) or AuraDB free tier (managed)? | Asad | Phase 0 |
| 6 | Chainlit: deploy as separate service or serve from FastAPI? | Asad | Phase 6 |
| 7 | When to activate Next.js upgrade path — after Phase 6 or leave as scaffold only? | Asad | Phase 6 |

---

*This PRD defines the v1 scope. Changes to scope should be reflected here and in [`18.implementation-plan-category6-clinical-ai.md`](../../18.implementation-plan-category6-clinical-ai.md).*
