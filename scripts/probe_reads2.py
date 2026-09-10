# -*- coding: utf-8 -*-
"""Hypothesis: endpoint activates after visiting its .lp page in-session.
Visit page first, then GET/POST the endpoint."""
import hashlib
import re

from zte_client import ZteClient, strip_tags

c = ZteClient()
print("LOGIN:", c.login())
s = c.s
BASE = c.base

page = c.page(1002, "Internet_QoS_type_t.lp")
print("page fetched:", len(page), "404" in page[:2000])
tok = c.write_token(page)
print("write_token:", tok)

for desc, method, data, headers in [
    ("GET after visit", "GET", None, {"Referer": BASE + "/getpage.lua?pid=1002&nextpage=Internet_QoS_type_t.lp"}),
    ("POST Get", "POST", "IF_ACTION=Get", {"Referer": BASE + "/getpage.lua?pid=1002&nextpage=Internet_QoS_type_t.lp"}),
    ("POST Get+token+Check", "POST", f"IF_ACTION=Get&_sessionTOKEN={tok}",
     {"Referer": BASE + "/getpage.lua?pid=1002&nextpage=Internet_QoS_type_t.lp"}),
]:
    h = dict(headers)
    if data is not None:
        h["Check"] = hashlib.sha256(data.encode()).hexdigest()
    url = BASE + "/common_page/Internet_QoS_type_lua.lua"
    if method == "GET":
        r = s.get(url, headers=h, timeout=10)
    else:
        r = s.post(url, data=data, headers=h, timeout=10)
    body = r.text
    stat = "404" if "404 Not Found" in body else ("400" if "400 Bad" in body else f"{len(body)}B")
    print(f"{desc:24} -> {stat}\n   {body[:220].strip()!r}\n")
