# ADR 0002: Server-owned evidence and citation identity

- Status: accepted
- Date: 2026-08-23

## Context

A small local model can produce fluent but unsupported text or invented citation metadata. Uploaded documents are untrusted and may contain instructions intended to change system behavior.

## Decision

Document text is always delimited as untrusted evidence and never participates in actor identity, permission, tool selection, approval, or execution. Intent classification receives the authenticated user request, not retrieved text. The model may return only opaque IDs from the retrieved set; application code resolves document title, revision, anchor, exact quote, and offsets and rejects unknown, stale, cross-user, or non-retrieved IDs.

PDFs use true one-based pages. DOCX uses stable heading/paragraph anchors and TXT uses stable line ranges; the UI never fabricates pages for non-paginated formats. Chunks never cross an anchor boundary. Retrieval combines exact pgvector cosine search with PostgreSQL full-text search using deterministic reciprocal-rank fusion; ANN indexes are deferred until corpus measurements justify them.

Every answer passes a sufficient-context gate. Missing evidence produces partial or insufficient status, not a guessed answer. One structured-output repair is allowed; a second schema failure ends safely.

## Consequences

- Citation deep links remain stable for a document revision and can highlight exact stored text.
- Reprocessing creates a new revision rather than silently moving old citation targets.
- Retrieval/model quality can improve without changing the public evidence contract.
- Prompt injection is mitigated by privilege separation and validation; the project does not claim perfect detection.
