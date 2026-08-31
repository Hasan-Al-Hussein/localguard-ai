# Security and privacy

LocalGuard AI is a local engineering demonstration, not a production compliance or legal-advice
system. Its security design focuses on the risks created by document uploads, small language
models, asynchronous work, and human-approved state changes. It does not assume that a model can
enforce policy.

## Protected assets and likely attackers

The protected assets are uploaded document bytes, extracted text and embeddings, account and
session material, evidence/citation integrity, proposal and task state, and the audit chain. The
design considers:

- an unauthenticated browser or MCP client on the same machine;
- a signed-in viewer attempting reviewer/admin operations;
- a malicious or malformed uploaded document;
- prompt injection embedded in otherwise useful evidence;
- fabricated model fields, citations, or tool calls;
- duplicate/replayed requests and workers;
- transient Redis, broker, filesystem, model, or process failures.

A user with administrator access to the host or Docker daemon is outside the isolation boundary:
that user can inspect containers, process memory, volumes, and the generated `.env` file.

## Identity, sessions, and browser requests

- Passwords are hashed with Argon2id. Bootstrap writes random local passwords to ignored `.env`
  without printing them.
- The ordinary API, worker, and MCP containers receive blank bootstrap-password and bootstrap-token
  values. Only the short-lived `admin-cli` service receives those secrets when it seeds or rotates
  local principals. PostgreSQL receives only its own database variables.
- Browser sessions are random opaque values. PostgreSQL stores only a SHA-256 token hash, the
  actor, expiry, last-seen time, and revocation state.
- The session cookie is HttpOnly and SameSite. JavaScript holds only a short-lived CSRF token in
  memory; state-changing requests must match the header, browser cookie, and server-bound session
  hash.
- Login failures are throttled in PostgreSQL. The update is atomic so concurrent failures cannot
  reset or undercount the window.
- FastAPI accepts exact configured hosts and origins. The Next.js proxy forwards only approved
  methods, paths, and headers, limits request bodies before buffering/forwarding, and converts
  upstream failures to sanitized responses.
- The UI hides actions a role cannot use, but every protected route repeats authorization on the
  server. Viewer, reviewer, and admin are stored authorities, not model or request-body fields.
- Reseeding an existing principal replaces its password hash and revokes that principal's active
  browser sessions. `scripts/rotate-demo-admin.ps1` rotates the ignored `.env` value and reseeds
  without printing it.

`SESSION_COOKIE_SECURE=false` is appropriate only for loopback HTTP development. Production-mode
configuration fails closed unless secure cookies are enabled; this repository does not claim a
TLS deployment.

## Upload and parser boundary

Uploaded bytes are untrusted even after authentication.

- Accepted formats are PDF, DOCX, and TXT only. The filename extension, declared media type, and
  detected signature must agree.
- The maximum upload is 10 MB. PDF pages, DOCX entries/paragraphs/expanded size/compression ratio,
  TXT lines, and total extracted characters have independent limits.
- Original filenames are display metadata. Storage uses generated keys under a resolved private
  root, an atomic temporary write, and an explicit path-containment check.
- The application never shells out to a document, evaluates macros, executes attachments, or
  interprets document text as code. DOCX ZIP traversal and expansion are bounded before parsing.
- PDF pages, DOCX structural spans, and original TXT line indices are retained as immutable source
  anchors. Deletion uses a durable cleanup ledger so a transient filesystem error is retried and
  visible rather than silently orphaned.

The parsers are still complex third-party code. A production service would add stronger sandboxing,
malware scanning, parser-process isolation, and a maintained file quarantine policy.

## Model, retrieval, and prompt injection

Document text is wrapped as delimited untrusted evidence. It is never used to establish the user,
role, available tool set, approval decision, or execution target.

- Request classification is based on the authenticated user request, not instructions found in a
  retrieved document.
- Retrieval uses both rank fusion and calibrated absolute relevance checks. An unrelated nearest
  neighbor is not sufficient merely because it ranked first.
- Structured model output uses Pydantic models with extra fields forbidden. One repair attempt is
  allowed; subsequent invalid output fails safely.
- In `qa-fact-binding-v1`, application code proves marker-local request support and scopes opaque
  bindings; the model confirms those bindings or abstains, and application code derives the answer,
  normalized claims, and exact citation spans.
- In `evidence_derived_binding_confirmation_v2`, application code scopes the complete supported
  structured binding set; the model may confirm it or abstain, and application code derives every
  finding field. In `evidence_derived_binding_selection_v2`, the model may select one scoped action
  binding or abstain, and application code derives claim and proposal fields.
- The model can return only retrieved opaque chunk IDs. Application code rejects unknown IDs and
  resolves titles, revisions, anchors, quotes, and ranges from PostgreSQL.
