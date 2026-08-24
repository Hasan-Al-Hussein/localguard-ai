# Career pack

This wording describes the repository as it exists. It does not claim a cloud deployment, paid API
integration, remote GitHub Actions run, or production use. It does claim the retained, local,
dependency-locked 25-case Ollama result documented below.

## Three CV bullets

- Built a CPU-only document intelligence application with FastAPI, Next.js, Ollama, LangGraph,
  PostgreSQL/pgvector, Redis, and Celery that ingests PDF, DOCX, and TXT files, performs hybrid
  retrieval, and returns server-resolved citations to immutable source ranges.
- Implemented version-bound human approval for agent-proposed tasks, with opaque sessions, RBAC,
  CSRF protection, strict MCP tools, PostgreSQL checkpoints, durable outbox delivery, idempotent
  workers, and a correlation-linked application audit trail.
- Created a schema 1.2.0, hash-verified 25-case evaluation suite covering grounded answers,
  insufficient evidence, prompt injection, and approval workflows, with raw failure retention and
  explicit separation between deterministic orchestration evidence and local-model quality.

## LinkedIn project summary

I built LocalGuard AI as a local, CPU-only document intelligence and workflow review project. It
accepts synthetic PDF, DOCX, and TXT documents, preserves real source anchors, combines pgvector
and PostgreSQL full-text retrieval, and produces structured answers with citations that the server
resolves to immutable revisions.

The agent workflow is explicit in LangGraph. A requested action becomes an inert proposal, pauses
for an authenticated reviewer, and can create one local task only after version, payload, evidence,
expiry, and role checks pass. Five FastMCP tools share the same authorization and audit policy.

I also built a 25-case evaluator with grounded, insufficient-evidence, prompt-injection, and
approval cases. The final dataset v1.0.2/schema 1.2.0 pinned-Ollama run completed 25/25 and passed
safety, quality, and overall gates; the older failed legacy run remains unedited. Deterministic
provider results remain separately labeled and are not presented as model accuracy.

Stack: Python, FastAPI, Pydantic, SQLAlchemy, Alembic, LangGraph, FastMCP, Ollama,
PostgreSQL/pgvector, Redis, Celery, Next.js, React, TypeScript, Docker Compose, Pytest, Vitest, and
Playwright.

## GitHub repository description

CPU-only local document intelligence with hybrid RAG, source-bound citations, LangGraph approval
workflows, audited MCP tools, and a reproducible 25-case evaluation suite.

## One-minute interview explanation

LocalGuard AI is a portfolio project for a common operational problem: policies contain deadlines
and obligations, but a useful answer needs evidence and an action needs control.

The application runs locally on a 16 GB Windows laptop with Docker Compose. A Next.js interface
talks to FastAPI through a same-origin proxy. Documents are parsed into immutable page, paragraph,
or line anchors, embedded with a small local model, and searched with both pgvector and PostgreSQL
full-text search. The model can return only retrieved chunk IDs; the server resolves the actual
citation metadata and rejects unknown evidence.

For actions, LangGraph creates a proposal and interrupts. A reviewer must approve an exact version
and its payload and evidence hashes before Celery can create one task. PostgreSQL remains the source
of truth, including the outbox and audit chain.

I built local unit, integration, browser, and evaluation gates around the design. The final local
snapshot is 383 Python unit tests, 45 disposable-database integration tests plus one expected
real-model skip, 46 frontend tests, a passing live portfolio journey, and a 25/25 pinned-Ollama
quality run. I keep real Ollama quality results separate from deterministic test results.

## Five-minute technical explanation

### 1. Product boundary

LocalGuard handles synthetic operational policies, procedures, and vendor documents. Users can
upload PDF, DOCX, or TXT files, ask questions, inspect citations, request structured findings, and
propose workflow tasks. It is a local engineering demonstration, not a legal-advice system.

The delivered extraction slice supports bounded evidence-derived modal rules. Standalone risk
extraction and standalone party/responsible-party extraction are unsupported roadmap capabilities.

The main design rule is that the model drafts content while application code owns identity,
permissions, evidence, approval, and state changes. That rule shaped the API, graph, tools, and
database schema.

### 2. Ingestion and retrieval

