# -*- coding: utf-8 -*-
"""ACL policy write with the FULL exact body InitialPostData would build."""
import re
import sys
import time

sys.path.insert(0, ".")
from zte_client import ZteClient

LP = "Localnet_WlanAdvanced_t.lp"
EP = "Localnet_WlanAdvanced_MACFilterACLPolicy_lua.lua"

c = ZteClient()
print("login:", c.login())

def pol():
    return {i["_InstID"]: i.get("ACLPolicy") for i in c.parse_instances(c.read_endpoint(LP, EP))}

cur = pol()
print("before:", cur)
insts = c.parse_instances(c.read_endpoint(LP, EP))
tok = c.write_token(c.page(1002, LP))

parts = ["IF_ACTION=Apply", f"_InstNum={len(insts)}"]
for i, inst in enumerate(insts):
    want = "Ban" if i == 0 else inst.get("ACLPolicy", "Disabled")
    parts.append(f"_InstID_{i}={inst['_InstID']}")
    parts.append(f"ACLPolicy_{i}={want}")
parts.append(f"_sessionTOKEN={tok}")
body = "&".join(parts)
print("body:", body[:160])
import hashlib
h = {"Check": hashlib.sha256(body.encode()).hexdigest(),
     "Referer": "http://192.168.1.1/getpage.lua?pid=1002&nextpage=" + LP,
     "Content-Type": "application/x-www-form-urlencoded"}
r = c.s.post("http://192.168.1.1/common_page/" + EP, data=body, headers=h, timeout=15)
print("resp:", r.text[:180])
time.sleep(1)
after = pol()
print("after:", after)
if after.get("DEV.WIFI.AP1") == "Ban":
    parts2 = [p if not p.startswith("ACLPolicy_0") else "ACLPolicy_0=Disabled" for p in parts[:-1]]
    parts2.append(f"_sessionTOKEN={c.write_token(c.page(1002, LP))}")
    body2 = "&".join(parts2)
    h["Check"] = hashlib.sha256(body2.encode()).hexdigest()
    c.s.post("http://192.168.1.1/common_page/" + EP, data=body2, headers=h, timeout=15)
    time.sleep(1)
    print("restored:", pol())
    print("*** SOLVED ***")
