# -*- coding: utf-8 -*-
"""Simulate a phone: gate login + what the UI fetches first, timed.
Runs 6 requests concurrently like the SPA does."""
import sys, time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, ".")
import requests
from zte_client import _CFG

B = "http://127.0.0.1:8766"
s = requests.Session()

t0 = time.time()
r = s.post(B + "/api/applogin", json={"username": _CFG["username"],
                                      "password": _CFG["password"]}, timeout=90)
print(f"applogin: {r.json()}  {time.time()-t0:.1f}s")

def timed(name):
    t0 = time.time()
    paths = {
        "dashboard": "/api/dashboard", "devices": "/api/devices",
        "wifi": "/api/wifi", "lan": "/api/lanstatus", "ops": "/api/ops",
        "wan": "/api/wan",
    }
    r = s.get(B + paths[name], timeout=60)
    ok = r.json().get("ok")
    dt = time.time() - t0
    flag = "SLOW" if dt > 6 else "ok"
    print(f"  {name:10s} {dt:5.1f}s ok={ok} [{flag}]")
    return dt

for round_no in (1, 2):
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=6) as ex:
        dts = list(ex.map(timed, ["dashboard"] * 0 or ["dashboard", "devices", "wifi", "lan", "ops", "wan"]))
    print(f"ROUND {round_no}: 6 parallel fetches total {time.time()-t0:.1f}s (max single {max(dts):.1f}s)")
