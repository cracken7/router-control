# -*- coding: utf-8 -*-
"""Empirically find the accepted write shape for policer Enable on QP2."""
from zte_client import ZteClient

LP = "Internet_QoS_speed_t.lp"
EP = "Internet_QoS_speed_lua.lua"

c = ZteClient()
print("LOGIN:", c.login())


def read():
    xml = c.read_endpoint(LP, EP)
    return {i["_InstID"]: i["Enable"] for i in c.parse_instances(xml)}


print("before:", read())

variants = [
    ("A: Apply+Enable+_InstID", {"Enable": "1", "_InstID": "DEV.QOS.QP2"}),
    ("B: full form fields", {"Enable": "1", "_InstID": "DEV.QOS.QP2", "Alias": "aboya",
                             "MeterType": "SimpleTokenBucket", "CommittedRate": "100000000",
                             "CommittedBurstSize": "12500000"}),
    ("C: Add hidden trio", {"Enable": "1", "_InstID": "DEV.QOS.QP2",
                            "ConformingAction": "Null", "NonConformingAction": "Drop"}),
]
for name, fields in variants:
    res = c.write(LP, EP, fields, if_action="Apply")
    ok, err = c.check_ok(res)
    after = read()
    print(f"{name:26} ok={ok} err={err} after={after}  resp={res[:120]}")
    if after.get("DEV.QOS.QP2") == "1":
        # restore
        f2 = dict(fields); f2["Enable"] = "0"
        c.write(LP, EP, f2, if_action="Apply")
        print("   restored:", read())
        break
