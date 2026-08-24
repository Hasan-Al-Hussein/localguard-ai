# Resource benchmarks

This document separates measured resource evidence from container limits and planning targets.
Numbers are filled only when a retained artifact or verification log supports them. The final
full-stack measurements below come from the frozen local release run on 2026-08-24.

## Target and measurement rules

The target machine is a Windows laptop with an Intel Core i7-1255U, 16 GB installed RAM,
integrated graphics, and no CUDA device. LocalGuard should remain below approximately 10 GB active
memory and 15 GB attributable disk while processing one model request at a time.

Use these rules for every final measurement:

1. Run from the same repository revision with the locked models and containers in
   `docs/runtime-lock.json`.
2. Record the UTC timestamp, Docker and Compose versions, available host memory, free disk, model
   manifest hashes, and dataset SHA before the sample.
3. Stop other LocalGuard tests and evaluations. Record unrelated workloads rather than deleting or
   pruning them.
4. Report cold and warm operations separately. A warm query runs after one successful request with
   the selected model still loaded.
5. Keep `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`, and Celery concurrency 1.
6. Use only committed synthetic fixtures. Do not upload personal documents for benchmarking.
7. Retain raw command output under the ignored `artifacts/verification/` directory before copying
   reviewed values into this table.
8. Do not add container memory limits and host WSL working-set values together. They are different,
   potentially overlapping views of the same memory.

## Evidence already recorded

The Phase 0 and bounded model-selection artifacts support the following values:

| Measurement | Observed value | Evidence | Scope |
|---|---:|---|---|
| Host physical memory | 15.68 GB total; 4.51 GB free | `docs/verification-log.md`, Phase 0 sample | Host baseline at 02:26 UTC on 2026-08-23 |
| C: free space | 98.14 GB | `docs/verification-log.md`, Phase 0 sample | Host baseline before project build |
| Selected generation model | `qwen3:1.7b-q4_K_M` | `docs/runtime-lock.json` | CPU-only Ollama model |
| Selected-model chat gate | 3/3 cases passed | `artifacts/model-gate-qwen3-1.7b.json` | One grounded, one insufficient, one injection case |
| Selected-model warm median | 4,912.23 ms | `artifacts/model-gate-qwen3-1.7b.json` | Bounded three-case gate, not the 25-case evaluation |
| Selected-model minimum / maximum | 4,202.29 ms / 35,086.51 ms | `artifacts/model-gate-qwen3-1.7b.json` | Includes a cold first request |
| Ollama container peak | 2.008 GiB | `docs/verification-log.md` | Peak observed during the selected-model gate |
| API runner at model gate | about 47 MiB | `docs/verification-log.md` | API runner only, not the full stack |
| Embedding output and latency | 384 dimensions in 646.93 ms | `artifacts/model-gate-qwen3-1.7b.json` | One MiniLM embedding request |
| Retained model volume | 1,405,257,156 bytes | `docs/verification-log.md` | Selected generation and embedding models |
| Rejected-model warm median | 11,294.36 ms | `artifacts/model-gate-qwen2.5-1.5b.json` | Comparison model, removed after the gate |

The selected-model gate is evidence for model choice and bounded model memory. It is not a
full-stack idle or query benchmark.

## Required final table

| Required measurement | Result | Status | Final evidence source |
|---|---:|---|---|
| Full-stack idle active memory | 576.06 MiB | Measured; pass | `resource-idle-20260824T001745Z.csv`, seven healthy containers after 60 seconds unloaded |
| Peak active memory during one warm Ollama query | 3,976.33 MiB | Measured; pass | `resource-query-20260824T001446Z.csv` and `.summary.json`; grounded cited answer succeeded |
| Average real-model retrieval time | 195.19 ms | Measured | Final 25-case run, 25 observations; p95 433.40 ms |
| Average real-model generation time | 8,921.34 ms | Measured | Final 25-case run, 25 observations; p95 14,566.59 ms |
| Indexing time for all 13 synthetic fixtures | 6,730.53 ms | Measured | `index-benchmark-20260823T203829Z.json`; 13/13 ready, no duplicate/failure |
| Single demo PDF ingestion time | 727.49 ms | Measured | `demo.json` field `document.ingestion_ms` |
| Total attributable project disk | approximately 12.94 GB | Measured; pass | `resource-disk-final-20260824T004023Z.txt` and `resource-final-20260824T002944Z.json` |
| Final retained model disk | 1,405,257,156 bytes | Measured | `docs/verification-log.md` |

Container limits such as the 4 GiB Ollama cap, 768 MiB worker cap, or 512 MiB database cap are not
measurements and must not be copied into the result column.

The idle sum is the seven LocalGuard container memory values, not a sum with the overlapping host
view. At the same timestamp `vmmemWSL` reported 5,001,744,384 bytes; it is retained as host context,
not added to 576.06 MiB. The warm request completed in 23,565.25 ms with one citation and no repair
or failure. The final evaluator run completed every case, and all 20 measured model calls were
accepted on their first attempt.

