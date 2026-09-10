# -*- coding: utf-8 -*-
"""WLAN ACL policy write — try first vs last occurrence of _sessionTmpToken."""
import sys
import time

sys.path.insert(0, ".")
from zte_client import ZteClient, unescape_zte
import re

LP = "Localnet_WlanAdvanced_t.lp"
EP = "Localnet_WlanAdvanced_MACFilterACLPolicy_lua.lua"

c = ZteClient()
print("login:", c.login())

def pol():
    return {i["_InstID"]: i.get("ACLPolicy") for i in c.parse_instances(c.read_endpoint(LP, EP))}

print("before:", pol())
html = c.page(1002, LP)
occ = re.findall(r'(?:var\s+)?_sessionTmpToken\s*=\s*"((?:\\x[0-9a-fA-F]{2})+)"', html)
first, last = unescape_zte(occ[0]), unescape_zte(occ[-1])

def write_with(tok):
    fields = {"ACLPolicy_0": "Ban", "ACLPolicy_1": "Disabled",
              "ACLPolicy_2": "Disabled", "ACLPolicy_3": "Disabled"}
    return c.write(LP, EP, fields, if_action="Apply", token=tok)

print("using FIRST token:", c.check_ok(write_with(first)))
time.sleep(1)
after_first = pol()
print("  pol:", after_first)
if after_first.get("DEV.WIFI.AP1") != "Ban":
    print("using LAST token:")
    r2 = write_with(last)
    print("  ", c.check_ok(r2))
    time.sleep(1)
    print("  pol:", pol())
# restore
c.write(LP, EP, {"ACLPolicy_0": "Disabled", "ACLPolicy_1": "Disabled",
                 "ACLPolicy_2": "Disabled", "ACLPolicy_3": "Disabled"}, if_action="Apply")
time.sleep(1)
print("final:", pol())
