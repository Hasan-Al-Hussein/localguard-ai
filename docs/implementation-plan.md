# LocalGuard AI implementation plan (historical)

This was the gated build plan used for the repository. It is kept as engineering context; observed
results belong in `docs/verification-log.md`, not in this plan.

The current release contract supersedes the Phase 2 model-selection wording below. Ordinary QA uses
`qa-fact-binding-v1`: the model confirms application-scoped opaque marker bindings or abstains, and
the application derives answer, claim, and citation values. Evaluator schema `1.2.0` uses
`evidence_derived_binding_confirmation_v2` for structured output: the application
scopes the full supported binding set, the model confirms or abstains, and the application derives
finding fields. Actions use `evidence_derived_binding_selection_v2`: the model selects one binding
or abstains, and the application derives claim/proposal fields. Standalone risk and standalone
party/responsible-party extraction remain unsupported roadmap capabilities.

## Outcome and non-negotiable boundaries

Deliver a recruiter-readable local application whose real path is upload → source-preserving parse
→ local embedding → pgvector retrieval → local structured answer → exact clickable citation, with
an explicit LangGraph proposal/approval workflow and reproducible evaluation.

The build must remain CPU-only, free of paid/cloud runtime dependencies, below approximately 10 GB
active RAM and 15 GB attributable disk, use no model above 3B parameters, serialize model calls,
and contain only original synthetic documents. Identity, RBAC, citations, tool availability,
approval, and execution must remain application-controlled.

## Phase 0: foundation and proof contracts

- Inspect Windows, Docker Desktop, memory, storage, Node, Python, Git, and Ollama availability.
- Initialize a local-only Git repository; do not create a remote.
- Record architecture decisions and a verification matrix before production implementation.
- Build original synthetic PDF/DOCX/TXT sources and injection variants with stable markers and a
  hash-locked 25-case gold dataset.
- Pin Python/npm dependencies, image digests, resource limits, and Windows PowerShell entry points.
- Select the real local model only after a bounded CPU schema/grounding comparison.

Gate: dependency resolution, Compose validation, fixture structural/visual review, dataset negative
self-tests, migration reversal, and model manifest/resource evidence.

## Phase 1: smallest complete vertical slice

- Opaque database sessions, Argon2id, CSRF, roles, throttled login, trusted host/origin policy.
- Bounded PDF/DOCX/TXT upload, private atomic storage, immutable revisions and true source anchors.
- Celery ingestion with local 384-dimensional embeddings and exact pgvector/FTS hybrid retrieval.
- Structured local answer with server-resolved citation snapshots and explicit abstention.
- Documents, viewer, and ask UI backed by the real API contract.

Gate: upload → ready → question → answer/abstain → immutable citation in real PostgreSQL/pgvector,
plus focused security and browser checks.

## Phase 2: controlled agent workflow

- Explicit LangGraph classify, retrieve, sufficiency, generation, validation, extraction, proposal,
  interrupt, resume, and execute nodes with PostgreSQL checkpoints.
- Evidence-constrained extraction of unambiguous modal obligations and deadlines plus the supported
  immediate-when-safe required-action shape, each with actor/action/deadline fields.
- Historical design target: model selection of finding type, action, and deadline from runtime
  exact-marker-derived candidate enums, with a model-authored, server-validated actor. This was
  replaced by the schema 1.2.0 evidence-derived contracts described above.
- Version/hash/evidence-bound proposals; reviewer/admin edit, reject, approve, and exactly-one task.
- Five strict FastMCP tools sharing REST policy and audit repositories.
- Durable outbox, idempotent workers, broker reconciliation, cleanup ledger, and causation chain.
- Complete approvals, tasks, findings, audit, overview, and evaluation UI/API contracts.

Gate: no preapproval mutation; approve/edit/reject/expire/replay tests; current-role recheck; MCP
authentication/RBAC/schema/audit; broker/filesystem failure recovery; schema drift after checkpoint
setup.

## Phase 3: reliability and evaluation

- Deterministic provider for CI that exercises the real graph and persistence without replaying gold
  answers or inspecting case IDs.
- Exact retrieval, citation, field, extraction, unsupported-claim, tool, approval, injection,
  forbidden-outcome, abstention, and latency metrics.
- Sequential 25-case runs with raw per-case output, SHA-linked summary, generated Markdown, and
  nonzero exit on failed gates.
- Unit, real-PostgreSQL/Redis, MCP transport, worker, migration, UI-contract, and unmocked production
  browser journeys.
- GitHub Actions with pinned actions and no model download or secret API key.

Gate: every case completes; every declared forbidden outcome is a hard failure; deterministic safety
gates pass; real-model failures remain visible; CI-parity commands pass locally.

## Phase 4: portfolio and operational quality

- Responsive accessible UI with loading, empty, error, keyboard, mobile, and exact evidence states.
- Real screenshots, architecture/security/evaluation/demo/troubleshooting documentation, and an
  honest career pack.
- Define schemas, evidence constraints, and evaluation cases before adding standalone risk or
  responsible-party extraction; those capabilities are outside the delivered extraction slice.
- Measured idle/query memory, indexing/retrieval/generation latency, and attributable disk.
- Secret/private-data scan, dependency and container checks, fresh-bootstrap proof, and bounded
  local cleanup.

Gate: all 15 definition-of-done items have linked evidence, the standard real demo uses no mocks,
the repository contains no private data or secret, and a new Windows developer can reproduce it
from the README.

## Stop/rollback rules

- Stop a phase when its prior gate fails; preserve the failure artifact and correct the cause.
- A structured-output repair is allowed once. Repeated invalid output fails closed.
- A model candidate that misses schema/citation/safety or resource limits is rejected and removed.
- A broker/filesystem outage leaves durable pending state; it never converts an accepted request
  into an untracked operation.
- An ambiguous or stale approval never executes. Any missing binding or audit invariant disables the
  privileged path.
- Project scripts stop services but do not delete named volumes or unrelated Docker data.
- No cloud deployment, remote repository, or production claim is made without separate explicit
  work and evidence.