Final disk accounting uses 1,256,835,703 workspace bytes, approximately 10.177 GB of required image
layers counted once, 1,502,490,134 bytes of LocalGuard volumes, 77,824 bytes of live writable
layers, and zero build-cache bytes. The fully identified 11.39 GB LocalGuard build cache was
removed after the definitive images were built and verified. One stale LocalGuard audit image and
12 unreferenced disposable audit volumes were also removed; the live PostgreSQL, Redis, upload, and
model volumes were not touched.

## Capture the environment baseline

Run this before starting the final benchmark:

```powershell
New-Item -ItemType Directory -Force .\artifacts\verification | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$baseline = ".\artifacts\verification\resource-baseline-$stamp.txt"
$revision = git rev-parse --verify HEAD 2>$null
if ($LASTEXITCODE -ne 0) { $revision = 'unborn HEAD' }

"utc=$((Get-Date).ToUniversalTime().ToString('o'))" | Set-Content $baseline
"revision=$revision" | Add-Content $baseline
"working_tree=$(if (git status --short) { 'dirty' } else { 'clean' })" | Add-Content $baseline
"dataset_sha=$((Get-FileHash .\evals\dataset\cases.jsonl -Algorithm SHA256).Hash.ToLowerInvariant())" | Add-Content $baseline
"docker=$(docker info --format '{{.ServerVersion}}')" | Add-Content $baseline
"compose=$(docker compose version --short)" | Add-Content $baseline
"host_ram_bytes=$((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory)" | Add-Content $baseline
"c_free_bytes=$((Get-PSDrive C).Free)" | Add-Content $baseline
docker system df -v | Add-Content $baseline
Get-Process | Where-Object ProcessName -Match 'docker|vmmem' |
    Select-Object ProcessName,Id,WorkingSet64,CPU | Format-Table -AutoSize |
    Out-String | Add-Content $baseline

Get-Content $baseline
```

The initial project baseline in `docs/verification-log.md` recorded zero Docker volume and build
cache bytes before LocalGuard. It also recorded unrelated pre-existing Docker images and stopped
containers. Keep those unrelated items out of the project delta.

## Measure full-stack idle memory

Start the normal profile from a stopped state and let it settle without sending a model request.
This defines idle as healthy services with no inference in progress and no intentionally warmed
model:

```powershell
pwsh -File .\scripts\stop.ps1
pwsh -File .\scripts\dev.ps1
Start-Sleep -Seconds 60
$ids = @(docker compose --profile app ps -q)
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$idle = ".\artifacts\verification\resource-idle-$stamp.csv"
"utc,name,mem_usage,mem_percent,cpu_percent" | Set-Content $idle
$utc = (Get-Date).ToUniversalTime().ToString('o')
docker stats --no-stream --format "$utc,{{.Name}},{{.MemUsage}},{{.MemPerc}},{{.CPUPerc}}" $ids |
    Add-Content $idle
Get-Content $idle
```

Also record the visible Windows Docker and WSL processes:

```powershell
Get-Process | Where-Object ProcessName -Match 'docker|vmmem' |
    Select-Object ProcessName,Id,WorkingSet64,CPU
```

Report the sum of LocalGuard container usage as the comparable idle metric. Report the host process
view beside it, not added to it. Note if another Compose project was active.

## Measure peak memory for one warm query

Use the committed `LG-POL-001` PDF and the exact question below. First ask it once to load the model,
then start the sampler in a second PowerShell window:

```powershell
$ids = @(docker compose --profile app ps -q)
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$samples = ".\artifacts\verification\resource-query-$stamp.csv"
"utc,name,mem_usage,mem_percent,cpu_percent" | Set-Content $samples

1..240 | ForEach-Object {
    $utc = (Get-Date).ToUniversalTime().ToString('o')
    docker stats --no-stream --format "$utc,{{.Name}},{{.MemUsage}},{{.MemPerc}},{{.CPUPerc}}" $ids |
        Add-Content $samples
    Start-Sleep -Milliseconds 500
}
```

While sampling, ask once through the running UI:

```text
How long does the Service Desk have to disable a vendor account after it receives an offboarding notice?
```

Record the highest LocalGuard container sum observed between request submission and the completed
answer. Keep the raw CSV. If the response fails or abstains, retain that outcome and do not label the
sample a successful query benchmark.

## Measure retrieval and generation time

Run the final 25-case local-model evaluation:

```powershell
pwsh -File .\scripts\evaluate.ps1 -Provider ollama
```

Use timings only when the retained run reports evaluator schema `1.2.0`, dataset v1.0.2 with the
final audited hashes, `evidence_derived_binding_confirmation_v2`, and
`evidence_derived_binding_selection_v2`. The failed legacy schema 1.1.0/dataset v1.0.1 run is
non-comparable and must not populate final measurements.

Extract the aggregate stage data without changing the generated report:

