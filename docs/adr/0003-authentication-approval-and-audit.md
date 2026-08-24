# ADR 0003: Opaque sessions and version-bound approval

- Status: accepted
- Date: 2026-08-23

## Context

The browser, REST API, LangGraph workflow, Celery worker, and MCP transport must share one authorization policy. A chat phrase or document instruction must never count as human approval, and retries must not duplicate tasks.

## Decision

The browser uses a random opaque session ID stored only as an HttpOnly SameSite cookie; the database stores its hash, actor, role, expiry, and revocation state. Passwords use Argon2id. State-changing browser calls include an in-memory synchronizer CSRF token. Bootstrap generates local credentials into ignored `.env`; no working password is committed.

MCP uses loopback Streamable HTTP. A hashed bearer credential is resolved by middleware into a trusted principal; actor and role are not tool inputs. REST, MCP, worker, and graph nodes call the same policy service.

An approval binds proposal ID, immutable version, canonical payload SHA-256, graph thread, evidence snapshot, expiry, and decision actor. Editing creates a new pending version. Decision and execution recheck role and hash under row locking; a unique idempotency key permits one task. The task mutation and application audit event commit in the same database transaction or fail closed.

## Consequences

- Frontend role gates are usability only; backend denial is authoritative.
- Session revocation works without a signing-key rotation and avoids browser token storage.
- LangGraph nodes may replay safely because no non-idempotent side effect occurs before an interrupt.
- Any missing privileged audit row, stale decision, role leak, or unauthorized execution disables the execution path and blocks delivery.
