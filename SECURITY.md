# Security and responsible-use policy

## Supported version

Security fixes are applied to the current `main` branch and the latest `0.1.x` source release. This
repository is a local engineering demonstration rather than a supported hosted service.

## Report a vulnerability privately

Use GitHub's [private vulnerability reporting form](https://github.com/Hasan-Al-Hussein/localguard-ai/security/advisories/new)
for suspected vulnerabilities, exposed sensitive data, or a way to bypass authentication, evidence
binding, human approval, or exactly-once task creation.

Please include the affected revision, reproducible steps, expected and observed behavior, impact,
and the smallest safe proof of concept. Do not open a public issue containing credentials, tokens,
private documents, exploit payloads, or other sensitive values. The maintainer will acknowledge a
complete report, assess its scope, and coordinate disclosure and remediation through the private
advisory.

## Security model

LocalGuard is designed for one trusted Windows computer:

- browser, API, and MCP ports bind to `127.0.0.1`;
- PostgreSQL, Redis, and Ollama remain on the private Docker network during normal runtime;
- uploaded text is untrusted evidence and cannot grant permission or approve an action;
- privileged actions require server-side RBAC and a stored, version-bound human decision;
- local secrets belong only in the ignored `.env`; `.env.example` is the public template;
- committed document fixtures and evaluation inputs are synthetic.

The complete trust boundaries, abuse cases, controls, and residual risks are documented in
[docs/security.md](docs/security.md).

## Safe use

- Run the standard stack only on loopback; it has no TLS and must not be exposed directly to another
  machine or the public internet.
- Test only documents and systems you own or are authorized to use.
- Never commit `.env`, real credentials, private documents, uploads, database volumes, or raw model
  data.
- Treat generated answers and proposals as reviewable evidence-bound outputs, not legal advice or
  autonomous authority.
- Add production identity, tenant isolation, TLS, backup, monitoring, and release-signing controls
  before adapting the project beyond its documented demonstration boundary.
