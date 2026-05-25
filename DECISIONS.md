# DECISIONS.md — Clinical AI Platform

Architecture Decision Records for all open questions raised in [PRD.md Section 16](PRD.md#16-open-questions).

**How to use this file:**
- Each decision includes a recommendation, rationale, trade-offs, and the concrete impact on implementation
- Review each recommendation, override if needed, then mark `[x] Finalised`
- Once finalised, the BUILD-PLAYBOOK prompts for that phase can be run without ambiguity
- If a decision changes mid-build, update here and note which files are affected

---

## Decision Status

| # | Question | Status | Decided |
|---|---|---|---|
| D-1 | Local model for PHI routing | ✅ Finalised | Phi-3 Mini 3.8B |
| D-2 | LangFuse: self-hosted or Cloud | ✅ Finalised | Self-hosted (Docker Compose) |
| D-3 | Golden sets: synthetic or open-access datasets | ✅ Finalised | Synthetic for v1, with one open-access supplement |
| D-4 | Episodic memory: filesystem Markdown or PostgreSQL | ✅ Finalised | Filesystem Markdown |
| D-5 | Neo4j: Community Edition or AuraDB free tier | ✅ Finalised | Community Edition (Docker) |
| D-6 | Chainlit: separate service or mounted in FastAPI | ✅ Finalised | Separate service |
| D-7 | Next.js upgrade path: when to activate | ✅ Finalised | Full implementation |

Mark status as `✅ Finalised` when decided. Update the "Decided" column with the date.

---

## D-1 — Local Open-Weight Model for PHI Routing

**Needed before:** BUILD-PLAYBOOK Task 0.1 (pyproject.toml), Task 0.2 (Docker Compose), Task 5.1 (ModelRouter)

**Question:** Which local model runs inside the VPC for PHI-sensitive documents that must not leave the environment?

**Options:**

| Model | Size | Strengths | Weaknesses |
|---|---|---|---|
| **Llama 3.1 8B** | ~5GB | Best reasoning quality at 8B class, Meta's instruction tuning is strong, most widely tested for clinical text | Largest of the three options — needs ≥8GB VRAM or slow on CPU |
| **Mistral 7B v0.3** | ~4.1GB | Fast inference, good instruction following, widely supported by Ollama | Slightly weaker on structured output tasks vs Llama 3.1 |
| **Phi-3 Mini 3.8B** | ~2.3GB | Smallest footprint, fast on CPU, surprisingly good reasoning for its size | Less reliable on long documents, smaller context window (4K vs 128K) |

**Recommendation: Llama 3.1 8B**

Rationale:
- Clinical document extraction requires structured output (JSON via tool use) — Llama 3.1 8B handles this more reliably than the smaller alternatives
- 128K context window handles large clinical documents without chunking workarounds
- Most widely tested model in the open-source clinical AI community
- Ollama supports it out of the box: `ollama pull llama3.1:8b`
- For a portfolio project, quality matters more than inference speed — the demo only processes one document at a time

**If your machine has < 8GB VRAM:** Use Phi-3 Mini as fallback. It fits in 4GB VRAM and runs acceptably on CPU. Document this in `.env.example` as an alternative value for `PHI_MODEL`.

**Impact on implementation:**
- `.env.example`: `PHI_MODEL=phi3:mini`
- `docker-compose.yml`: add Ollama service (`ollama/ollama` image, port 11434, GPU passthrough if available)
- `packages/shared/src/clinical_ai_shared/llm/local.py`: client targets Ollama REST API
- `CLAUDE.md` already reflects this choice

- [x] Finalised — Decision: `Phi-3 Mini 3.8B`
  - we'll use it as we are implementing a PoC. 

---

## D-2 — LangFuse: Self-Hosted or Cloud Free Tier

**Needed before:** BUILD-PLAYBOOK Task 0.2 (Docker Compose), Task 5.2 (LangFuse tracing integration)

**Question:** Where does LangFuse run?

**Options:**

| Option | Setup effort | Cost | Data stays local? | Limits |
|---|---|---|---|---|
| **Self-hosted (Docker Compose)** | Medium — add 2 services to docker-compose.yml (langfuse + its postgres) | Free forever | Yes — all trace data on your machine | No limits |
| **LangFuse Cloud free tier** | Low — create account, get API keys, done | Free up to 50K observations/month | No — trace data on LangFuse servers | 50K observations/month, 30-day retention |

**Recommendation: Self-hosted**

Rationale:
- This is a clinical AI platform. Even though no real PHI is used in development, the habit of keeping observability data local is the correct posture for this domain — and it's a talking point in interviews ("I used self-hosted LangFuse because clinical environments can't send trace data to third-party services")
- 50K observations/month is low — a single integration test run can produce hundreds of trace entries
- The `langfuse/langfuse` Docker image works out of the box with a companion PostgreSQL instance
- Self-hosting demonstrates operational maturity (DevOps background advantage)

**If you want simplicity during early development:** Start with Cloud free tier (quicker to set up), then switch to self-hosted before Phase 5. Switching only requires changing 3 environment variables — no code changes.

**Impact on implementation:**
- `docker-compose.yml`: add `langfuse` service (image: `langfuse/langfuse:latest`) + `langfuse-db` PostgreSQL instance
- `.env.example`: `LANGFUSE_HOST=http://localhost:3000` (self-hosted) vs `https://cloud.langfuse.com` (Cloud)
- No code differences — the Python SDK handles both via `LANGFUSE_HOST`

- [x] Finalised — Decision: `Self-hosted`

---

## D-3 — Golden Sets: Synthetic Documents or Open-Access Datasets

**Needed before:** BUILD-PLAYBOOK Task 2.10 (golden test sets)

**Question:** Where do the evaluation documents come from?

**Options:**

| Option | Quality | Setup effort | Legal risk |
|---|---|---|---|
| **Synthetic (programmatically generated)** | Medium — realistic enough to test extraction logic | Low — create with reportlab/fpdf2 | Zero — we own all content |
| **Open-access de-identified datasets** | High — real clinical language, real format variation | Medium — find, download, curate | Low but non-zero — check licence per dataset |

**Available open-access datasets:**
- **MIMIC-III / MIMIC-IV** (PhysioNet) — large de-identified clinical notes, requires credentialing application (1-2 days)
- **n2c2 NLP datasets** — shared task datasets for clinical NLP, includes annotated notes, requires licence agreement
- **MTSamples** — medical transcription samples, free to use, covers many note types

**Recommendation: Synthetic for v1, with one open-access supplement**

Rationale:
- Synthetic documents get you to a working eval pipeline immediately — no waiting for dataset access approval
- Build `scripts/generate_golden_sets.py` that creates realistic-but-fake PDFs using reportlab — this is itself a useful portfolio artefact
- Supplement with 5 notes from **MTSamples** (no approval required, immediately available) for the clinical_notes golden set — this adds real language variation without process overhead
- If time permits, apply for MIMIC access for a richer evaluation in v2

**Synthetic document strategy:**
- Lab reports: generate with realistic test names (CBC, BMP, LFT panels), realistic reference ranges, seeded random values, some intentionally abnormal
- Clinical notes: use SOAP format templates with variable diagnoses, medications, ICD codes
- Trial summaries: use abstract-style templates with realistic endpoint descriptions and p-values

**Impact on implementation:**
- `scripts/generate_golden_sets.py` — builds all synthetic test PDFs + expected JSON
- `tests/evaluation/golden_sets/` — committed to repo (small PDFs, synthetic data only)
- MTSamples notes: download 5 manually, add to `tests/evaluation/golden_sets/clinical_notes/open_access/`, add LICENCE.txt noting source

- [x] Finalised — Decision: `Synthetic for v1, with one open-access supplement`

---

## D-4 — Episodic Memory Storage: Filesystem Markdown or PostgreSQL

**Needed before:** BUILD-PLAYBOOK Task 3.1 (EpisodicMemory implementation)

**Question:** Where are episodic memory session logs stored?

**Options:**

| Option | Readability | Query capability | Complexity | Backup |
|---|---|---|---|---|
| **Filesystem Markdown** | Excellent — open in any editor, browse in GitHub | Low — text search only, no SQL filtering | Low — just file I/O | Standard file backup |
| **PostgreSQL table** | Low — requires DB client to read | Excellent — filter by date, agent, outcome, run SQL | Medium — needs migration, ORM model | DB backup required |

**Recommendation: Filesystem Markdown**

Rationale:
- Directly mirrors the OpenClaw architecture this system is based on — episodic logs are intended to be human-readable by design
- Debugging a failed agent run means opening the log file, not writing a SQL query
- The dreaming consolidation (Light Sleep phase) reads files with Python — no DB overhead
- Git-trackable if desired (small text files, not binary)
- PostgreSQL is already heavily used for workflow state, audit trail, long-term memory, and checkpointing — keeping episodic logs on the filesystem reduces DB load and keeps the data stores conceptually separate
- **Counter-argument addressed:** "What about querying by date range?" — The file path structure `data/episodic_logs/YYYY/MM/DD/session_{run_id}.md` provides date-range access via directory listing, which is sufficient for the dreaming consolidation use case

**File path structure (finalised):**
```
data/episodic_logs/
  2026/
    05/
      25/
        session_{run_id_1}.md
        session_{run_id_2}.md
    06/
      01/
        session_{run_id_3}.md
```

**Impact on implementation:**
- `packages/memory/src/clinical_ai_memory/episodic.py` — uses `pathlib.Path` for all I/O, `aiofiles` for async writes
- `data/episodic_logs/` — directory committed with `.gitkeep`, actual logs gitignored
- `k8s/deployments/api.yml` — mount a PersistentVolume at `/app/data/episodic_logs` in K8s
- No additional migration needed — purely filesystem

- [x] Finalised — Decision: `Filesystem Markdown`

---

## D-5 — Neo4j: Community Edition or AuraDB Free Tier

**Needed before:** BUILD-PLAYBOOK Task 0.2 (Docker Compose), Task 4.3 (Neo4j seed)

**Question:** Where does Neo4j run?

**Options:**

| Option | Setup | Cost | Limits | APOC Plugin |
|---|---|---|---|---|
| **Community Edition (Docker)** | Add to docker-compose.yml | Free | None (local) | Manual install — add to docker-compose PLUGINS env var |
| **AuraDB Free Tier** | Create account, get connection URI | Free | 1 instance, 200K nodes, 400K relationships, no APOC | Not available on free tier |
| **Enterprise Edition (Docker)** | Same as Community + licence | Paid | None | Full support |

**Recommendation: Community Edition (Docker)**

Rationale:
- APOC plugin is important — it provides graph algorithms and utility procedures used in multi-hop traversal queries. AuraDB free tier does not support APOC.
- No node/relationship limits — the drug knowledge graph could grow beyond AuraDB's 200K node limit once seeded with a comprehensive dataset
- Keeps all data local — consistent with the clinical data posture (D-2)
- `docker-compose.yml` already supports it: `image: neo4j:5`, `NEO4J_PLUGINS=["apoc"]`
- One command to start: `docker-compose up neo4j`

**Community vs Enterprise:** Community Edition lacks clustering and advanced security features, but neither matters for a single-instance portfolio project.

**AuraDB use case:** AuraDB free tier is appropriate if you want a persistent Neo4j instance accessible from multiple machines without running Docker locally (e.g., if you develop on different computers). If that's your situation, use AuraDB but avoid APOC-dependent queries.

**Impact on implementation:**
- `docker-compose.yml`: `image: neo4j:5`, ports `7474:7474` and `7687:7687`, `NEO4J_PLUGINS: '["apoc"]'`
- `.env.example`: `NEO4J_URI=bolt://localhost:7687`, `NEO4J_USER=neo4j`, `NEO4J_PASSWORD=password123`
- `scripts/seed_neo4j.py`: uses APOC procedures for batch import — works only with Community+APOC or Enterprise
- `k8s/deployments/`: add neo4j deployment with PersistentVolumeClaim for `/data`

- [x] Finalised — Decision: `Community Edition (Docker)`

---

## D-6 — Chainlit: Separate Service or Mounted Inside FastAPI

**Needed before:** BUILD-PLAYBOOK Task 6.1 (Chainlit app), Task 6.4 (Dockerfile + K8s)

**Question:** How is the Chainlit UI deployed relative to the FastAPI backend?

**Options:**

| Option | Architecture | Pros | Cons |
|---|---|---|---|
| **Separate service** | Chainlit runs on port 8001, FastAPI on port 8000. Chainlit calls FastAPI via HTTP. | Clean separation of concerns. Independent deployments. Standard microservice pattern. | Two processes to manage locally. Extra network hop. |
| **Mounted in FastAPI** | Chainlit app mounted at `/ui` via ASGI sub-mounting | Single process, single port | Chainlit is not designed for ASGI sub-mounting — unofficial/hacky. Would break Chainlit's websocket handling. |

**Recommendation: Separate service**

Rationale:
- Chainlit uses WebSockets for real-time step streaming — this breaks when mounted inside another ASGI app
- Separate service is the officially supported Chainlit deployment pattern
- Aligns with the Next.js upgrade path: both Chainlit and Next.js are separate frontend services pointing at the same FastAPI backend
- In K8s: two deployments (api + ui), one ingress routing `/api` → api service, `/` → ui service
- In local dev: two terminal windows or one `make dev` that runs both with `concurrently`

**Impact on implementation:**
- `Dockerfile` uses `--target api` or `--target ui` build stages to produce separate images
- `docker-compose.yml`: `api` service on port 8000, `ui` service on port 8001
- `Makefile` `make dev`: `concurrently "uvicorn api.main:app --reload" "chainlit run ui/app.py"`
- `k8s/deployments/api.yml` and `k8s/deployments/ui.yml` — separate manifests
- `k8s/ingress.yml`: routes `/api/*` → api ClusterIP, `/*` → ui ClusterIP
- Chainlit's API calls use `settings.API_BASE_URL` (e.g. `http://api:8000` in K8s, `http://localhost:8000` locally)

- [x] Finalised — Decision: `Separate service`

---

## D-7 — Next.js Upgrade Path: When to Activate

**Needed before:** BUILD-PLAYBOOK Task 6.3 (Next.js scaffold)

**Question:** Should the Next.js upgrade path be a full implementation or just a scaffold?

**Options:**

| Option | Effort | Portfolio signal |
|---|---|---|
| **Scaffold only** (Task 6.3 as written) | ~1 day | Shows architectural awareness, documents upgrade path clearly |
| **Full implementation after Phase 6** | +5–7 days | Full-stack signal: Python backend + React frontend — strong for roles that want full-stack AI engineers |
| **Replace Chainlit entirely with Next.js** | Replaces Phase 6 UI tasks | Stronger frontend signal, but loses Chainlit's agentic UI features (streaming steps, action buttons) |

**Recommendation: Scaffold in Phase 6, full implementation as optional Phase 7**

Rationale:
- Chainlit is the right tool for the agentic AI use case — streaming agent steps and action-button HITL are natively supported. A Next.js equivalent requires custom WebSocket handling.
- The scaffold (Phase 6.3) already demonstrates the architectural decision: "same FastAPI backend, no changes needed to switch UI frameworks"
- If time permits after Phase 6, building out the Next.js UI fully creates a stronger full-stack portfolio signal. This is optional — the Chainlit demo is already interview-ready.
- **Do NOT replace Chainlit** — Chainlit directly demonstrates JD 45 agentic UI patterns. Keep both.

**Decision matrix:**
- Portfolio review in < 4 weeks → scaffold only (save the time for polishing Chainlit demo)
- Portfolio review in > 4 weeks → build Next.js UI after Chainlit is working
- Targeting roles that emphasise full-stack → prioritise Next.js full implementation

**Impact on implementation:**
- Phase 6 Task 6.3 always runs (scaffold)
- Optional Phase 7 added to BUILD-PLAYBOOK if you choose full implementation: "Build full Next.js UI with all pages matching Chainlit handlers"
- No backend changes in either case

- [x] Finalised — Decision: `Full implementation`

---

## Additional Decisions (Emerged During Design)

These were not in PRD Section 16 but should be documented before their respective tasks.

---

## D-8 — Embedding Model for pgvector

**Needed before:** Task 0.4 (pgvector client), Task 2.8 (clinical knowledge RAG tool)

**Decision: `all-MiniLM-L6-v2` (sentence-transformers)**

Rationale:
- 384-dimensional vectors — small, fast, sufficient quality for clinical text retrieval
- Runs entirely locally — no data leaves the VPC (critical for clinical context)
- Already in `pyproject.toml` as `sentence-transformers = ">=3.3.0"`
- Consistent model used at both index time and query time — no embedding mismatch

**Alternative considered:** OpenAI `text-embedding-3-small` — rejected because it sends data to OpenAI servers, which violates the PHI-safe architecture posture.

**Impact:** `packages/shared/src/clinical_ai_shared/db/pgvector.py` hardcodes this model. Vector dimension in pgvector schema is `vector(384)`.

- [x] Finalised — Decision: all-MiniLM-L6-v2 (already reflected in implementation plan)

---

## D-9 — BM25 Index Storage for Dual-Channel Search

**Needed before:** Task 3.3 (Index Layer)

**Decision: In-memory BM25 index, rebuilt on startup**

Rationale:
- `rank_bm25` library builds index in-memory from a list of tokenised documents
- Long-term memory entries are loaded from pgvector at startup and indexed
- Index is rebuilt on startup and updated incrementally as new entries are added
- For the volume of long-term entries in this portfolio project (hundreds, not millions), in-memory is fast enough
- No additional infrastructure (no Elasticsearch, no separate search service)

**Alternative considered:** PostgreSQL full-text search (`tsvector`) — viable but adds complexity to the pgvector schema. Rejected in favour of simplicity.

**Impact:** `packages/memory/src/clinical_ai_memory/index.py` maintains `self._bm25_index` as an instance variable. Startup latency: < 1 second for up to 10,000 entries.

- [x] Finalised — Decision: in-memory rank_bm25

---

## D-10 — API Authentication Strategy

**Needed before:** Task 1.7 (ClinFlow API + auth middleware)

**Decision: Static API key via `X-API-Key` header, configured in environment**

Rationale:
- PRD explicitly scopes out user accounts and RBAC (Section 13 Out of Scope)
- A static API key is sufficient for a portfolio project and demo environment
- Keys configured as `API_KEYS=key1,key2` in settings — supports multiple keys (e.g. UI service key vs external caller key)
- `/health` and `/ready` are unauthenticated (required for K8s probes)

**Alternative considered:** JWT with OAuth2 — rejected as out of scope for v1 (PRD Section 13).

**Impact:** `packages/shared/src/clinical_ai_shared/auth/middleware.py` reads `X-API-Key` and validates against `settings.API_KEYS`. Chainlit UI sends key via `Authorization` header on every FastAPI call.

- [x] Finalised — Decision: static API key

---

## How to Propagate Decisions to Other Files

When you finalise a decision, update these files accordingly:

| Decision | Files to update |
|---|---|
| D-1 (local model) | `.env.example` — `PHI_MODEL=` value; `docker-compose.yml` — Ollama service |
| D-2 (LangFuse) | `docker-compose.yml` — add or remove LangFuse service; `.env.example` — `LANGFUSE_HOST=` |
| D-3 (golden sets) | `scripts/generate_golden_sets.py` — implementation approach |
| D-4 (episodic storage) | `packages/memory/src/clinical_ai_memory/episodic.py` — implementation |
| D-5 (Neo4j) | `docker-compose.yml` — Neo4j service config; `.env.example` — connection string |
| D-6 (Chainlit deploy) | `docker-compose.yml` — ports; `Makefile` — `make dev` command; `Dockerfile` — build targets |
| D-7 (Next.js timing) | `BUILD-PLAYBOOK.md` — add or skip Phase 7 tasks |

---

*When all decisions are finalised, delete the "Pending" rows from the status table at the top and replace with "✅ Finalised" + date.*
*Reference this file at the start of every Phase 0 task — the prompts in BUILD-PLAYBOOK.md assume these decisions are made.*
