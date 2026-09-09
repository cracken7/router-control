# TESTING.md

## Live verification log (all against the real router 192.168.1.1)

### Protocol layer (scripts/)
| Test | Result |
|---|---|
| Login flow (GET page → token → SHA256 post) `user` account | ✅ LOGIN OK |
| Wrong `_sessionTOKEN` rejected ("This page has expired") | ✅ (detected & fixed by per-fetch token) |
| Session-activated GET reads (visit .lp → GET endpoint) | ✅ all 8 QoS/support endpoints |
| Un-visited endpoint returns 404 | ✅ (discovered gating behavior) |
| Write Basic QoS Enable 1→0→1 + read-back ×2 | ✅ PASS |
| Write DownLimit rule Enable 0→1→0 (QCDownlimit1 "aboya") | ✅ PASS |
| Write DownLimit global Enable+DownBandwidth off→on | ✅ PASS |
| Write Policing Enable (3 payload variants) | ⚠️ SUCC-but-no-op — firmware lock (see QOS doc) |
| Auto re-login on SessionTimeout | ✅ (implemented in client, exercised by long sessions) |

### API layer (app/server.py) — verified via curl
| Endpoint | Result |
|---|---|
| GET /api/status | ✅ {"ok": true, "router": "ZXHN H168N V3.5"} |
| GET /api/dashboard | ✅ qos_enabled, downlimit, devices_count, router_time |
| GET /api/devices | ✅ 6 devices with names/IPs/MACs |
| GET /api/qos/{basic,classification,congestion,policing,shaping,downlimit_global,downlimit_rules} | ✅ all 7 return live data |
| POST /api/qos/* (write + read-back) | ✅ |

### UI (ui/index.html)
- JS syntax validated via node (new Function compile) ✅
- Arabic RTL dark glass layout; views: dashboard / QoS (6 sub-sections) / devices ✅
- Served correctly by local server (title check) ✅
- Browser-automation screenshot pass: skipped (cloud browser has no LAN access;
  local browser drive timed out) — manual check: open http://127.0.0.1:8766

## Repro
```
cd C:\Users\Admin\router-agent\app
python server.py        # → http://127.0.0.1:8766
```
Write tests are toggle-and-restore; they leave config unchanged.
