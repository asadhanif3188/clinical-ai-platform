# Clinical AI Platform

Agentic AI System for Clinical & Life-Sciences Workflows.

## Overview

A monorepo of three agentic AI systems designed for clinical environments:

- **ClinicalTriage AI** — Multi-agent document pipeline (Classify, Extract, Validate, Report).
- **PharmaSafe AI** — Drug interaction checker using OpenFDA and Neo4j.
- **ClinFlow AI** — Shared workflow orchestration engine powered by LangGraph.

## Architecture

```text
+-----------------------------------------------------------+
|                      Chainlit UI                          |
+---------------------------+-------------------------------+
                            |
                            v
+---------------------------+-------------------------------+
|                      FastAPI API                          |
+---------------------------+-------------------------------+
                            |
        +-------------------+-------------------+
        |                   |                   |
        v                   v                   v
+---------------+   +---------------+   +---------------+
| ClinicalTriage|   |  PharmaSafe   |   |   ClinFlow    |
|      AI       |   |      AI       |   |    Engine     |
+-------+-------+   +-------+-------+   +-------+-------+
        |                   |                   |
        +---------+---------+---------+---------+
                  |                   |
                  v                   v
        +---------+---------+---------+---------+
        |           5-Layer Memory System       |
        |  (Working, Episodic, LTM, Proc, Index)|
        +---------------------------------------+
                  |                   |
        +---------+---------+---------+---------+
        |         Shared Infrastructure         |
        | (DB Clients, LLM Router, Observability)|
        +---------------------------------------+
```

## Quickstart

### Prerequisites

- [uv](https://github.com/astral-sh/uv)
- [Docker](https://www.docker.com/) & Docker Compose
- [Ollama](https://ollama.ai/) (for local PHI routing)

### Setup

1. **Start Infrastructure:**
   ```bash
   docker compose up -d
   ```

2. **Install Dependencies:**
   ```bash
   uv sync
   ```

3. **Run API:**
   ```bash
   uv run uvicorn api.main:app --reload
   ```

4. **Run UI:**
   ```bash
   uv run chainlit run ui/app.py
   ```

## Documentation

- [PRD.md](PRD.md) — Product Requirements
- [CLAUDE.md](CLAUDE.md) — Coding Conventions & Patterns
- [DECISIONS.md](DECISIONS.md) — Architecture Decisions
