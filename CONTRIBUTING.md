# Contributing to LocalGuard AI

LocalGuard AI is a local-first engineering portfolio project. Contributions should preserve its evidence, privacy, approval, and resource boundaries rather than weakening them for convenience.

## Development setup

1. Use Windows PowerShell 7 and Docker Desktop with the Linux engine.
2. Run `pwsh -File scripts/bootstrap.ps1 -SkipModelPull` for deterministic development, or omit `-SkipModelPull` when validating the real local model.
3. Start the application with `pwsh -File scripts/dev.ps1`.
4. Run `pwsh -File scripts/test.ps1 -Suite all` before requesting review.
5. Run `pwsh -File scripts/evaluate.ps1 -Provider fake` for CI-parity evaluation. Real-model claims require a separate `-Provider ollama` run.

Project-local configuration belongs in the ignored `.env` file. Never commit passwords, tokens, personal documents, private datasets, or generated uploads.

## Change expectations

- Keep API, agent orchestration, model providers, persistence, and UI concerns separated.
- Preserve strict schemas and permission checks at application boundaries.
- Treat retrieved document text as untrusted data, never as instructions.
- Keep privileged operations behind the durable reviewer approval gate.
- Add focused tests for changed behavior and regression tests for every security fix.
- Update migrations, generated contracts, evaluation cases, and documentation together when their shared contract changes.
- Report measured failures honestly. Do not hand-edit generated evaluation or benchmark results to improve them.

Synthetic fixture changes must retain `SYNTHETIC_NOTICE`, stable marker IDs, committed hashes, and the exact 25-case category contract. Regenerate upload-ready files with `python scripts/generate-fixtures.py`, then validate them with `python scripts/validate-fixtures.py` and visually review every rendered PDF/DOCX page.

## Pull-request checklist

- [ ] Formatting, linting, typing, unit, integration, and browser checks pass.
- [ ] Migration upgrade/downgrade and contract-drift checks pass when applicable.
- [ ] No secret, private document, or external paid-service dependency was introduced.
- [ ] Approval, RBAC, citation, and audit invariants remain covered.
- [ ] Resource usage remains compatible with CPU-only operation and the documented RAM/disk limits.
- [ ] User-facing behavior and limitations are reflected in the README or `docs/`.

This software is an engineering demonstration, not legal advice or a production compliance decision system.
