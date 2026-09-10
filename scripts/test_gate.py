# -*- coding: utf-8 -*-
"""Exercise the app auth gate end-to-end (no secrets in argv)."""
import json
import sys

import requests

sys.path.insert(0, ".")
from zte_client import _CFG

B = "http://127.0.0.1:8766"

print("appstatus:", requests.get(B + "/api/appstatus", timeout=10).json())
r = requests.post(B + "/api/applogin", json={"username": _CFG["username"],
                                             "password": _CFG["password"]}, timeout=60)
print("applogin:", r.json())
d = requests.get(B + "/api/dashboard", timeout=40).json()
print("dashboard ok:", d.get("ok"), "| wan:", (d.get("wan") or {}).get("ConnStatus"))
p = requests.get(B + "/api/ping", params={"host": "8.8.8.8"}, timeout=40).json()
print("ping:", p.get("ok"), p.get("avg_ms"), "ms")
print("lan IP for phone:", requests.get(B + "/api/appstatus", timeout=10).json()["lan"])
