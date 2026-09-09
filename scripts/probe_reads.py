# -*- coding: utf-8 -*-
"""Probe read paths: known-good sntp read vs QoS endpoints; test Referer impact."""
from zte_client import ZteClient

c = ZteClient()
print("LOGIN:", c.login("user", "etis"))
s = c.s

tests = [
    ("GET", "/getpage.lua?pid=1005&nextpage=Internet_sntp_lua.lua", None),
    ("GET", "/common_page/Internet_QoS_type_lua.lua", None),
    ("GET", "/common_page/Internet_QoS_type_lua.lua", "http://192.168.1.1/getpage.lua?pid=1002&nextpage=Internet_QoS_type_t.lp"),
    ("POST", "/common_page/Internet_QoS_type_lua.lua", "http://192.168.1.1/getpage.lua?pid=1002&nextpage=Internet_QoS_type_t.lp"),
    ("GET", "/common_page/security_lua.lua", None),
]
for method, url, ref in tests:
    headers = {}
    if ref:
        headers["Referer"] = ref
    if method == "GET":
        r = s.get("http://192.168.1.1" + url, headers=headers, timeout=10)
    else:
        r = s.post("http://192.168.1.1" + url, data="IF_ACTION=Get", headers=headers, timeout=10)
    body = r.text
    tag = "404" if "404 Not Found" in body else f"{len(body)}B"
    print(f"{method:4} {tag:>7} ref={'Y' if ref else '-'} {url}\n      head: {body[:200].strip()[:160]!r}\n")