FastAPI checks the extension, declared media type, detected content, 10 MB byte limit, and
format-specific parser limits. The original filename is display metadata. The stored filename is a
generated private storage key under a contained upload root.

The Celery worker parses true PDF pages, DOCX structure, or TXT line ranges. Chunks do not cross a
source anchor. It generates 384-dimensional embeddings locally and stores them with the revision in
PostgreSQL. An accepted upload, audit event, and outbox event commit together, so a Redis outage
does not lose the work request.

Retrieval performs exact cosine search in pgvector and PostgreSQL full-text search, then uses
reciprocal-rank fusion. Absolute vector and text thresholds sit beside rank so an unrelated nearest
neighbor is not automatically sufficient evidence.

### 3. Grounded output

Retrieved text is delimited as untrusted evidence. Intent classification uses the authenticated
user request, not document instructions. The provider returns a strict Pydantic shape and opaque
chunk IDs. One bounded schema repair is allowed; another invalid result fails closed.

Under `evidence_derived_binding_confirmation_v2`, the application scopes the complete supported
structured-output binding set, the model confirms it or abstains, and the application derives all
finding fields. Under `evidence_derived_binding_selection_v2`, the model selects one scoped action
binding or abstains, and the application derives the claim and proposal fields.

The server checks every citation against the retrieved allowlist and resolves its document,
immutable revision, page or structural anchor, quote, and offsets from PostgreSQL. The browser opens
that stored identity, so reprocessing a document cannot move an older citation to a new revision.

### 4. Agent workflow and approval

LangGraph makes the sequence visible: classify, retrieve, assess evidence, generate, validate,
propose, interrupt, resume, and execute. Read-only answers can complete after validation. Action
requests create a pending proposal and stop.

Approval is a reviewer or admin API decision. It binds the proposal ID, immutable version,
canonical payload hash, evidence snapshot hash, expiry, graph thread, and decision actor. Execution
reloads and row-locks the authoritative records, rechecks the actor's current role and all bindings,
then relies on database uniqueness to create at most one task. Edit creates a new pending version;
reject, expiry, and replay cannot create an extra task.

### 5. MCP and asynchronous reliability

FastMCP exposes five tools: document search, section lookup, task proposal, pending approvals, and
audit-event lookup. Middleware resolves a hashed bearer token to a principal. Actor and role are
not tool inputs, and no tool can directly create an approved task.

PostgreSQL is authoritative for domain state, the durable outbox, cleanup ledger, audit events, and
LangGraph checkpoints. Redis is used for Celery and a shared model lease. Workers receive opaque
IDs, reload state, lock transitions, and are idempotent. The API reconciles undispatched outbox rows
with stable task IDs and bounded backoff.

### 6. Evaluation and proof

The original dataset has 10 grounded, 5 insufficient-evidence, 5 prompt-injection, and 5
action/approval cases. Stable markers and raw-byte hashes make the gold corpus reproducible. The
runner invokes real retrieval, graph, approval, and persistence paths, then computes recall at K,
citation precision, extraction scores, unsupported-claim rate, exact tools and proposals, approval
compliance, forbidden outcomes, and stage latency without a learned judge.

Evaluator schema `1.2.0` is paired with the final audited dataset v1.0.2 corpus and the two
evidence-derived mode identifiers above. Run
`20260823T234625509074Z-ollama-914d80632516` completed 25/25 with safety, quality, and overall PASS:
retrieval recall@5 0.9667, citation precision 1.0000, extraction F1 0.8889, exact tools and proposals
1.0000, 5/5 abstentions, 27/27 injection controls, and 97/97 forbidden controls. The older failed
schema 1.1.0 run remains metadata-only historical evidence.

Earlier deterministic and repository-wide test results remain in the verification ledger as
historical evidence. They are not presented as final schema 1.2.0 counts or as Qwen quality.

### 7. Resource and scope decisions

The selected model is Qwen3 1.7B Q4. A historical bounded model-selection gate recorded a
4.91-second warm median and a 2.008 GiB Ollama peak; those measurements are not final full-stack or
schema 1.2.0 evaluation results. Generation and embedding share one Redis lease; Ollama and Celery
both use concurrency one. Exact vector search fits the small portfolio corpus and avoids
approximate-index tuning.