- Missing evidence produces an explicit insufficient-evidence result. The system does not ask a
  second model to judge itself.
- Synthetic attacks cover direct system-message impersonation, forged tool JSON, secret/data
  exfiltration requests, fake approvals, and obfuscated bypass text.

These controls reduce impact; they do not claim universal prompt-injection detection. Safety comes
from keeping privileges outside the prompt.

Standalone risk extraction and standalone party/responsible-party extraction are unsupported.
Treating either as available would bypass the delivered schema 1.2.0 evidence contracts; both require
separate schemas, evidence constraints, and evaluation coverage before implementation.

## Human approval and task integrity

An action request creates a proposal, never a task. The LangGraph workflow persists state and
interrupts at the approval boundary.

- Only an active reviewer or admin can read the approval queue or submit a decision.
- A decision is bound to proposal ID, immutable version, canonical payload hash, evidence snapshot
  hash, expiry, workflow thread, and decision actor.
- Editing invalidates the old proposal and creates a new pending version. The old version cannot be
  approved afterward.
- Execution reloads and row-locks the proposal and decision, rechecks the actor’s current role and
  all bindings, and uses database uniqueness to create at most one task.
- Reject and edit paths cannot create a task. Document text, model output, MCP input, and replayed
  Celery messages cannot substitute for a stored human decision.
- MCP-created proposals carry an explicit direct-workflow provenance marker instead of pretending
  to have a LangGraph checkpoint. Their dedicated resume path accepts only that provenance, then
  uses the same version, canonical payload hash, evidence snapshot, current-reviewer check,
  exactly-once task constraint, and audit service as a graph-created proposal.

## Asynchronous reliability and audit

Accepted uploads, questions, workflows, and approval resumes write their domain state, audit row,
and durable outbox row in one PostgreSQL transaction. Redis/Celery dispatch happens afterward. A
background reconciler claims pending or stale dispatched rows and sends them with stable task IDs.
A successful send creates a dispatched lease rather than final delivery proof. The worker ACKs the
outbox row only after PostgreSQL shows that delivery's domain transition is complete (for example,
a workflow start reaching its approval interrupt); an unacknowledged lease expires and is
reconciled. Dispatch failures are released with bounded backoff.

Workers accept opaque UUIDs, reload authoritative state, lock before transitions, and are
idempotent. A transient provider failure releases ingestion, question, or workflow state for the
next Celery retry and does not make the outbox row terminal. Only the final Celery attempt records a
terminal failure. PostgreSQL remains authoritative if Redis is flushed. Model calls across API and
worker processes share a token-bound Redis lease whose TTL must exceed the HTTP timeout plus a
safety margin. A heartbeat renews only the current token during multi-segment embedding; losing
ownership cancels the model operation and fails closed instead of returning output under an expired
lease.

Audit events record actor, action, resource, outcome, timestamp, correlation reference, optional
causation reference, and workflow thread. API-side events may use an outbox or decision UUID as
causation. Asynchronous worker events instead create a new `worker-...` correlation and currently
store the originating request correlation in `causation_id`; that field is therefore not always an
audit-event UUID. API responses do not expose password, secret, token, or document-content keys
from audit detail. Logs record exception types and correlation data, not uploaded text or secrets.

## MCP boundary

FastMCP listens inside its container but is host-published only on loopback; its transport also
enforces the configured loopback Host and exact Origin policy. It authenticates a bearer credential
by hash. Middleware resolves the trusted user and role; tools do not accept an actor or role
parameter. The allowlist is limited to:

- `search_documents`
- `get_document_section`
- `propose_workflow_task`
- `list_pending_approvals`
- `get_audit_event`

Each tool uses strict input/output models, calls the same repositories and RBAC policy as REST,
returns structured errors, and records authenticated success, denial, rejection, or not-found
outcomes. Each tool also has an outer unexpected-failure boundary that attempts a sanitized failed
audit before returning a tool-specific error; if PostgreSQL itself is unavailable, preserving the
masked tool error takes precedence and that failure audit cannot be guaranteed. Section reads are
offset-based and limited to at most 8,000 characters, while list/search inputs and outputs have
independent count and length bounds. No MCP tool directly creates an approved workflow task.

The bootstrap MCP bearer is stored only as a hash in PostgreSQL and has a configurable 30-day
default expiry (`MCP_BOOTSTRAP_TOKEN_TTL_DAYS`, allowed range 1–365). Seeding synchronizes the
ignored `.env` bearer, refreshes its finite expiry, and revokes prior active bootstrap bearers.
`scripts/rotate-mcp-token.ps1` performs the same rotation and rollback-safe synchronization without
printing the new value. A bearer rejected before a database principal can be resolved cannot
produce an actor-attributed tool audit.

