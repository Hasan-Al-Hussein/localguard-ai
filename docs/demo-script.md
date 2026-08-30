# Extended LocalGuard AI live-demo script

This walkthrough uses only the committed synthetic fixtures and the real local Ollama providers.
It is designed for a five-minute live interview walkthrough. For the edited presentation cut, use
the [110-second product tour](../demo-video/output/product-demo.mp4), its
[captions](../demo-video/output/product-demo.srt), and the concise
[production script](../demo-video/script.md). Nothing in this live path is mocked.

## Before the recording

From the repository root:

```powershell
pwsh -File scripts/bootstrap.ps1
pwsh -File scripts/demo.ps1 -Reset
```

Bootstrap generates the three demo passwords in the ignored `.env`. Keep that file off screen.
Use `BOOTSTRAP_VIEWER_PASSWORD` with `demo-viewer` and `BOOTSTRAP_REVIEWER_PASSWORD` with
`demo-reviewer`. The script waits for all services and refuses deterministic providers.

Bootstrap also synchronizes a hashed MCP bearer with a configurable 30-day default expiry. Do not
show or paste it during a browser demo. If recording hygiene requires fresh credentials afterward,
use `scripts/rotate-demo-admin.ps1` and `scripts/rotate-mcp-token.ps1`; neither prints the new value.

Open `http://localhost:3000`. Keep `docs/architecture.md`, `evals/results/latest.md`, and
`artifacts/verification/demo.json` available as supporting evidence, but do not present an old run
as if it happened during the recording.

## 0:00–0:35 — frame the problem

Say:

> Teams receive policies and procedures full of obligations and deadlines. LocalGuard keeps the
> documents and models on this laptop, answers with source-level evidence, and turns an action
> request into an inert proposal that a human must approve.

Show the overview briefly. Point out that the status indicator is connected to the local FastAPI
service and that this is an engineering demonstration, not legal advice.

## 0:35–1:25 — upload and index a real fixture

Sign in as `demo-reviewer`, open **Documents**, and upload:

`fixtures/documents/clean/lg-pol-001-vendor-access.pdf`

Mention the three boundaries while the status progresses from queued to ready:

- FastAPI verifies format and size; the original filename never becomes a storage path.
- Celery parses true PDF pages and generates 384-dimensional embeddings locally.
- PostgreSQL/pgvector is authoritative; Redis is only the broker and model lease.

Open the document. Show the page/section structure and extracted text. The synthetic notice should
be visibly recognizable.

## 1:25–2:15 — ask a cited question

Open **Ask LocalGuard** and ask:

> How long does the Service Desk have to disable a vendor account after it receives an offboarding
> notice?

Expected substance: **within one hour after receiving the notice**. The wording may vary because
this is the real local model. Ask searches the authenticated user's ready indexed vault; this
screen has no per-document selector.

Click the citation. Show that it opens the immutable source revision and exact cited range on the
correct PDF page. Explain that the model returned only an allowed opaque chunk ID; the server
resolved the title, revision, anchor, quote, and offsets.

If the response abstains, do not hide it. Confirm that the intended document revision is ready and
keep the failure in the demo evidence; never lower the guardrail live simply to force an answer.

## 2:15–3:45 — prove the human approval boundary

Submit this explicitly synthetic action request:

> For a synthetic September 1 scenario, an authorized sponsor's vendor offboarding notice was
> received at 2026-09-01T09:00:00Z. Propose the required account-disable task; do not execute it
> without review.

Open **Approvals** when the workflow reaches `waiting_approval`. The proposal should identify the
Service Desk, high priority, and a due time of `2026-09-01T10:00:00Z`, supported by the one-hour
source passage.

Before approving, open **Workflow tasks** and show that no task exists for this proposal. Say:

> The graph is durably interrupted. A prompt phrase, forged tool call, or model output cannot cross
> this boundary; approval must bind this exact proposal version and its payload and evidence hashes.

Return to the proposal and approve it. Refresh/poll until the asynchronous resume completes, then
show exactly one task. Repeating the approval cannot create another task because both decision and
task identity are unique in PostgreSQL.

