# Verification Log

This ledger records observed evidence. Planning estimates are labelled as estimates and are replaced by measured artifacts as each phase closes.

## 2026-08-23 — Phase 0 pre-build baseline

| Check | Observed result | Status |
|---|---:|---|
| Host memory | 15.68 GB total; 4.51 GB free at 02:26 UTC | recorded |
| C: free space | 98.14 GB | recorded |
| Project working files | 69,582 bytes (0.066 MB) | recorded |
| Docker images before LocalGuard | 2 images; 13.32 GB | unrelated baseline, excluded from project delta |
| Docker stopped containers before LocalGuard | 4 containers; 4.673 GB writable size | unrelated baseline, never pruned by project scripts |
| Docker local volumes/build cache | 0 B / 0 B | project delta starts at zero |
| Docker engine | 29.7.2, Linux engine reachable | pass |
| Compose | v5.3.1-desktop.1 | pass |
| Host Python | 3.11.9 plus 3.13.3; no 3.12 | informational; project uses Python 3.12 container |
| Node/npm | Node 24.13.0; npm 11.6.2 | pass |
| Host Ollama | absent | expected; project uses pinned CPU-only container |

Docker Desktop itself used approximately 0.75 GB across its visible Windows processes at this sample; WSL VM memory will be included once LocalGuard containers are active. No unrelated images, containers, files, or processes were removed.

## Planning proof

- `docs/implementation-plan.md`: the pre-build gated plan; adversarial review initially failed,
  blocker corrections were applied, and the second review returned `PASS`.
- The pre-build verification matrix mapped phase gates and all 15 definition-of-done items to proof;
  this log is its public, machine-path-free evidence ledger.
- Root syntax checks: PowerShell parser, Python `tomllib`, and Node JSON parsing all returned `PASS` after scaffold creation.

## Evidence policy

Phase 0 closed after the locked dependencies, Compose configuration, reversible migrations,
synthetic-data validation, model-selection gate, and initial test harnesses below passed. Later
sections append commands, exit codes, artifact paths, metrics, and failures without replacing the
baseline or silently rewriting an earlier result.

## 2026-08-23 — Foundation integration evidence

| Check | Observed result | Status |
|---|---:|---|
| Backend dependency resolution | `docker compose build api`; 154 packages frozen from Python 3.12 image | pass after correcting Redis client to 6.4.0 for Celery/Kombu compatibility |
| Database migration | upgrade → metadata check → downgrade → upgrade | pass |
| pgvector extension | present after upgrade; absent after downgrade | pass |
| Schema drift | `alembic check` returned `No new upgrade operations detected.` | pass |
| Synthetic source validator | 8 clean sources, 5 attacks, exactly 25 cases, category split 10/5/5/5 | pass after adversarial fixes |
| Evaluation negative self-test | schema, source-hash, and artifact-hash mutations | all rejected |
| Upload-ready fixtures | 13 documents: 6 PDF, 4 DOCX, 3 TXT; 176 stable markers | pass after regeneration |
| Fixture structural validation | every generated hash, PDF page, DOCX paragraph, TXT line, marker, and synthetic notice resolved | pass |
| Fixture visual QA | all 12 PDF pages and all 4 Word-rendered DOCX pages inspected; changed continuity page re-reviewed | pass; no clipping, overlap, or broken glyphs |

The packaged LibreOffice DOCX renderer was attempted first and failed because `soffice` is absent. The documented Windows fallback was then used: Office COM preflight returned `can_use_com=true`, Microsoft Word exported all four DOCX fixtures to PDF, and those rendered pages were inspected. The temporary review PDFs and PNGs are not repository deliverables.

## 2026-08-23 — Phase 1 vertical-slice gate

All checks below were reproduced from the dependency-locked Python 3.12 backend image. The
working tree was bind-mounted for source checks so the commands verified the exact files under
review rather than a stale image layer.

| Check | Observed result | Status |
|---|---:|---|
| Backend image from `requirements.lock` | 154 resolved packages; image build completed | pass |
| Ruff lint | 32 Python files across API, worker, migrations, scripts, and backend tests | pass |
| Ruff format check | 32 files already formatted | pass |
| Strict mypy | 21 API and worker source files | pass, zero issues |
| Deterministic backend suite | 25 passed; 2 opt-in integration tests skipped | pass |
| Real PostgreSQL/pgvector/Redis integration | 2 passed | pass |
| Synthetic fixture validation | 13 files and 176 stable anchors | pass |
| Evaluation-corpus adversarial self-test | schema and both hash-mutation checks rejected | pass |
| Compose interpolation and schema | `docker compose config --quiet` | pass |
| Git whitespace check | `git diff --check` | pass |

