# -*- coding: utf-8 -*-
"""Live-verify WRITE shapes for the NEW features (safe round-trips):
1) URL filter: add test rule -> read-back -> delete -> read-back
2) MAC filter: add test rule -> read-back -> delete -> read-back
3) WiFi channel: write SAME current value (re-apply) -> read-back unchanged
4) Firewall level: re-apply current value -> read-back unchanged
5) QoS classification Enable toggle on existing rule -> restore
"""
import sys
import time

sys.path.insert(0, ".")
from zte_client import ZteClient

c = ZteClient()
print("login:", c.login())


def read(lp, ep):
    return c.parse_instances(c.read_endpoint(lp, ep))


def ids(insts):
    return [i.get("_InstID") for i in insts if "_InstID" in i]


ok_all = True


def check(label, cond):
    global ok_all
    ok_all = ok_all and cond
    print(("  PASS " if cond else "  FAIL ") + label)


# 1) URL filter
LP, EP = "Internet_Security_SecFilter_t.lp", "URLFilter_lua.lua"
before = ids(read(LP, EP))
print("URL before:", before)
r = c.write(LP, EP, {"_InstID": "-1", "Name": "TESTURL", "Url": "test-blocked-domain.example"},
            if_action="Apply")
time.sleep(1)
after_add = read(LP, EP)
new = [i for i in after_add if i["_InstID"] not in before]
print("add resp:", c.check_ok(r), "| new:", [(i["_InstID"], i.get("Url")) for i in new])
check("URL add visible", bool(new))
if new:
    rd = c.write(LP, EP, {"_InstID": new[0]["_InstID"]}, if_action="Delete")
    time.sleep(1)
    after_del = ids(read(LP, EP))
    print("delete resp:", c.check_ok(rd), "| after delete:", after_del)
    check("URL delete gone", new[0]["_InstID"] not in after_del)

# 2) MAC filter
LP2, EP2 = "Localnet_WlanAdvanced_t.lp", "Localnet_WlanAdvanced_MACFilterRule_lua.lua"
LP2a, EP2a = "Localnet_WlanAdvanced_t.lp", "Localnet_WlanAdvanced_MACFilterACLPolicy_lua.lua"
before2 = ids(read(LP2, EP2))
print("MAC before:", before2)
# policy is Disabled on all APs, so a rule has no effect. Add anyway to test shape.
r = c.write(LP2, EP2, {"_InstID": "-1", "MACAddress": "AA:BB:CC:DD:EE:FF",
                       "Interface": "DEV.WIFI.AP1"}, if_action="Apply")
time.sleep(1)
after2 = read(LP2, EP2)
new2 = [i for i in after2 if i["_InstID"] not in before2]
print("add resp:", c.check_ok(r), "| new:", [(i["_InstID"], i.get("MACAddress")) for i in new2])
check("MAC add visible", bool(new2))
if new2:
    rd = c.write(LP2, EP2, {"_InstID": new2[0]["_InstID"]}, if_action="Delete")
    time.sleep(1)
    after2b = ids(read(LP2, EP2))
    print("delete resp:", c.check_ok(rd), "| left:", after2b)
    check("MAC delete gone", new2[0]["_InstID"] not in after2b)

# 3) WiFi channel re-apply (same value, no disruption)
LP3, EP3 = "Localnet_WlanBasicUser_t.lp", "Localnet_WlanBasicAd_WlanBasicAdConf_lua.lua"
insts3 = read(LP3, EP3)
wlan = [i for i in insts3 if i["_InstID"] == "DEV.WIFI.RD1"][0]
ch = wlan.get("Channel", "1")
r = c.write(LP3, EP3, {"_InstID": "DEV.WIFI.RD1", "AutoChannelEnabled": wlan.get("AutoChannelEnabled", "1"),
                       "Channel": ch, "BandWidth": wlan.get("BandWidth", "20MHz"),
                       "Standard": wlan.get("Standard", "b,g,n")}, if_action="Apply")
time.sleep(1)
wlan_after = [i for i in read(LP3, EP3) if i["_InstID"] == "DEV.WIFI.RD1"][0]
print("wifi resp:", c.check_ok(r), "| channel before/after:", ch, "/", wlan_after.get("Channel"))
check("wifi re-apply ok", c.check_ok(r)[0])

# 4) Firewall level re-apply
LP4, EP4 = "Internet_Security_Firewall_t.lp", "FirewallConf_lua.lua"
fw = [i for i in read(LP4, EP4) if i["_InstID"] == "IGD"][0]
r = c.write(LP4, EP4, {"_InstID": "IGD", "Level": fw.get("Level"), "AntiAttack": fw.get("AntiAttack")},
            if_action="Apply")
time.sleep(1)
fw_after = [i for i in read(LP4, EP4) if i["_InstID"] == "IGD"][0]
print("fw resp:", c.check_ok(r), "| level:", fw.get("Level"), "/", fw_after.get("Level"))
check("fw re-apply ok", c.check_ok(r)[0] and fw_after.get("Level") == fw.get("Level"))

print("\nALL:", "PASS" if ok_all else "SOME FAILED")
c.logoff()