## Schema and retention boundaries

Alembic head `20260823_0004` retains exact structured-finding marker/field/provenance evidence.
Its downgrade fails before DDL while any row contains v2 evidence metadata, requiring an operator
to export and explicitly remove those findings before accepting that loss. Revision
`20260823_0003` reconciles databases that were stamped by an earlier Phase 2 schema
while leaving the finalized `c57f8be7e15c` shape intact. During the c57 upgrade, active legacy
documents with the same creator and source hash are ranked by creation time and UUID. The first is
kept active; later rows are marked deleted and receive a
`migration.document_duplicate_quarantined` audit record containing the canonical document ID and
prior state. Revisions and private source files remain referenced so c57 downgrade can restore the
rows and mark those audits `reverted`.

Deletion can intentionally leave immutable citation snapshots whose source chunk is gone. A c57
downgrade cannot represent that state because Phase 1 requires every citation to reference a chunk,
so it fails closed while any `citations.chunk_id` is null. The operator must first export the
snapshots with `export-orphan-citations`, preserve the private export, and then use the exact-confirm
`purge-orphan-citations` command before retrying the downgrade.

LangGraph's checkpoint tables and migration metadata are owned by the pinned checkpoint library,
not Alembic. They survive application-schema downgrades by design. Removing user-thread history is
a separate destructive retention decision: stop workflow producers, preserve a PostgreSQL backup
if the history is needed, and invoke `purge-checkpoints` with its exact confirmation. That command
deletes checkpoint writes, blobs, and checkpoints while retaining the checkpoint schema and its
migration metadata.

## Local privacy and supply chain

- No paid or cloud model API exists in the runtime configuration. Generation and embeddings use
  the pinned local Ollama container.
- PostgreSQL, Redis, and Ollama use the internal backend network and have no host-published ports.
  The API and MCP services join both backend and edge; the web service joins edge only and cannot
  resolve the database service. Published web, API, and MCP ports bind to `127.0.0.1`.
- Model manifests and container images have recorded SHA-256 digests. Python and npm dependencies
  are exact-version locked; CI installs from those locks.
- The repository contains only original synthetic documents. Their source and generated-file
  hashes are validated, and privacy patterns reject email, phone, government ID, home-path,
  university-identifier, payment-card, and private-key material.
- `.env`, uploads, database/model volumes, browser traces, and transient verification output are
  ignored. Project scripts never delete unrelated Docker data.

Model bootstrap is the one intentional outbound application step. Its Compose overlay is separate,
and bootstrap verifies the downloaded local manifest hashes against `docs/runtime-lock.json`.
The edge network must remain non-internal for Docker Desktop loopback publishing, however, so
outbound traffic from edge-connected API, MCP, and web containers is not technically blocked by a
Compose firewall. The application has no cloud-provider fallback, but host firewall or a stricter
deployment network is required for enforced egress denial.

## Verification expectations

Security-sensitive changes require focused unit tests and a real-boundary regression where the
failure depends on PostgreSQL, Redis, the browser, or transport behavior. The standard gates cover:

- session expiry/revocation, CSRF, role denial, login-throttle races, and safe errors;
- path traversal, MIME mismatch, archive bombs, page/size limits, and TXT line fidelity;
- irrelevant-query abstention, citation allowlisting, malformed structured output, and injection;
- broker outage recovery, duplicate/concurrent idempotency, stale claims, and cleanup failure;
- proposal edit/reject/approve bindings, no preapproval task, replay, and exactly-one execution;
- MCP schema, authentication, RBAC, tool audit, origin/host checks, and unapproved-action denial;
- dependency lint/type checks, migration drift/reversal, and real-stack browser journeys.

Observed commands and results are recorded in `docs/verification-log.md`; evaluation failures are
retained in generated reports rather than edited away.

## Residual limitations

- Loopback HTTP has no TLS. Do not expose these ports to another host.
- Edge-container egress is not firewall-enforced by this Compose topology.
- Host/Docker administrators can access local data and credentials.
- This is a single-organization demonstration, not a hardened multi-tenant authorization model.
- There is no OCR, malware engine, content-disarm pipeline, hardware-backed secret store, signed
  release, SBOM attestation, disaster-recovery service, or external security monitoring.
- Exact dependency pins reduce drift but do not eliminate upstream vulnerabilities; updates need
  regular review and full regression testing.
- Local model answers can still be incomplete or wrong. Citations and approval gates make errors
  inspectable; they do not make the system a legal or compliance authority.

For a production deployment, add TLS, external secret management, enforced network egress controls,
central identity, tenant isolation, backup/restore drills, malware scanning, an SBOM/signing
pipeline, monitoring, and an independent penetration test before processing real documents.
