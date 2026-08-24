# Troubleshooting

Run commands from the repository root in PowerShell 7. Project scripts stop on the first failed
check; the last error is normally more useful than later container noise.

## Docker Desktop is not ready

Symptom: bootstrap reports that the Linux engine is unavailable.

1. Start Docker Desktop and wait until it reports that the engine is running.
2. Verify it directly:

   ```powershell
   docker info --format '{{.ServerVersion}}'
   docker compose version
   ```

3. If Docker Desktop is not installed, the free Windows installation command is:

   ```powershell
   winget install --exact --id Docker.DockerDesktop
   ```

The scripts do not install or start a system application silently.

## A loopback port is already in use

The standard ports are 3000 (web), 8000 (API), and 8001 (MCP). Find the owning process without
terminating it:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 3000,8000,8001 |
    Select-Object LocalAddress,LocalPort,OwningProcess
```

Stop the conflicting application yourself or change the Compose host port and corresponding local
origin settings together. Do not expose LocalGuard on `0.0.0.0` merely to avoid a conflict.

## A service is unhealthy

Inspect bounded status and logs:

```powershell
docker compose --profile app ps
docker compose logs --tail 200 api worker web mcp ollama db redis
```

Common causes are an unapplied migration, missing model, unhealthy Docker volume, invalid `.env`, or
the model lock TTL being shorter than its HTTP timeout. Re-run bootstrap after correcting the first
reported cause:

```powershell
pwsh -File scripts/bootstrap.ps1
```

Do not delete volumes as a first response; PostgreSQL, uploads, and model data are intentionally
preserved by `scripts/stop.ps1`.

The current Alembic head is `20260823_0004`. Check it without changing data:

```powershell
docker compose run --rm api alembic current
docker compose run --rm api alembic check
```

## Bootstrap rejects the configuration

LocalGuard validates settings before the API starts. Typical deliberate failures include:

- deterministic providers outside `APP_ENV=test` with `ALLOW_TEST_PROVIDERS=true`;
- different `AI_PROVIDER` and `EMBEDDING_PROVIDER` values;
- a model lease TTL less than the HTTP timeout plus 30 seconds;
- an empty host/origin allowlist;
- insecure cookies in production mode;
- unchanged bootstrap password or MCP token placeholders.

Compare names—not secret values—with `.env.example`. If `.env` is missing, bootstrap creates a new
one. It never overwrites an existing credential file.

API, worker, and MCP deliberately receive empty bootstrap-password and bootstrap-token variables;
this is not a configuration loss. Only `admin-cli` receives them for explicit seed and rotation
operations. The database receives only its PostgreSQL variables.

## A model is missing or its manifest does not match

Bootstrap pulls only the two models in `docs/runtime-lock.json` and hashes their local Ollama
manifests. A mismatch stops setup because an unchanged tag is not accepted as proof of unchanged
content.

Check the project volume without exposing document data:

```powershell
docker compose -f docker-compose.yml -f docker-compose.bootstrap.yml `
    --profile app up -d --wait ollama
docker compose exec -T ollama ollama list
docker compose -f docker-compose.yml -f docker-compose.bootstrap.yml stop ollama
```

Then rerun bootstrap. The model-download procedure intentionally uses network only through this
explicit overlay; the edge-network egress limitation is described below.

## CPU generation is slow

The first response after a model swap or cold start is expected to be slower than a warm request.
Keep the defaults unless measurement shows a problem:

- one Celery worker process;
- `OLLAMA_NUM_PARALLEL=1`;
- `OLLAMA_MAX_LOADED_MODELS=1`;
- 4096-token context;
- at most 512 output tokens.

Do not enable CUDA on this project’s target machine. Avoid running the Playwright browser process,
real evaluation, and an interactive demo simultaneously.

## Memory or disk approaches the project limit

Inspect before removing anything:

```powershell
docker stats --no-stream
docker system df -v
(Get-ChildItem . -Force -File -Recurse | Measure-Object Length -Sum).Sum
```

Stop the application to release active memory while preserving data:

```powershell
pwsh -File scripts/stop.ps1
```

