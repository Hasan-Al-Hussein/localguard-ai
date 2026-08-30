# Product-demo recording harness

The harness records only the original synthetic LocalGuard corpus. Credentials are read from the
repository's ignored `.env` by a short-lived PowerShell process and never written to a screenshot,
video, trace, or source file.

From the repository root:

```powershell
pwsh -File .\demo-video\recording\capture-screenshots.ps1
pwsh -File .\demo-video\recording\record-product-flow.ps1
```

The screenshot command atomically refreshes `docs/screenshots/pipeline/` and the seven legacy
README aliases only after all twelve PNGs pass basic validation. The recording command authenticates
before recording, then saves:

- `demo-video/recording/output/raw-product-flow.webm`
- `demo-video/recording/output/timeline.json`

The output directory is intentionally ignored. The editable Remotion project consumes selected
segments and copies only publication-safe final media into `demo-video/output/`.

Both commands require the full LocalGuard app profile to be healthy and the locked synthetic demo
document/evaluation artifacts to be present. They create new synthetic question, workflow,
proposal, approval, task, outbox, and audit rows; they do not reset or delete existing data.
