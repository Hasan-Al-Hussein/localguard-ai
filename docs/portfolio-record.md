# LocalGuard AI portfolio preservation record

Recorded on **2026-09-26**. This catalog preserves delivered engineering work and selected
historical evidence. It is not a new runtime evaluation, a production certification, or a backup
of the original machine.

## Delivered work and public source

The localhost application implements source-preserving PDF, DOCX, and TXT ingestion; hybrid
pgvector/full-text retrieval; exact citation resolution; bounded model-confirmed evidence
bindings; authenticated human approval; database-enforced task uniqueness; and correlated audit
records. The [pipeline](pipeline.md), [architecture](architecture.md), and
[security boundaries](security.md) connect those capabilities to their implementation and limits.

Two public source snapshots serve different purposes:

| Snapshot | Preserved scope |
|---|---|
| [Main at `79b9a79`](https://github.com/Hasan-Al-Hussein/localguard-ai/tree/79b9a79b8ec25a5ef39ca3c3f08aa112310cf4cb) | Localhost application, contracts, synthetic corpus, tests, operating documentation, and product film; baseline for this preservation update |
| [Showcase at `94608ee`](https://github.com/Hasan-Al-Hussein/localguard-ai/tree/94608eebe8f996f6f304039f04123afa46672f7b) | Separate public branch containing `apps/showcase`, browser-side fixtures/transport, static-export verification, deployment configuration, and showcase tests |

The showcase remains on its existing public branch; this record does not merge its implementation
or change main's build behavior. Its [source](https://github.com/Hasan-Al-Hussein/localguard-ai/tree/94608eebe8f996f6f304039f04123afa46672f7b/apps/showcase)
implements a deterministic, browser-only demonstration with synthetic data. It has no live model,
document uploads, durable persistence, or real-world action execution. Refresh resets browser
state. A hosted showcase screen cannot establish that the localhost services are running.

## Project map

| Path | Responsibility and validation surface |
|---|---|
| `apps/api/localguard_api`, `apps/api/migrations` | FastAPI, authorization, ingestion, evidence binding, workflow persistence, audit, and schema migrations |
| `services/worker`, `services/mcp` | Celery jobs and authenticated FastMCP tools |
| `apps/web` | Local product UI, same-origin API boundary, component tests, and browser contracts |
| `packages/contracts` | OpenAPI snapshot, generated types, and runtime contracts |
| `fixtures`, `evals`, `tests` | Synthetic source corpus, versioned evaluation contract, and deterministic/integration tests |
| `docker-compose*.yml`, `scripts` | Local service configuration, bootstrap, lifecycle, evaluation, and packaging |
| `requirements.lock`, `package-lock.json`, `docs/runtime-lock.json` | Dependency, container, and model identities; Python 3.12 and Node 24 runtime constraints |
| `demo-video`, `docs/screenshots`, `docs/visuals` | Final film/captions, editable Remotion source, narration, source recording, product screenshots, and architecture figures |

The [Windows guide](../README-WINDOWS.txt) and [troubleshooting guide](troubleshooting.md)
describe setup. Reproduction requires the documented prerequisites and dependencies; preserving
source does not make it an offline installation. Test commands and proof boundaries remain in
the [verification ledger](verification-log.md) and [evaluation guide](evaluation.md).

## Historical evidence retained here

The eight files in [the evidence directory](evidence/preservation-20260926/) preserve the selected
original bytes. Their filenames are descriptive archive names; the original locations and SHA-256
identities are listed below. Other files mentioned inside these historical records are not
implicitly included in this archive.

| Published file | Observed historical evidence | Limit |
|---|---|---|
| [Final evaluation summary](evidence/preservation-20260926/evaluation-final-summary.json) and [report](evidence/preservation-20260926/evaluation-final-report.md) | Run `20260823T234625509074Z-ollama-914d80632516`: schema 1.2.0, dataset 1.0.2, 25/25 completed; 31/31 supported returned citations; extraction F1 0.8889; 7/7 approval transitions; zero preapproval tasks/executions | Bounded synthetic corpus and pinned local models, not general model accuracy or production assurance |
| [Legacy evaluation summary](evidence/preservation-20260926/evaluation-legacy-summary.json) and [report](evidence/preservation-20260926/evaluation-legacy-report.md) | Earlier run `20260823T154041554662Z-ollama-2237aa9ef1fd`: 18/25 completed, seven execution failures, safety and quality gates failed | Schema 1.1.0/dataset 1.0.1; not directly comparable to the later run and not release proof |
| [Model identities](evidence/preservation-20260926/model-lock.json) | August 23 manifest hashes for Qwen3 `1.7b-q4_K_M` and MiniLM `22m-l6-v2-fp16` | Identity record, not model binaries or a fresh model check |
| [Indexing measurement](evidence/preservation-20260926/index-benchmark.json) | August 23: 13/13 synthetic fixtures ready, zero failures, 6,730.53 ms measured duration | One recorded local indexing run |
| [Later domain demo](evidence/preservation-20260926/demo-20260824T011852Z.json) | Completed August 24 at 01:18:52 UTC: exact synthetic citation; zero tasks before approval, one after approval, one after replay; correlated audit events | Declared `proof_scope` is `in_process_domain`; not an HTTP/browser test or the earlier ledger demo |
| [Resource summary](evidence/preservation-20260926/resource-final.json) | Measured August 24 at 00:40:23 UTC: 576.06 MiB unloaded idle, 3,976.33 MiB successful warm-query peak, approximately 12.94 GB attributable disk | Historical target-machine measurements; source revision recorded as `unborn HEAD`; underlying samples are not all included and these are not current disk/RAM values |

The final evaluation's original raw-result SHA-256 was independently recomputed during this
preservation review and matched both its summary and the existing ledger:
`be9f481ef13719ce1bef4b6f752bfc2409657366282ee6abff8f559515f54ada`.
The raw `run.json` is deliberately omitted because opted-in model-response capture is private
diagnostic material under the [evaluation policy](evaluation.md).
The published summary/report preserve the original reference hash; they do not enable a reader
to independently recompute every metric without the omitted raw record.

The archived demo is a different run from the demo referenced by the earlier resource summary
and ledger. Those earlier records cite
`1a2970d3b2b0d311625d3af801aef24f3796124199d32ba89d3c68e1e516f53e`;
the later retained `demo.json` hashes to
`aaac2c5ee4424fd2b3897de55a2b62089460633aabab8d28c76c04b28b472a70`.
Both identities are retained as recorded; the later file is not presented as satisfying the
earlier hash or its latency measurements.

## Test receipts and their limits

The two retained local XML files below were parsed during preservation. The table is an extracted
public receipt: hostnames and individual test records are not republished. Counts include skipped
tests; passed counts are total minus skipped, failures, and errors.

| Original receipt | Recorded UTC time | Total | Passed | Skipped | Failures/errors |
|---|---|---:|---:|---:|---:|
| `artifacts/pytest-unit-final.xml` | 2026-08-23 14:01:48 | 234 | 233 | 1 | 0 / 0 |
| `artifacts/pytest-integration-final.xml` | 2026-08-23 14:03:07 | 43 | 42 | 1 | 0 / 0 |

Original XML SHA-256 values, computed without changing the files:

- Unit: `f5f4b42c047f59d00c382da25b4c89a0879b086069e51b18105cb56ef54fbb62`.
- Integration: `037642a7246b32469f229d4744954fd733687a8b8503637641deea9395ca5208`.

Despite their `final` filenames, these XML receipts predate the later release counts. They do
**not** establish the 384 Python unit/security, 45 integration, or 46 frontend test results
documented in the [August 24 verification ledger](verification-log.md).
Those larger counts remain historical documentation claims, not newly executed checks.

Separately, GitHub's [CI run 33508458129](https://github.com/Hasan-Al-Hussein/localguard-ai/actions/runs/33508458129)
records success for main commit `79b9a79b8ec25a5ef39ca3c3f08aa112310cf4cb`, started on
2026-09-01. Its completed status and commit identity were checked through GitHub on September 26.
This is not a claim that the new preservation commit has passed CI. The locally retained
Playwright `.last-run.json` files contain only a pass flag and failed-test list, without enough
date/count/source identity to serve as independent current browser-test receipts.

## Media and authored capture utilities

The [160-second film](../demo-video/output/product-demo.mp4),
[captions](../demo-video/output/product-demo.srt),
[editable Remotion project](../demo-video/remotion/README.md), narration clips, selected source
recording, and [twelve-step product walkthrough](pipeline.md) were already present on public main.
The local `product-demo-final-candidate-160-v2.mp4` has the same SHA-256 as the published film and
adds no distinct deliverable. Other intermediate renders and local screenshots are not promoted
to final evidence by this catalog.

The source-only utilities under [scripts/archived-capture](../scripts/archived-capture/) originated
in ignored `output/playwright/`. They capture the authenticated localhost product UI, despite
the historical word `showcase` in two filenames. They are not an automated verification of the
public browser-only showcase. The originals were inspected; the archived adaptations were not
executed against an application during preservation. Do not commit generated browser state,
credentials, or unreviewed captures.

| Original script | Original SHA-256 |
|---|---|
| `output/playwright/audit-refinement-current.cjs` | `8427a1eafefdac6e8886c9fd6093d882de1f324e1e0a48ef6c2506ca90a8e26f` |
| `output/playwright/capture-showcase-current.cjs` | `c8cb61cd245c164d0018b10e5b0342fa40b4f87ca653aa651ce054269a0d9ff4` |
| `output/playwright/capture-showcase-current.ps1` | `8530de8d9f2ffeb6558794ef5372d8016f2c9c7783f836eb09f3e6885140c62f` |

These hashes identify the original local sources, not any adapted copies. The archive's own
documentation describes relocation changes.

## Evidence provenance

All source locations below are repository-relative paths from the inspected original checkout.
The final evaluation directory was `evals/results/20260823T234625509074Z-ollama-914d80632516/`;
the legacy directory was `evals/results/20260823T154041554662Z-ollama-2237aa9ef1fd/`.

| Archive filename | Original location | Original SHA-256 |
|---|---|---|
| `evaluation-final-summary.json` | Final evaluation directory: `summary.json` | `69bf183d5b515d79c6c751d5f94656f27d4fcfa1780cc19a07601c67cac685fd` |
| `evaluation-final-report.md` | Final evaluation directory: `report.md` | `0dec562e6cd719627ff1778605fe6a000233cfc3acf2b1f853772a05167a4191` |
| `evaluation-legacy-summary.json` | Legacy evaluation directory: `summary.json` | `4f347539f774ab92cd87f5714f2916bd183ee0c70b868d4991d4a1488282dcfa` |
| `evaluation-legacy-report.md` | Legacy evaluation directory: `report.md` | `3330580c2a0e405d183fcdf5ecb28e5d8b7ee472177abcd0793763c7b42a7200` |
| `model-lock.json` | `artifacts/verification/model-lock.json` | `57ec1389090a02e3309ca678939223f520e165516adaa76ac1ef8a458e2e818c` |
| `index-benchmark.json` | `artifacts/verification/index-benchmark-20260823T203829Z.json` | `e62581c613c5311d074858b6e96fbd66743860c6541bc5a1fdac7b2d445a64be` |
| `demo-20260824T011852Z.json` | `artifacts/verification/demo.json` | `aaac2c5ee4424fd2b3897de55a2b62089460633aabab8d28c76c04b28b472a70` |
| `resource-final.json` | `artifacts/verification/resource-final-20260824T002944Z.json` | `b539ae2779cd4bd5da41ed454807a87ab67a8da4f8dc8e0b9162be6830a21b87` |

## Preservation boundary

The recorded localhost system remains a single-machine engineering demonstration using a
synthetic corpus, CPU inference, loopback HTTP without TLS, and no standard OCR path. Production
identity, tenant isolation, backup/restore operations, malware scanning, and deployment assurance
remain outside these demonstrated claims; see [security.md](security.md).

Private `.env` values, login helpers, raw model diagnostics, browser state/traces, database records,
uploaded files, model binaries, Docker images/volumes, and machine-specific logs are excluded.
Historical measurement JSON may contain synthetic record IDs and loopback service URLs; these are
part of its provenance, not public-service endpoints.

Docker and WSL remained stopped during preservation. Their current contents were not inspected.
Whether the original volumes contain unique uploads or other state existing nowhere else could
not be confirmed. This GitHub record is intentionally **not a runtime/data backup** and does not
establish that removing those volumes would be lossless. No restoration, runtime service start,
application test suite, or fresh media playback was performed for this record.
