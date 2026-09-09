# -*- coding: utf-8 -*-
"""Read all QoS data endpoints via GET getpage.lua?pid=1005&nextpage=<EP> —
the router's standard AJAX read path (same as UpdateCurrTime in firmware JS)."""
from zte_client import ZteClient

EPS = [
    "Internet_AdminQos_BasicCfg_lua.lua",
    "Internet_QoS_type_lua.lua",
    "Internet_AdminQos_Congestion_lua.lua",
    "Internet_QoS_speed_lua.lua",
    "Internet_QoS_shaper_lua.lua",
    "Internet_QoS_Down_Port_lua.lua",
    "Internet_QoS_IPDownList_lua.lua",
    "Internet_AdminQos_QoSStatistics_lua.lua",
]

c = ZteClient()
print("LOGIN:", c.login("user", "etis"))
import os
os.makedirs("fixtures", exist_ok=True)

for ep in EPS:
    body = c.page(1005, ep)
    fn = f"fixtures/{ep.replace('_lua.lua', '')}.xml"
    open(fn, "w", encoding="utf-8", errors="replace").write(body)
    ok404 = "404 Not Found" in body
    head = body[:260].replace("\n", " ")
    print(f"{'404!' if ok404 else 'OK  '} {ep} len={len(body)}\n     {head}\n")
