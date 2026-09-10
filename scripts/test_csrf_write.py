# -*- coding: utf-8 -*-
"""Exhaustive ACL policy write: try every token candidate, with csrf check."""
import re
import sys
import time

sys.path.insert(0, ".")
from zte_client import ZteClient, unescape_zte

LP = "Localnet_WlanAdvanced_t.lp"
EP = "Localnet_WlanAdvanced_MACFilterACLPolicy_lua.lua"

c = ZteClient()
print("login:", c.login())

def pol():
    return {i["_InstID"]: i.get("ACLPolicy") for i in c.parse_instances(c.read_endpoint(LP, EP))}

html = c.page(1002, LP)
dq = [unescape_zte(x) for x in re.findall(r'(?:var\s+)?_sessionTmpToken\s*=\s*"((?:\\x[0-9a-fA-F]{2})+)"', html)]
sq = [unescape_zte(x) for x in re.findall(r"_sessionTmpToken\s*=\s*'((?:\\x[0-9a-fA-F]{2})+)'", html)]
cands = list(dict.fromkeys(dq + sq))
print("before:", pol())
for tok in cands:
    chk = c.get("/common_page/template_token_check.lua?sessToken=" + tok)
    cres = re.search(r"<CHECK_RESULT>(.*?)</CHECK_RESULT>", chk)
    print(f"\ntoken={tok} csrf_check={cres.group(1) if cres else chk[:60]!r}")
    r = c.write(LP, EP, {"ACLPolicy_0": "Ban", "ACLPolicy_1": "Disabled",
                         "ACLPolicy_2": "Disabled", "ACLPolicy_3": "Disabled"},
                if_action="Apply", token=tok)
    print("  write:", c.check_ok(r))
    time.sleep(1)
    after = pol()
    print("  pol:", after)
    if after.get("DEV.WIFI.AP1") == "Ban":
        c.write(LP, EP, {"ACLPolicy_0": "Disabled", "ACLPolicy_1": "Disabled",
                         "ACLPolicy_2": "Disabled", "ACLPolicy_3": "Disabled"}, if_action="Apply")
        time.sleep(1)
        print("  restored:", pol())
        print("  *** ACL WRITE SOLVED with this token ***")
        break