The first broad test invocation intentionally injected test-provider environment variables into
the entire suite and caused two configuration-policy tests to fail. Re-running with the suite's
documented environment produced 25 passes. The failure was retained here because it confirmed
that production-mode and deterministic-provider safeguards are environment-sensitive as designed.

## 2026-08-23 — bounded local-model selection gate

The pinned Ollama runtime was attached to the temporary `model_egress` network only while pulling
the two candidates and embedding model. It was then recreated on the internal-only backend network
before inference. Both candidates ran the same three sequential, schema-constrained cases covering
a grounded deadline, irrelevant evidence, and an embedded instruction. No LLM judge was used.

| Candidate | Strict cases | Warm median | Notable behavior | Decision |
|---|---:|---:|---|---|
| `qwen3:1.7b-q4_K_M` | 3/3 + 384d embed | 4,912.23 ms | concise grounded answers and abstention | selected |
| `qwen2.5:1.5b-instruct-q4_K_M` | 3/3 | 11,294.36 ms | repetitive 175-token abstention | removed |

The observed Ollama container peak during the selected-model gate was 2.008 GiB of its 4 GiB cap;
the API runner used about 47 MiB. The retained MiniLM embedding returned one finite
384-dimensional vector in 646.93 ms. The retained generation and embedding model volume was
1,405,257,156 bytes. Exact model-manifest hashes and the Node/container pins are recorded in
`docs/runtime-lock.json`; raw per-case timings, token counts, and outputs are stored in
`artifacts/model-gate-qwen3-1.7b.json` and the rejected-candidate comparison artifact.

## 2026-08-23 — Phase 2 migration and checkpoint gate

Alembic revision `c57f8be7e15c` adds the workflow and reliability schema. Corrective revision
`20260823_0003` reconciles databases created from the pre-final Phase 2 shape. The data-bearing
matrix exercised the Phase 1 schema, the historical Phase 2 shape, and the final head against a
disposable PostgreSQL database.

| Check | Observed result | Status |
|---|---:|---|
| Existing-data upgrade | Phase 1 document, revision, and question rows upgraded with expected backfills | pass |
| Legacy duplicate content | later active duplicate quarantined with its revision and file reference preserved; downgrade restored the prior state | pass |
| Historical Phase 2 repair | pre-final c57 constraints and indexes reconciled by `20260823_0003` | pass |
| Citation-loss guard | populated orphan citation blocked downgrade before DDL; export and exact-confirm purge then allowed downgrade | pass |
| Schema drift before checkpoint setup | `alembic check` reported no operations | pass |
| LangGraph setup | four PostgreSQL checkpoint tables created by the pinned library | pass |
| Schema drift after checkpoint setup | externally managed tables ignored; no Alembic operations | pass |
| Application-schema reversal | downgrade to base and upgrade through all three revisions after resolving the explicit citation guard | pass |
| Checkpoint retention | externally managed checkpoint tables and rows intentionally survive Alembic downgrade | pass, separate export/purge procedure documented |
| Phase 2 schema at that checkpoint | revision `20260823_0003`; 24 public tables including four LangGraph tables | pass (historical; superseded by 0004 below) |

## 2026-08-23 — Structured-finding evidence migration

Revision `20260823_0004` adds exact marker IDs, structured fields, and derivation provenance to
persisted findings without changing the public-table count. A disposable PostgreSQL 16 matrix
proved legacy backfill, transactional failure recovery, data-loss refusal, and full-chain recovery.

| Check | Observed result | Status |
|---|---:|---|
| Legacy finding upgrade | pre-0004 finding preserved with `origin=model` and empty marker/field metadata | pass |
| Evidence-bearing downgrade | populated deterministic-normalizer finding blocked downgrade before DDL and remained byte-for-byte queryable | pass |
| Explicit cleanup and recovery | after explicit probe-row removal, downgrade to 0003 and re-upgrade to 0004 preserved legacy meaning | pass |
| Historical/full migration chain | c57 reconciliation plus base-to-head recovery completed at `20260823_0004`; `alembic check` found no drift | pass |
| Restart/API persistence | real PostgreSQL graph write survived process/checkpointer loss and `GET /findings` returned actor, action, deadline, marker, and provenance | pass (`1 passed`) |

## 2026-08-23 — Release-contract alignment

This section records the frozen release identities and final local verification. It does not replace
the historical phase evidence above.