```powershell
$latest = Get-Content .\evals\results\latest.json -Raw | ConvertFrom-Json
$runPath = Join-Path .\evals\results (Join-Path $latest.run_id 'run.json')
$run = Get-Content $runPath -Raw | ConvertFrom-Json
$run.aggregate.latency_by_stage.retrieval | Format-List
$run.aggregate.latency_by_stage.generation | Format-List
$run.aggregate.latency_by_stage.total | Format-List
```

Use `mean_ms` for the requested averages and retain p50, p95, maximum, and sample count. Confirm that
`runtime_provider` is `ollama`; deterministic sub-millisecond generation is not a local-model speed
result.

The automated real demo provides one additional observation:

```powershell
pwsh -File .\scripts\demo.ps1 -Reset
$demo = Get-Content .\artifacts\verification\demo.json -Raw | ConvertFrom-Json
$demo.document.ingestion_ms
$demo.question.retrieval_ms
$demo.question.generation_ms
$demo.question.total_ms
```

Label those fields as one demo fixture and one question, not an average across the corpus.

## Measure synthetic fixture indexing

The required corpus interval covers all 13 files named in `fixtures/documents/manifest.json`:
8 clean sources and 5 attack variants. Use a clean benchmark-owned data set, upload the files in
manifest order through the authenticated API or UI, and measure from immediately before the first
upload request until every accepted revision reports `ready`.

Before the run, save the exact ordered input list and hashes:

```powershell
$manifest = Get-Content .\fixtures\documents\manifest.json -Raw | ConvertFrom-Json
$fixtureRows = foreach ($entry in $manifest.documents) {
    $path = Join-Path (Get-Location) $entry.path
    [pscustomobject]@{
        source_id = $entry.source_id
        path = $entry.path
        sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
$fixtureRows | Export-Csv .\artifacts\verification\index-fixtures.csv -NoTypeInformation
$fixtureRows
```

With a clean demo-reviewer data set and the normal application profile healthy, run the dedicated
loopback-only client:

```powershell
pwsh -File .\scripts\benchmark-index.ps1
```

The script verifies all 13 source hashes before login, refuses a duplicate upload or existing
output file, disables redirects, bounds individual requests and the complete run, and polls each
accepted revision until it first observes `ready`. It writes a timestamped, non-secret JSON
artifact atomically under `artifacts/verification/` with these timestamps:

- first upload request start;
- each `202 Accepted` response;
- each revision's first `ready` observation;
- the final ready timestamp;
- any failed or duplicate revision.

The reported `duration_ms` is one wall-clock interval from the first upload request to the final
ready observation. Do not substitute container startup, a single PDF's `ingestion_ms`, or total
evaluator time for this 13-fixture index measurement.

## Measure attributable disk

Capture `docker system df -v` before the first LocalGuard bootstrap and after the final retained
state. Also record workspace bytes and named-volume contents:

```powershell
$workspaceBytes = (Get-ChildItem . -Force -File -Recurse |
    Measure-Object Length -Sum).Sum
"workspace_bytes=$workspaceBytes"

docker image inspect localguard-backend:dev localguard-web:dev `
    --format '{{join .RepoTags ","}} {{.Size}}'
docker compose exec -T db du -sb /var/lib/postgresql/data
docker compose exec -T redis du -sb /data
docker compose exec -T ollama du -sb /root/.ollama
docker compose run --rm api du -sb /var/lib/localguard/uploads
docker system df -v
```

Use before/after unique-size and volume deltas. Shared Docker layers must not be counted once per
image. Report `node_modules`, frontend build output, Python images, data volumes, model volume, and
build cache separately before giving a total. Do not delete unrelated images or run a global prune
to make the number smaller.

## Final reporting template

Copy only verified numbers into the required table, then include the following context:

| Field | Value |
|---|---|
| UTC timestamp | `2026-08-24T00:40:23.4077323Z` |
| Git revision | `unborn HEAD`; all files remain uncommitted in the local project workspace |
| Docker / Compose versions | `29.7.2` / `5.3.1` |
| Generation model and manifest | `qwen3:1.7b-q4_K_M`; `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7` |
| Embedding model and manifest | `all-minilm:22m-l6-v2-fp16`; `1b226e2802dbb772b5fc32a58f103ca1804ef7501331012de126ab22f67475ef` |
| Evaluator schema / dataset | `1.2.0` / `1.0.2` |
| Structured / action modes | `evidence_derived_binding_confirmation_v2` / `evidence_derived_binding_selection_v2` |
| Dataset cases SHA-256 | `914d80632516db91cbd46700f52564677aa3a3b264d5c747b6537a8d1690392c` |
| Query state | Warm, after one successful request |
| Concurrent LocalGuard work | None |
| Failures or retries | None in the warm query or final 25-case Ollama run |

A result above the 10 GB active-memory or 15 GB disk target is a failed constraint, not a number to
round away. Keep the artifact and document the service or dependency responsible.