The project never runs a global Docker prune because unrelated images and volumes may belong to the
user. Browser output, `.next`, and other ignored build products can be regenerated; confirm their
exact project paths before removing them manually.

## An upload is rejected

The UI’s validation is advisory; FastAPI is authoritative. Confirm that:

- the file is PDF, DOCX, or UTF-8/plain TXT;
- extension, declared type, and detected signature agree;
- it is no larger than 10 MB;
- PDFs contain at most 100 pages;
- DOCX is not encrypted, traversal-shaped, or an expansion/compression bomb;
- extracted text remains within configured page, paragraph, line, and character limits.

The API returns a stable error code and correlation ID. Search that ID in the audit page or bounded
API logs; do not upload a private document merely to reproduce a portfolio-fixture issue.

## A document remains queued

An accepted upload has a durable outbox record, so retrying the same file is not the recovery
mechanism. Check worker and API reconciliation logs:

```powershell
docker compose logs --tail 200 worker api redis
```

Restart the normal profile after Redis or the worker recovers. The API reconciler dispatches pending
rows and reclaims stale `dispatched` leases with the same task ID. Workers mark the outbox row
`acked` only when PostgreSQL confirms that delivery's domain transition is complete; reaching an
approval interrupt completes a workflow-start delivery. A transient model or service failure
releases the aggregate for Celery's next retry and is marked failed only on the final attempt.
Repeatedly uploading the same bytes is intentionally deduped.

The same lease/ACK behavior applies to queued questions, workflow starts, and approval resumes. Do
not manually change outbox state to make a stuck item disappear; that can hide work that never
reached its terminal database transition.

## A question says evidence is insufficient

This may be the correct guardrail. LocalGuard requires an absolute relevance signal as well as a
good rank. Check that the intended revision is ready and that the question names terms present in
the selected document scope. Do not lower the retrieval thresholds merely to force an answer;
evaluate the change against irrelevant and injection cases first.

## Login is temporarily blocked

Concurrent failures count toward a database-backed window. Wait for the configured window or sign
in with the correct generated password from the ignored `.env`. Passwords are never printed by
seed or normal startup. Bootstrap does not replace an existing `.env`, so rerunning it will not
recover a lost credential; use the explicit `create-user` CLI for a new local account.

To rotate the local demo administrator instead, use the supported script:

```powershell
pwsh -File scripts/rotate-demo-admin.ps1
```

It updates `.env` atomically, runs the seed path, and prints no password. Seed re-applies all three
demo principals and revokes active browser sessions for existing principals, so sign in again after
the rotation. If database synchronization fails, the script restores the old `.env` value and
attempts to reseed it before returning the error.

## An MCP bearer is expired or was exposed

The bootstrap bearer expires after 30 days by default; configure
`MCP_BOOTSTRAP_TOKEN_TTL_DAYS` from 1 to 365 before synchronization if a different local lifetime
is required. Rotate the ignored `.env` value and database hash together:

```powershell
pwsh -File scripts/rotate-mcp-token.ps1
```

The script calls `sync-mcp-token`, refreshes the finite expiry, revokes prior active bootstrap
bearers, and never prints the replacement. If you deliberately changed the token in `.env` through
another secure procedure, synchronize it explicitly with:

```powershell
docker compose run --rm admin-cli python -m localguard_api.cli sync-mcp-token
```

Do not put the bearer on a command line or in a tracked MCP client configuration. Authentication
failures that occur before a principal is resolved cannot have an actor-attributed tool audit.

## Browser tests show CSP `eval` messages

The UI contract suite may use the Next development server, whose diagnostics require development
evaluation support. Production builds retain the strict nonce-based CSP. The unmocked full-stack
gate runs against the production server, which is the authoritative CSP check.

## Evaluation exits nonzero

That means at least one safety or quality gate failed; it is not a report-generation failure.
Inspect the generated files:

```powershell
Get-Content evals/results/latest.md
```

`run.json` contains per-case retrieved markers, claims, extraction, tool trace, policy outcomes, and
stage timings. Fix the application or dataset contract and rerun. Never edit a generated report to
turn a failure into a pass.

