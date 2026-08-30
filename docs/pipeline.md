# LocalGuard AI: complete product pipeline

[Back to the project overview](../README.md) · [Architecture](architecture.md) · [Security](security.md) · [Evaluation](evaluation.md)

This walkthrough follows one evidence-bound workflow from local sign-in through document indexing,
grounded answering, exact citation proof, human approval, exactly-once task creation, audit, and
measured evaluation. The screenshots come from the validated local application; the documents in
the demonstration are synthetic.

[Watch the 160-second product tour](../demo-video/output/product-demo.mp4) or open its
[captions](../demo-video/output/product-demo.srt) for a concise pass through the same live
application surfaces.

![LocalGuard AI end-to-end pipeline](visuals/localguard-pipeline.svg)

## 1. Sign in to the private local workspace

![Local sign-in screen](screenshots/pipeline/step-01-sign-in-local-workspace.png)

The browser authenticates with an opaque HttpOnly local session. Viewer, reviewer, and administrator
roles are enforced by the server; document text is never an authentication or approval channel.

## 2. Confirm operational state

![Overview and system status](screenshots/pipeline/step-02-overview-system-status.png)

The overview makes documents, indexing work, questions, proposals, tasks, recent activity, and the
latest stored evaluation visible in one place. PostgreSQL is the source of truth for this state.

## 3. Inspect the indexed policy

![Ready indexed document](screenshots/pipeline/step-03-inspect-indexed-document.png)

The captured frame proves that the synthetic vendor-access policy is ready for retrieval. In the
preceding intake stage, PDF, DOCX, and TXT uploads are validated and stored as immutable revisions
with stable anchors, bounded chunks, MiniLM embeddings, pgvector data, and PostgreSQL full-text
data.

## 4. Choose the evidence-answer workflow

![Ask LocalGuard workspace](screenshots/pipeline/step-04-ask-evidence-question.png)

The Ask workspace states the contract before a request is sent: answers come from the authorized
indexed vault, citations open exact proof, and requested actions still require human approval.
There is no per-document selector on this screen.

## 5. Submit a grounded question

![Prepared grounded question](screenshots/pipeline/step-05-submit-grounded-question.png)

Retrieval fuses vector and full-text ranks across the user's authorized, ready indexed documents. A
request-local sufficient-context gate rejects evidence that is absent, contradictory, conditional,
or unrelated.

## 6. Receive an evidence-derived answer

![Grounded answer with citation](screenshots/pipeline/step-06-grounded-answer-with-citation.png)

The local Qwen model confirms a scoped opaque evidence binding or abstains. The application derives
the factual answer, normalized claim, and server-resolved citation from the confirmed marker bytes.

## 7. Open exact source proof

![Immutable document citation](screenshots/pipeline/step-07-open-exact-source-proof.png)

The citation resolves to a document, immutable revision, stable page or structural anchor, and exact
start and end offsets. The viewer highlights the stored bytes that support the answer.

## 8. Request an evidence-bound action

![Evidence-bound action request](screenshots/pipeline/step-08-propose-evidence-bound-action.png)

For the explicitly synthetic September 1 scenario, the application scopes valid rule candidates
and derives the actor, action, description, priority, source citation, and due time from one
confirmed binding and the trusted 09:00 UTC event supplied by the authenticated user. It proposes
an internal task; it does not disable an external account.

## 9. Review an inert proposal

![Pending approval with no task created](screenshots/pipeline/step-09-review-pending-proposal.png)

The LangGraph workflow pauses at human review. The stored proposal binds its version, canonical
payload hash, evidence hash, expiry, actor, and graph thread. No matching task exists yet.

## 10. Approve and create exactly one task

![Approved task and provenance](screenshots/pipeline/step-10-approved-task-created-once.png)

An authorized approval resumes the workflow only after every binding is rechecked. Database
uniqueness permits one task; replay cannot create a duplicate.

## 11. Inspect the causal audit trail

![Correlation-bound workflow audit trail](screenshots/pipeline/step-11-inspect-causal-audit-trail.png)

Ingestion, retrieval, validation, proposal creation, the human decision, graph resume, internal
task creation, retries, failures, and durable outbox dispatch leave correlation-bound events.

## 12. Verify the measured result

![Passing evaluation result](screenshots/pipeline/step-12-verify-evaluation-results.png)

The latest stored, verified local-model run completed all 25 hash-verified synthetic cases and
passed its safety, quality, and overall gates. It was completed on August 24, 2026; it is not
presented as a run executed during the screenshot or video capture. The corpus covers grounded
answers, insufficient evidence, indirect prompt injection, and action/approval behavior. See
[evaluation.md](evaluation.md) for the exact corpus identities, formulas, thresholds, current
result, and honest historical evidence.

## Where the pipeline lives in code

| Pipeline surface | Primary implementation |
|---|---|
| Web experience and same-origin BFF | [`apps/web`](../apps/web) |
| Auth, intake, retrieval, evidence binding, workflow, audit | [`apps/api/localguard_api`](../apps/api/localguard_api) |
| Background indexing and durable retries | [`services/worker`](../services/worker) |
| Audited local tools | [`services/mcp`](../services/mcp) |
| OpenAPI and runtime contracts | [`packages/contracts`](../packages/contracts) |
| Evaluation corpus and validators | [`evals`](../evals) |
| Unit, integration, security, browser, and evaluation tests | [`tests`](../tests) and [`apps/web/e2e`](../apps/web/e2e) |