| Contract | Current audited value |
|---|---|
| Alembic head | `20260823_0004` |
| Evaluator schema | `1.2.0` |
| Dataset | v1.0.2, 25 cases; final audited release identity |
| Cases SHA-256 | `914d80632516db91cbd46700f52564677aa3a3b264d5c747b6537a8d1690392c` |
| Canonical manifest SHA-256 | `bb6e6da1b7eaa5a12e7f09020289a5e35ac5ea6f27c6ba161d378562c744b765` |
| Generated fixture manifest SHA-256 | `dbf94e15405e09637f90a4331fa525baeebb9684aa8f9cf65039a648e38c05d6` |
| Corpus bundle SHA-256 | `19594770fb8e359bb68c8b7944ca63ad36ac93ba77f4da227fd7a53a5aa4633e` |
| Ordinary QA normalizer | `qa-fact-binding-v1`: model confirms opaque exact-marker bindings; application derives answer, claims, and citations |
| Structured mode | `evidence_derived_binding_confirmation_v2`: application scopes the full set; model confirms or abstains; application derives fields |
| Action mode | `evidence_derived_binding_selection_v2`: model selects one scoped binding or abstains; application derives claim/proposal fields |

Final real-model run `20260823T234625509074Z-ollama-914d80632516` completed 25/25 with no execution
failure and passed safety, quality, and overall gates. Raw response capture was enabled. Its exact
raw SHA-256 is `be9f481ef13719ce1bef4b6f752bfc2409657366282ee6abff8f559515f54ada`.
Macro retrieval recall@5 was 0.9667, both citation-precision views were 1.0000, extraction F1 was
0.8889, exact tool and proposal accuracy were 1.0000, and total latency p95 was 15,546.71 ms. The
run recorded 20 accepted first calls, no repair/retry, 5/5 abstentions, 7/7 approval transitions,
27/27 injection controls, 97/97 forbidden controls, and zero preapproval tasks or executions.

The older `20260823T154041554662Z-ollama-2237aa9ef1fd` run remains unchanged as metadata-only,
non-comparable failure evidence: schema 1.1.0/dataset v1.0.1, 18/25 completed, 7 case failures,
safety failed, and quality failed.

Final exact-image gates on the frozen tree: 383 unit tests passed; 45 isolated PostgreSQL/Redis
integration tests passed with one expected opt-in Ollama skip; 46 frontend tests passed; Ruff,
strict mypy (44 source files), OpenAPI drift, frontend contracts/lint/types/build, Alembic head and
drift, and 143/143 backend copied-file hashes passed. The live portfolio Playwright journey passed
and published seven screenshots atomically. The current demo artifact SHA-256 is
`1a2970d3b2b0d311625d3af801aef24f3796124199d32ba89d3c68e1e516f53e`.

| Definitive image | OCI index | Linux/amd64 manifest | Config |
|---|---|---|---|
| Backend | `6d30482e6a75ac7187a1fe13dbb3d511d889616ae14f86eb466843dadf968c35` | `68b395279d400280949fe0506c21e4e550e6881837ce54c185b78256c8729bd1` | `be74ed1063724dabcb40f47a597aecbf076b2bf11e2a01f2d0797217eb886559` |
| Web | `34b3402fdb9111b21bebd585873a277febffb6c271cc225e69758ef2b802a0b6` | `5f696c2cdbc43c3e4848750d6898ecd1d5da39faf82bedbf80e947545b286ad9` | `5480cab6db5660209187b09d47d8c8238df8819aca80579ba3898459c08e5f8a` |

The live API, worker, and MCP containers all run the backend index above; the live web container
runs the web index. Screenshot SHA-256 values are: overview `0678eb9b7deab4df5c37bdb8790baa00ad5fe56f389d32c7346a0b9ee2afbf7c`,
ask `426107a6446eecb101157624739b667ac38b1e078f58c54ccd50d39c59f8a7be`, citation
`9894828cbe1695f9a1cb9c402b5fe95e669faf13d4ddb090265b2eda441a113b`, pending approval
`a73b6bbd0235c03c90f2ddbc37313f9ca9f9b922a31eccfdf2069e70d80ab8d3`, task
`156d71b412a1af70c655cc1313b009fbd036915d5c12ae8d9565556153f138ab`, audit
`ef9cf46c22ecdb631ad0fc97ad5cad59f66ec1a09f2240c5540b85df2c9973a8`, and evaluation
`c349d2c5a0d0aef523331aa21f3b0a59ff92343c3ff9e0102685938871642b13`.

Final resource evidence on the target laptop: 576.06 MiB unloaded full-stack idle memory, 3,976.33
MiB successful warm-query peak, 195.19 ms mean retrieval, 8,921.34 ms mean generation, 6,730.53 ms
for all 13 fixtures, 727.49 ms for the demo PDF, and approximately 12.94 GB retained attributable
disk. Both memory and disk targets passed. The fully identified 11.39 GB LocalGuard build cache,
one stale audit image, and 12 disposable audit volumes were removed; live app data and models were
preserved.