Before treating a run as the final release evaluation, verify schema `1.2.0`, final audited dataset
v1.0.2 and its hashes, structured mode `evidence_derived_binding_confirmation_v2`, and action mode
`evidence_derived_binding_selection_v2`. The retained
`20260823T154041554662Z-ollama-2237aa9ef1fd` result is an intentional historical failure from
schema 1.1.0/dataset v1.0.1 (18 of 25 completed, 7 case failures, safety and quality failed); it is
not comparable to final run `20260823T234625509074Z-ollama-914d80632516`, which completed 25/25
and passed safety, quality, and overall gates. Its raw SHA-256 is
`be9f481ef13719ce1bef4b6f752bfc2409657366282ee6abff8f559515f54ada`. The v1.0.2 hashes documented
in the evaluation guide and verification log are the final audited corpus identities.

## A Phase 2 downgrade is blocked by orphan citations

This is a deliberate fail-closed check. Phase 2 preserves citation title, revision, anchor, quote,
and range snapshots after source deletion by allowing their chunk reference to become null. Phase 1
cannot represent that state.

First export the snapshots to a new private path. The command refuses to overwrite a file:

```powershell
docker compose run --rm admin-cli python -m localguard_api.cli `
    export-orphan-citations `
    --output /workspace/artifacts/verification/orphan-citations-before-phase1.json
```

Verify and retain that ignored JSON with the database backup. If and only if losing those database
snapshots is acceptable, use the exact confirmation and retry the downgrade:

```powershell
docker compose run --rm admin-cli python -m localguard_api.cli `
    purge-orphan-citations --confirm "PURGE ORPHAN CITATIONS"
docker compose run --rm api alembic downgrade 20260823_0001
```

The c57 migration also handles old active duplicates deterministically. It leaves the earliest
document for each creator/source hash active, marks later rows deleted, retains their revisions and
private files, and records `migration.document_duplicate_quarantined`. Downgrading c57 restores the
previous states and marks those migration audits `reverted`; do not delete the quarantined private
files manually if reversibility matters. Revision `20260823_0003` only reconciles historical schema
drift and has a no-op downgrade. Revision `20260823_0004` adds lossless structured-finding marker,
field, and provenance columns. A downgrade to `20260823_0003` deliberately fails while any finding
uses them; export the affected findings and explicitly remove those rows before retrying only when
that evidence loss is acceptable.

## Checkpoint rows remain after an Alembic downgrade

That is expected. The pinned LangGraph checkpoint library, not Alembic, owns
`checkpoint_migrations`, `checkpoint_writes`, `checkpoint_blobs`, and `checkpoints`. Application
schema downgrades deliberately leave them intact.

Retention is the default. If policy requires deletion, stop workflow producers, take and verify a
PostgreSQL backup, then use the separate exact-confirm command:

```powershell
docker compose --profile app stop api worker mcp
docker compose run --rm admin-cli python -m localguard_api.cli `
    purge-checkpoints --confirm "PURGE CHECKPOINT HISTORY"
```

This removes checkpoint writes, blobs, and thread checkpoints, but preserves the checkpoint tables
and their migration metadata. The operation is not undone by an Alembic upgrade; restore the backup
if the history is needed again.

## The web container cannot resolve PostgreSQL

This is the intended network boundary. Web joins only the `edge` network and reaches FastAPI by its
internal API name; database, Redis, Ollama, and worker remain on the internal `backend` network.
API and MCP bridge edge to backend. Edge must be non-internal for Docker Desktop's loopback port
publishing, so this layout does not technically prevent outbound connections from web, API, or MCP.
Use a host firewall or a stricter deployment network when enforced egress denial is required.

## Safe reset boundaries

`pwsh -File scripts/demo.ps1 -Reset` removes only data owned by the three generated demo accounts
and their private upload files. It does not remove arbitrary users, Docker images, or unrelated
volumes.

A complete database/volume reset is intentionally not automated in the normal scripts because it
is destructive. If one is ever necessary, first stop the project, identify the exact
`localguard_*` volumes with `docker volume ls`, back up anything needed, and confirm the target
before removal.
