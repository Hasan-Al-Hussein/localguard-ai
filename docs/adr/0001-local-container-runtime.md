# ADR 0001: CPU-only container runtime

- Status: accepted
- Date: 2026-08-23

## Context

The target Windows laptop has 16 GB RAM, integrated graphics, no CUDA device, and no host Python 3.12 or Ollama installation. The application must be free, local, reproducible, and stay below approximately 10 GB active memory and 15 GB attributable disk.

## Decision

Run the application in Linux containers through the already-installed Docker Desktop/WSL2 engine. Use one shared Python 3.12 image for FastAPI, Celery, MCP, and evaluation entrypoints; PostgreSQL and Redis use named volumes; Ollama runs in a pinned CPU-only container with a named model volume.

The measured model gate selected `qwen3:1.7b-q4_K_M` and removed the slower
`qwen2.5:1.5b-instruct-q4_K_M` comparison candidate. Embeddings use
`all-minilm:22m-l6-v2-fp16`. Exact manifest hashes and raw comparison artifacts are recorded in
`docs/runtime-lock.json`. Ollama parallelism and loaded-model count are both one, and application
provider calls also share a cross-process lock. PostgreSQL, Redis, and Ollama remain on an
internal-only network after the temporary bootstrap pull; the web, API, and MCP services are
published only on host loopback addresses.

Celery runs only in Linux because native Windows is not supported. Worker concurrency and prefetch are one. Optional observability is off by default.

## Consequences

- A new developer needs Docker Desktop plus the locked Node.js/npm major used by the frontend
  contract and test workflow, but does not need host PostgreSQL, Redis, Python 3.12, Celery, or
  Ollama.
- Named volumes avoid OneDrive database/model I/O and file-lock problems.
- First bootstrap downloads several gigabytes; later operation has no paid or cloud dependency.
- Image, volume, model, cache, and WSL memory deltas must be measured at every gate; unrelated pre-existing Docker data is never deleted.
