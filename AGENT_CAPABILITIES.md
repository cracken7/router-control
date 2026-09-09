# AGENT_CAPABILITIES.md — verified inventory (detected, not assumed)

## Runtime / host
- Windows 11, elevated shell, git-bash (MSYS) + native tools
- Python 3.11.16 (`python`), pip 26.2.1 — `requests` available
- Node v22.23.2, npm 10.9.8 — **no cargo (Rust) → Tauri not viable**
- git 2.54.0.windows.1, curl (mingw64 + system)

## Network reachability (verified)
- Host LAN IP 192.168.1.168/24, gateway 192.168.1.1
- Router @ http://192.168.1.1 → HTTP 200, `Server: ZTE web server 1.0 ZTE corp 2015`
- Product: ZXHN H168N V3.5, FW **V3.5.0_EG1T13_ET** (Egypt)

## Browser automation
- Hermes browser_exec (Chromium CDP) available — not needed: HTTP layer fully
  reproducible in Python (all flows verified via curl/requests)

## Session memory
- session_search available; no prior session found for this router project
  (first session = this one; project root `C:\Users\Admin\router-agent`)

## Skills loaded/used
- blocked-page-recovery (not needed — direct HTTP worked)
- No ZTE-specific skill existed; RE done from live firmware JS (source of truth)

## Chosen implementation stack (rationale)
- **Backend**: Python 3.11 + requests (ZteClient) — stdlib http.server for local API.
  No Rust toolchain → Tauri rejected. Electron too heavy for a LAN control app.
- **UI**: local web UI (dark, Arabic RTL) served by the local server, wrapper-ready
  for pywebview if a desktop exe is wanted later.
