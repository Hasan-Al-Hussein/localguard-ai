# Upload-ready synthetic fixtures

This directory is generated from the canonical Markdown sources in `fixtures/source-documents/` and `fixtures/attacks/` by `scripts/generate-fixtures.py`.

- `clean/` contains the eight benign PDF, DOCX, and TXT evaluation documents.
- `attacks/` contains five useful-evidence documents with deliberately embedded prompt-injection text.
- `manifest.json` records the source and generated SHA-256 hashes plus stable marker-to-page, paragraph, or line anchors.

Every file is original synthetic content for LocalGuard AI. Do not replace these fixtures with personal, university, employment, legal, or confidential material.
