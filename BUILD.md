# BUILD.md

## Run (dev)
```
cd C:\Users\Admin\router-agent\app
python server.py
# open http://127.0.0.1:8766
```
Requirements: Python 3.11 + `requests` (already on this machine).
Router credentials: `scripts/config.json` (git-ignored).

## Desktop exe (pywebview) — optional next milestone
Wrap `app/server.py` in pywebview (window → http://127.0.0.1:8766), then:
```
pip install pywebview pyinstaller
pyinstaller --onefile --name RouterControl --icon NONE app/server.py
```
The local API/UI split keeps the exe trivial: the window just loads the local URL.
Never evaluate_js from background threads on WebView2 (see windows-desktop-apps skill).

## Git milestones
- 01-environment ✅
- 02-router-discovery ✅ (fixtures + menu tree + discovery report)
- 03-authentication ✅ (verified login incl. per-fetch session token)
- 04-07 QoS RE ✅ (reads all sections; writes verified where firmware allows)
- 14-ui ✅ (server + Arabic RTL dashboard)
- 15-testing ✅ (live round-trips)
- 16-packaging ⬜ (optional pywebview exe)
