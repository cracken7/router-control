# SECURITY.md

## Secrets policy (implemented)
- Router credentials live ONLY in `scripts/config.json` (local, git-ignored).
- No credentials in source files (throwaway probes sanitized), reports, or fixtures.
- `.gitignore` blocks: config.json, page dumps (pages/), fixtures/, capture/, logs.

## Router-side security notes (from live firmware inspection)
- Login is SHA256(password+nonce) — nonce is fresh per login; fine.
- `_sessionTOKEN` + `Check: sha256(body)` header = session binding + body integrity.
  **But everything is plain HTTP on the LAN** — no TLS; any LAN listener can see cookies.
- Router web UI has no CSRF-free design (token per page render mitigates cross-site posts).
- Recommendation: keep management on LAN only; do not port-forward 80/443 of the router.
