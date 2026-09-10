# -*- coding: utf-8 -*-
"""Pattern confirmed: visit .lp page (session-activates endpoint) -> GET endpoint.
Fetch ALL QoS + supporting endpoints and save XML fixtures."""
import os

from zte_client import ZteClient

QOS_PAGES = {
    "Internet_QoS_Basic_t.lp": "Internet_AdminQos_BasicCfg_lua.lua",
    "Internet_QoS_type_t.lp": "Internet_QoS_type_lua.lua",
    "Internet_QoS_Congestion_t.lp": "Internet_AdminQos_Congestion_lua.lua",
    "Internet_QoS_speed_t.lp": "Internet_QoS_speed_lua.lua",
    "Internet_QoS_shaper_t.lp": "Internet_QoS_shaper_lua.lua",
    "Internet_QoS_DownLimit_t.lp": ["Internet_QoS_Down_Port_lua.lua", "Internet_QoS_IPDownList_lua.lua"],
}

EXTRA_EPS = [
    ("home_t.lp", "home_lanDevice_lua.lua"),
    ("home_t.lp", "home_wlanDevice_lua.lua"),
    ("home_t.lp", "home_usbDevice_lua.lua"),
    ("Localnet_LocalnetStatusUser_t.lp", "Localnet_LanMgrIpv4_lua.lua"),
    ("Internet_sntp_t.lp", "Internet_sntp_lua.lua"),
]

c = ZteClient()
print("LOGIN:", c.login())
os.makedirs("fixtures", exist_ok=True)


def visit_then_get(lp, ep):
    c.page(1002, lp)
    body = c.get("/common_page/" + ep)
    return body


jobs = []
for lp, eps in QOS_PAGES.items():
    if isinstance(eps, str):
        eps = [eps]
    for ep in eps:
        jobs.append((lp, ep))
for lp, ep in EXTRA_EPS:
    jobs.append((lp, ep))

for lp, ep in jobs:
    try:
        body = visit_then_get(lp, ep)
    except Exception as e:
        print(f"ERR {ep}: {e}")
        continue
    name = ep.replace("_lua.lua", "")
    ok = "ajax_response_xml_root" in body
    fn = f"fixtures/{name}.xml"
    open(fn, "w", encoding="utf-8", errors="replace").write(body)
    print(f"{'OK ' if ok else '404'} {lp:42} -> {ep:45} {len(body)}B")
