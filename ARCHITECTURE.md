# ARCHITECTURE.md

## Stack decision
- **Python 3.11** backend (`scripts/zte_client.py`) — the only verified-to-work layer;
  no Rust toolchain on this machine (Tauri rejected), Electron rejected (weight).
- **Local web UI** (planned next milestone): `server.py` (stdlib http.server) serving a
  dark Arabic-RTL single-page UI; talks to ZteClient over local JSON API.
- Optional later: pywebview wrapper for a desktop .exe (matches user's other apps).

## Layers
1. **zte_client.py** — reverse-engineered router protocol:
   login (SHA256+nonce), session-token handling, session-activated GET reads,
   Check-header POST writes, XML instance parsing, auto re-login.
2. **server.py (planned)** — REST: GET/POST /api/qos/... ; holds one ZteClient.
3. **ui/ (planned)** — index.html (RTL Arabic, dark glass), pages: Dashboard,
   QoS (global/classification/congestion/policing/shaping/downlimit), Devices.
4. **tests** — against live router in read-only + one guarded write-toggle test.

## Key protocol facts (see QOS_REVERSE_ENGINEERING.md)
- Read = visit .lp page then GET /common_page/<ep> (session-activated).
- Write = POST IF_ACTION + fields + _sessionTOKEN, header Check: sha256(body).
- Write was verified live (QoS Enable toggle + read-back + restore).
