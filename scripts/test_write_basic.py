# -*- coding: utf-8 -*-
"""SAFE write test: toggle global QoS Enable 1->0->1 with read-back verification
at each step. Everything else stays read-only."""
import sys

sys.path.insert(0, ".")
from zte_client import ZteClient

LP = "Internet_QoS_Basic_t.lp"
EP = "Internet_AdminQos_BasicCfg_lua.lua"

c = ZteClient()
print("LOGIN:", c.login())

xml = c.read_endpoint(LP, EP)
inst = c.parse_instances(xml)[0]
orig = inst["Enable"]
print("current Enable =", orig)

flipped = "0" if orig == "1" else "1"
print(f"--> writing Enable={flipped} ...")
res = c.write(LP, EP, {"Enable": flipped}, if_action="Apply")
ok, err = c.check_ok(res)
print("write resp:", res[:300], "| ok:", ok, "err:", err)

xml2 = c.read_endpoint(LP, EP)
now = c.parse_instances(xml2)[0]["Enable"]
print("read-back Enable =", now, "| MATCH:", now == flipped)

print("--> restoring Enable=" + orig)
res2 = c.write(LP, EP, {"Enable": orig}, if_action="Apply")
ok2, err2 = c.check_ok(res2)
xml3 = c.read_endpoint(LP, EP)
final = c.parse_instances(xml3)[0]["Enable"]
print("final Enable =", final, "| RESTORED:", final == orig)
print("RESULT:", "PASS" if (now == flipped and final == orig) else "FAIL")
c.logoff()
