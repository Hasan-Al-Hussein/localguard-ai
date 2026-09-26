# Historical local-product capture utilities

These authored utilities were recovered from ignored `output/playwright/` on
2026-09-26. They are source-only preservation, not newly executed tests. Despite the
word `showcase` in their names, they sign into the **localhost application**, not
the public synthetic showcase.

The original identities are recorded in [the portfolio record](../../docs/portfolio-record.md).
The two JavaScript copies now write to ignored `output/archived-capture/` instead
of beside their source. The wrapper still resolves the repository two levels above
its directory and reads the reviewer password from the local ignored `.env`.
No password, browser storage state, or new screenshot is included here.

If deliberately reused, install the project's documented dependencies and a compatible
Playwright browser first. Use only a synthetic local workspace: screenshots can expose
anything visible in the signed-in account. These historical scripts assume the recorded
route names and demo reviewer; inspect them before running. The base URL must remain a
trusted loopback application, and generated files must be reviewed before publication.

```powershell
pwsh -NoProfile -File scripts/archived-capture/capture-showcase-current.ps1
pwsh -NoProfile -File scripts/archived-capture/capture-showcase-current.ps1 -Script audit-refinement-current.cjs
```

Neither command is needed to view the preserved screenshots or video.