Optionally demonstrate edit semantics with the Severity 1 incident fixture: edit creates a new
pending version, invalidates the old hash, and still creates no task until the replacement is
approved.

## 3:45–4:25 — inspect the audit chain

Open **Audit log**. Follow the same correlation/workflow thread through:

- workflow request and retrieval;
- evidence-binding confirmation/selection, application-derived fields, and proposal creation;
- human approval decision;
- outbox dispatch and worker resume;
- exactly-one task creation.

Explain that later asynchronous events remain traceable to the originating request through their
correlation and causation references. Audit detail redacts secret/token/content-shaped keys before
returning to the browser. Be precise about the fields: each worker creates a new `worker-...`
correlation, and its `causation_id` currently stores the originating request correlation reference.
It is not necessarily an audit-event UUID.

## 4:25–5:00 — close with measured evidence

Open **Evaluations** or the generated `evals/results/latest.md`. State the provider and contract
shown in the report:

- A schema-matching deterministic run can exercise orchestration, exact metrics, and safety
  invariants on the CI path; it is not claimed as model quality or as a remote CI pass.
- The latest stored, verified Ollama run, `20260823T234625509074Z-ollama-914d80632516`, completed on
  August 24, 2026. It uses schema 1.2.0/dataset v1.0.2, completed 25 of 25 cases, and passed safety,
  quality, and overall gates. Its raw response capture is enabled and its exact raw-file SHA-256
  is `be9f481ef13719ce1bef4b6f752bfc2409657366282ee6abff8f559515f54ada`. Do not present it as a run
  performed during a later live demo, screenshot session, or video capture.
- The older `20260823T154041554662Z-ollama-2237aa9ef1fd` run remains a failed schema 1.1.0/dataset
  v1.0.1 historical artifact: 18 of 25 completed, 7 failed, and both safety and quality failed.
  Show it only as preserved, non-comparable failure evidence.
- No paid LLM judge is used. Retrieval, citation, field matching, unsupported claims, tool sequence,
  approval compliance, injection compliance, abstention, and latency are computed from raw outputs.

Finish with:

> The interesting engineering is not just local RAG. It is the evidence boundary, durable retries,
> version-bound approval, cross-transport RBAC, and a reproducible test and evaluation story that
> fits on a 16 GB CPU-only Windows laptop.

## Automated proof path

For a non-interactive evidence run:

```powershell
pwsh -File scripts/demo.ps1 -Reset
pwsh -File scripts/evaluate.ps1 -Provider ollama -CaptureRawResponses
```

The demo command emits `artifacts/verification/demo.json`; evaluation emits a timestamped raw run,
summary, Markdown report, and `latest` pointers under `evals/results/`. A nonzero exit is a genuine
failure and must remain visible.

## Optional MCP boundary proof

For a longer engineering interview, use a local MCP client without putting the ignored bearer on
screen. Show that `get_document_section` returns an offset-bounded slice (at most 8,000 characters)
and explain that `list_pending_approvals` requires reviewer/admin authority. The bootstrap bearer is
admin-bound; do not present it as a viewer credential. Show the audit row for each intentional tool
outcome. An unexpected tool failure is sanitized and the service attempts a failed audit unless
PostgreSQL itself is unavailable.

Then submit the same cited task through `propose_workflow_task`. It creates only a pending proposal
with canonical payload and evidence hashes. This MCP-direct run is marked with explicit provenance
and intentionally has no fabricated LangGraph checkpoint. Human approval follows the dedicated
direct-resume route, which invokes the same binding, current-reviewer, current-evidence,
exactly-once task, and audit checks as the graph route. Show zero tasks before approval and exactly
one after replaying the approved decision.

## Screenshot evidence

The refreshed release set contains 12 ordered frames, from local sign-in through the stored,
verified evaluation result. Open the [complete visual pipeline](screenshots/pipeline/README.md) for
the filenames, capture conditions, and per-frame labels, or the
[pipeline walkthrough](pipeline.md) for the matching technical explanation.

The evaluation frame shows the stored August 24, 2026 result; it does not imply that evaluation was
rerun during the August 30 capture. Do not composite, edit, or substitute fixture screens for
behavior that was not observed.