The normal path has no OCR, CUDA, cloud API, Kubernetes, or external telemetry. Final measured
values are 576.06 MiB unloaded idle memory, 3,976.33 MiB successful warm-query peak, 6.73 seconds to
index all 13 fixtures, and approximately 12.94 GB retained attributable disk.

## Skills supported by repository evidence

These are appropriate additions to a CV skills section after completing and being able to explain
the project:

### Languages and application development

- Python 3.12
- TypeScript 5.9
- SQL
- PowerShell 7
- FastAPI
- Pydantic 2
- SQLAlchemy 2
- Alembic
- Next.js 16 App Router
- React 19
- Tailwind CSS 4
- React Hook Form
- TanStack Query
- TanStack Table
- Zod

### Applied AI and agents

- Retrieval-augmented generation
- Hybrid vector and full-text retrieval
- pgvector
- Reciprocal-rank fusion
- Structured model outputs
- Citation grounding
- Local LLM integration with Ollama
- LangGraph state machines and PostgreSQL checkpoints
- Human-in-the-loop approval workflows
- Model-provider interfaces
- AI evaluation without a learned judge
- Prompt-injection guardrails
- FastMCP tool design

### Data, reliability, and security

- PostgreSQL 16
- Redis
- Celery
- Durable outbox pattern
- Idempotent background jobs
- Optimistic and pessimistic concurrency controls
- Role-based access control
- Opaque session authentication
- CSRF protection
- Argon2id password hashing
- Immutable audit trails and correlation IDs
- Secure document-upload validation

### Testing and delivery

- Pytest and pytest-asyncio
- Vitest and Testing Library
- Playwright
- Ruff
- mypy strict mode
- OpenAPI contract generation and drift checks
- Docker Compose
- GitHub Actions workflow design
- Deterministic test providers
- Synthetic evaluation datasets

Use the exact technology name only when you can explain where it appears, why it was selected, and
how it was tested. Do not convert this list into claims of production scale, cloud deployment,
Kubernetes, fine-tuning, computer vision, or MLOps platforms that are not in the repository.

## Suggested portfolio screenshots

Seven actual-run screenshots are committed under `docs/screenshots/`. A guarded Playwright journey
captured and atomically published them only after validating the live demo and final evaluation:

| Image | What should be visible | Claim it supports |
|---|---|---|
| Overview | Local service state, document count, pending approvals, tasks, and current evaluation summary | Product breadth and operational state |
| Document viewer | Synthetic PDF, immutable revision identity, exact highlighted one-hour passage | Source-preserving ingestion and citation resolution |
| Ask LocalGuard | Real Ollama answer, evidence state, source chip, and open citation | Local grounded answering |
| Approval detail | Proposal version, evidence binding, reviewer controls, and zero matching tasks before approval | Human approval boundary |
| Approved task | One executed proposal and its single source-bound task | Exactly-once action execution |
| Audit thread | Request, model/tool, proposal, decision, outbox, resume, and task events sharing correlation or causation | Auditability and asynchronous trace |
| Evaluation detail | Provider, schema/dataset versions, evidence mode IDs, all cases, provenance, and gate outcomes | Reproducible final schema 1.2.0 evaluation without edited failures |

Use full application frames at readable browser scale. Keep the local URL and synthetic labels
visible where useful. Do not composite screens, hide failed cases, replace the provider name, or
crop away evidence that changes the meaning.

## Claims to avoid

- "Deployed to production" or "production-grade" without a real deployment and operations record.
- "Cloud-native," "Kubernetes," or a named cloud provider.
- "Prompt-injection proof" or "hallucination free."
- "Real-time" unless a measured requirement and latency support it.
- "100% accurate" based on safety controls or pooled citation precision.
- "CI passed on GitHub" until an actual remote workflow run exists.
- Performance claims for other hardware or workloads; the recorded figures apply only to the
  documented 16 GB CPU-only laptop and exact locked run.
- “Perfect extraction” or “100% accurate”; the final extraction F1 is 0.8889 and the evaluation is
  a bounded synthetic corpus, not a production guarantee.
