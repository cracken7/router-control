# -*- coding: utf-8 -*-
"""Router Control — local API server for ZTE ZXHN H168N V3.5.
Reverse-engineered protocol, every write live-verified (see docs/).
Serves ui/index.html + JSON API. Port 8766. Credentials: %APPDATA%\\RouterControl\\config.json
"""
import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "scripts"))
from zte_client import ZteClient

ROOT = _HERE
UI_DIR = os.path.join(os.path.dirname(ROOT), "ui")
LOCK = threading.RLock()
STATE_DIR = os.path.join(os.environ.get("APPDATA", _HERE), "RouterControl")
NAMES_FILE = os.path.join(STATE_DIR, "names.json")
OPS_FILE = os.path.join(STATE_DIR, "opslog.json")

client = ZteClient()
_cache = {}
CACHE_TTL = 2.5
TTL_OVERRIDE = {"devices": 45, "wifi": 45, "lanstatus": 45, "dashboard": 20,
                "sec:macfilter": 45, "sec:macfilter_policy": 45,
                "sec:downlimit_rules": 30, "sec:basic": 30}

# ---- web-app auth gate --------------------------------------------------
# The app no longer auto-logs into the router: a human must submit the login
# screen once per server start. Credentials are checked against config.json,
# then forwarded to the router. Phones on the LAN use the same gate.
AUTH = {"ok": False, "user": ""}
LOGIN_LOCK = threading.Lock()
EXECUTOR = ThreadPoolExecutor(max_workers=4)


def lan_ip() -> str:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.1.1", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

SECTIONS = {
    "basic": ("Internet_QoS_Basic_t.lp", "Internet_AdminQos_BasicCfg_lua.lua"),
    "classification": ("Internet_QoS_type_t.lp", "Internet_QoS_type_lua.lua"),
    "congestion": ("Internet_QoS_Congestion_t.lp", "Internet_AdminQos_Congestion_lua.lua"),
    "policing": ("Internet_QoS_speed_t.lp", "Internet_QoS_speed_lua.lua"),
    "shaping": ("Internet_QoS_shaper_t.lp", "Internet_QoS_shaper_lua.lua"),
    "downlimit_global": ("Internet_QoS_DownLimit_t.lp", "Internet_QoS_Down_Port_lua.lua"),
    "downlimit_rules": ("Internet_QoS_DownLimit_t.lp", "Internet_QoS_IPDownList_lua.lua"),
    "firewall": ("Internet_Security_Firewall_t.lp", "FirewallConf_lua.lua"),
    "urlfilter": ("Internet_Security_SecFilter_t.lp", "URLFilter_lua.lua"),
    "urlfilter_global": ("Internet_Security_SecFilter_t.lp", "SecurityGlobalCtl_lua.lua"),
    "dhcp": ("Localnet_LanMgrIpv4_t.lp", "Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua"),
    "dhcp_static": ("Localnet_LanMgrIpv4_t.lp", "Localnet_LanMgrIpv4_DHCPStaticRule_lua.lua"),
    "dhcp_leases": ("Localnet_LanMgrIpv4_t.lp", "Localnet_LanMgrIpv4_DHCPHostInfo_lua.lua"),
    "macfilter": ("Localnet_WlanAdvanced_t.lp", "Localnet_WlanAdvanced_MACFilterRule_lua.lua"),
    "macfilter_policy": ("Localnet_WlanAdvanced_t.lp", "Localnet_WlanAdvanced_MACFilterACLPolicy_lua.lua"),
}
WIFI_PAGE = "Localnet_WlanBasicUser_t.lp"
WIFI_CONF_EP = "Localnet_WlanBasicAd_WlanBasicAdConf_lua.lua"
WIFI_ONOFF_EP = "Localnet_WlanBasicAd_OnOff_lua.lua"
WIFI_SSID_EP = "Localnet_WlanBasicAd_WLANSSIDConf_EncryOption_lua.lua"
WAN_PAGE = "Internet_AdminInternetStatus_DSL_t.lp"
WAN_EP = "Internet_Internet_lua.lua?TypeUplink=1&pageType=1"
DSL_EP = "internet_dsl_interface_lua.lua"
DEV_EPS = [
    ("home_t.lp", "home_wlanDevice_lua.lua", "wifi"),
    ("home_t.lp", "home_lanDevice_lua.lua", "lan"),
    ("home_t.lp", "home_usbDevice_lua.lua", "usb"),
]
SYS_PAGE = "ManagDiag_DeviceManag_t.lp"
SYS_EP = "deviceManag_lua.lua"
INFO_PAGE = "ManagDiag_StatusManag_t.lp"
INFO_EP = "ManagReg_lua.lua"


def cached(key, fn):
    now = time.time()
    ttl = TTL_OVERRIDE.get(key, CACHE_TTL)
    hit = _cache.get(key)
    if hit and now - hit["t"] < ttl:
        return hit["data"]
    data = fn()
    _cache[key] = {"t": now, "data": data}
    return data


def _warm():
    """Prefetch the heavy views in background so first render is a cache hit."""
    for fn_ in (api_devices, api_wifi, api_lan_status, api_dashboard):
        try:
            fn_()
        except Exception:
            pass


def invalidate():
    _cache.clear()


def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def oplog(action, detail):
    """Persist a small ops log for the UI activity feed."""
    log = _load_json(OPS_FILE, [])
    log.insert(0, {"t": int(time.time()), "action": action, "detail": detail})
    _save_json(OPS_FILE, log[:50])


# ---------------------------------------------------------------- sections
def _read(section):
    lp, ep = SECTIONS[section]
    xml = client.read_endpoint(lp, ep)
    ok, err = client.check_ok(xml)
    return {"ok": ok, "error": err, "instances": client.parse_instances(xml) if ok else []}


def api_read(section):
    return cached("sec:" + section, lambda: _read(section))


def api_write(section, payload):
    lp, ep = SECTIONS[section]
    action = payload.get("action", "Apply")
    fields = dict(payload.get("fields", {}))
    inst_id = payload.get("instId")
    if inst_id is not None:
        fields.setdefault("_InstID", str(inst_id))
    xml = client.write(lp, ep, fields, if_action=action)
    ok, err = client.check_ok(xml)
    invalidate()
    fresh = _read(section)
    oplog(f"{section}:{action}", ",".join(sorted(fields)[:4]))
    return {"ok": ok and fresh["ok"], "error": err, "instances": fresh["instances"]}


# ---------------------------------------------------------------- devices
def api_devices():
    def fn():
        names = _load_json(NAMES_FILE, {})
        devs = []
        for lp, ep, kind in DEV_EPS:
            xml = client.read_endpoint(lp, ep)
            for inst in client.parse_instances(xml):
                if "MACAddress" in inst:
                    mac = inst.get("MACAddress", "").lower()
                    devs.append({
                        "name": names.get(mac) or inst.get("HostName") or "(جهاز غير معروف)",
                        "auto": inst.get("HostName") or "",
                        "custom": bool(names.get(mac)),
                        "ip": inst.get("IPAddress", ""),
                        "mac": mac,
                        "type": kind,
                        "ssid": inst.get("AliasName", ""),
                    })
        # cross-mark blocked devices
        try:
            pol = _read("macfilter_policy")
            rules = _read("macfilter")
            banned = {r.get("MACAddress", "").lower() for r in rules["instances"]}
            policy = {p["_InstID"]: p.get("ACLPolicy") for p in pol["instances"]}
            mode = policy.get("DEV.WIFI.AP1", "Disabled")
            for d in devs:
                if mode == "Ban":
                    d["blocked"] = d["mac"] in banned
                elif mode == "Allow":
                    d["blocked"] = d["mac"] not in banned  # whitelist: missing = off
                else:
                    d["blocked"] = False
                d["acl_mode"] = mode
        except Exception:
            for d in devs:
                d["blocked"] = False
        # throttle map: downlimit rule per MAC
        try:
            dls = _read("downlimit_rules")["instances"]
            tmap = {}
            for r0 in dls:
                m = r0.get("DestMAC", "").lower()
                if m:
                    tmap[m] = {"inst": r0["_InstID"], "alias": r0.get("Alias", ""),
                               "bps": r0.get("DownBandwidth", "0"),
                               "enable": r0.get("Enable", "0")}
            for d in devs:
                d["throttle"] = tmap.get(d["mac"])
        except Exception:
            for d in devs:
                d["throttle"] = None
        return {"ok": True, "devices": devs}
    return cached("devices", fn)


def api_set_name(mac, name):
    names = _load_json(NAMES_FILE, {})
    if name:
        names[mac.lower()] = name
    else:
        names.pop(mac.lower(), None)
    _save_json(NAMES_FILE, names)
    invalidate()
    oplog("rename", mac)
    return {"ok": True}


# ---------------------------------------------------------------- traffic monitor
_traffic_state = {"prev": None, "prev_t": 0.0, "series": []}


def _totals():
    tot = {"wifi_rx": 0, "wifi_tx": 0, "lan_rx": 0, "lan_tx": 0}
    xml = client.read_endpoint("Localnet_LocalnetStatusUser_t.lp", "wlanStatus_lua.lua")
    for i in client.parse_instances(xml):
        tot["wifi_rx"] += int(i.get("TotalBytesReceived") or 0)
        tot["wifi_tx"] += int(i.get("TotalBytesSent") or 0)
    xml = client.read_endpoint("Localnet_LocalnetStatusUser_t.lp", "lanStatus_lua.lua")
    for i in client.parse_instances(xml):
        tot["lan_rx"] += int(i.get("BytesReceived") or 0)
        tot["lan_tx"] += int(i.get("BytesSent") or 0)
    return tot


def api_traffic():
    now = time.time()
    t = _totals()
    out = dict(t)
    out["dsl_rate"] = 0
    try:
        dsl = client.parse_instances(client.read_endpoint(WAN_PAGE, DSL_EP))
        if dsl:
            out["dsl_rate"] = int(dsl[0].get("Downstream_current_rate") or 0) * 1000
            out["dsl_up"] = int(dsl[0].get("Upstream_current_rate") or 0) * 1000
            out["up_time"] = int(dsl[0].get("Showtime_start") or 0)
    except Exception:
        pass
    prev, pt = _traffic_state["prev"], _traffic_state["prev_t"]
    dt = max(now - pt, 0.5)
    rx_rate = tx_rate = 0
    if prev:
        rx = max(0, (t["wifi_rx"] + t["lan_rx"]) - (prev["wifi_rx"] + prev["lan_rx"]))
        tx = max(0, (t["wifi_tx"] + t["lan_tx"]) - (prev["wifi_tx"] + prev["lan_tx"]))
        rx_rate, tx_rate = rx * 8 / dt, tx * 8 / dt
    _traffic_state["prev"], _traffic_state["prev_t"] = t, now
    _traffic_state["series"].append([round(rx_rate), round(tx_rate)])
    _traffic_state["series"] = _traffic_state["series"][-60:]
    out.update({"rx_rate": int(rx_rate), "tx_rate": int(tx_rate),
                "series": _traffic_state["series"], "ok": True})
    return out


# ---------------------------------------------------------------- wifi
def wifi_aps():
    def fn():
        xml = client.read_endpoint(WIFI_PAGE, WIFI_SSID_EP)
        ok, err = client.check_ok(xml)
        insts = client.parse_instances(xml) if ok else []
        aps = [i for i in insts if re.match(r"^DEV\.WIFI\.AP\d+$", i["_InstID"])]
        return {"ok": ok, "error": err, "aps": aps}
    return cached("wifi:aps", fn)


def wifi_radio():
    def fn():
        insts = client.parse_instances(client.read_endpoint(WIFI_PAGE, WIFI_ONOFF_EP))
        radio = [i for i in insts if i["_InstID"] == "DEV.WIFI.RD1"]
        return radio[0] if radio else {}
    return cached("wifi:radio", fn)


def wifi_conf():
    def fn():
        insts = client.parse_instances(client.read_endpoint(WIFI_PAGE, WIFI_CONF_EP))
        wl = [i for i in insts if i["_InstID"] == "DEV.WIFI.RD1"]
        return wl[0] if wl else {}
    return cached("wifi:conf", fn)


def api_wifi():
    out = wifi_aps()
    out["radio"] = wifi_radio()
    out["conf"] = wifi_conf()
    return out


def api_wifi_save(ap_id, fields):
    aps = [a for a in wifi_aps()["aps"] if a["_InstID"] == ap_id]
    if not aps:
        return {"ok": False, "error": "AP not found"}
    ap = aps[0]
    body = {
        "_InstID": ap["_InstID"],
        "Enable": fields.get("Enable", ap.get("Enable", "1")),
        "ESSID": fields.get("ESSID", ap.get("ESSID", "")),
        "ESSIDHideEnable": str(fields.get("ESSIDHideEnable", ap.get("ESSIDHideEnable", "0"))),
        "BeaconType": fields.get("BeaconType", ap.get("BeaconType", "WPAand11i")),
    }
    pw = fields.get("KeyPassphrase")
    if pw:
        if len(pw) < 8:
            return {"ok": False, "error": "الباسورد أقل من 8 حروف — الراوتر سيرفض"}
        body["_InstID_PSK"] = ap["_InstID"] + ".PSK1"
        body["_PSKCONIG"] = "Y"
        body["KeyPassphrase"] = pw
    xml = client.write(WIFI_PAGE, WIFI_SSID_EP, body, if_action="Apply")
    ok, err = client.check_ok(xml)
    invalidate()
    fresh = [a for a in wifi_aps()["aps"] if a["_InstID"] == ap_id]
    changed = bool(fresh) and fresh[0]["ESSID"] == body["ESSID"]
    oplog("wifi-save", ap_id)
    return {"ok": ok and changed, "error": err, "ap": fresh[0] if fresh else {}}


def api_wifi_password(ap_id):
    xml = client.write(WIFI_PAGE, WIFI_SSID_EP,
                       {"_InstID_PASS": ap_id, "PASSTYPE": "PSK"}, if_action="GetPassword")
    m = re.search(r"<ParaName>KeyPassphrase</ParaName>\s*<ParaValue>(.*?)</ParaValue>", xml, re.S)
    ok, err = client.check_ok(xml)
    return {"ok": ok, "error": err, "password": m.group(1) if m else ""}


def api_wifi_radio(on):
    body = {"RadioStatus": "1" if on else "0", "_InstID": "DEV.WIFI.RD1",
            "Band": "2.4GHz", "Standard": "b,g,n", "BandWidth": "20MHz",
            "AutoChannelEnabled": "1", "Channel": "1"}
    xml = client.write(WIFI_PAGE, WIFI_ONOFF_EP, body, if_action="Apply")
    ok, err = client.check_ok(xml)
    invalidate()
    oplog("wifi-radio", "on" if on else "off")
    return {"ok": ok, "error": err, "radio": wifi_radio()}


def api_wifi_channel(channel, auto):
    conf = wifi_conf()
    body = {
        "_InstID": "DEV.WIFI.RD1",
        "Band": conf.get("Band", "2.4GHz"),
        "Standard": conf.get("Standard", "b,g,n"),
        "BandWidth": conf.get("BandWidth", "20MHz"),
        "AutoChannelEnabled": "1" if auto else "0",
        "Channel": str(channel),
        "CountryCode": conf.get("CountryCode", "EGI"),
    }
    xml = client.write(WIFI_PAGE, WIFI_CONF_EP, body, if_action="Apply")
    ok, err = client.check_ok(xml)
    invalidate()
    oplog("wifi-channel", f"{channel} auto={int(bool(auto))}")
    return {"ok": ok, "error": err, "conf": wifi_conf()}


# ---------------------------------------------------------------- device control
def api_block(mac, block):
    """Ban/Allow a WiFi MAC via ACL: rule list + policy per AP. Reversible."""
    rules = _read("macfilter")["instances"]
    existing = [r for r in rules if r.get("MACAddress", "").lower() == mac]

    def set_policy(target):
        """The ACL-policy endpoint requires the FULL form body (_InstNum + every
        _InstID_i/ACLPolicy_i row) — partial posts answer 404/SessionTimeout.
        (Live-verified 2026-09.)"""
        invalidate()
        insts = _read("macfilter_policy")["instances"]
        fields = {"_InstNum": len(insts)}
        for i, inst in enumerate(insts):
            cur = inst.get("ACLPolicy", "Disabled")
            fields[f"_InstID_{i}"] = inst["_InstID"]
            fields[f"ACLPolicy_{i}"] = target if i == 0 else cur
        client.write(*SECTIONS["macfilter_policy"], if_action="Apply", fields=fields)
        time.sleep(0.5)
        invalidate()
        pol = {p["_InstID"]: p.get("ACLPolicy") for p in _read("macfilter_policy")["instances"]}
        return pol.get("DEV.WIFI.AP1")

    if block:
        if not existing:
            client.write(*SECTIONS["macfilter"], if_action="Apply",
                         fields={"_InstID": "-1", "MACAddress": mac, "Interface": "DEV.WIFI.AP1"})
            time.sleep(0.5)
            invalidate()
        ok_pol = set_policy("Ban") == "Ban"
        invalidate()
        left = [r for r in _read("macfilter")["instances"] if r.get("MACAddress", "").lower() == mac]
        ok = bool(left) and ok_pol
        err = "SUCC" if ok else "لم يتأكد الحظر"
    else:
        for r0 in existing:
            client.write(*SECTIONS["macfilter"], if_action="Delete",
                         fields={"_InstID": r0["_InstID"]})
        time.sleep(0.5)
        invalidate()
        left = [r for r in _read("macfilter")["instances"] if r.get("MACAddress", "").lower() == mac]
        if not left:
            pol = {p["_InstID"]: p.get("ACLPolicy") for p in _read("macfilter_policy")["instances"]}
            if pol.get("DEV.WIFI.AP1") == "Ban":
                set_policy("Disabled")
        ok = not left
        err = "SUCC" if ok else "لم يتأكد فك الحظر"
    invalidate()
    oplog("block" if block else "unblock", mac)
    return {"ok": ok, "error": err}


PRESETS = {
    "gaming": {"label": "أونلاين — 2M", "bps": 2000000},
    "streaming": {"label": "ستريمنج — 15M", "bps": 15000000},
    "homework": {"label": "مذاكرة — 8M", "bps": 8000000},
    "free": {"label": "بدون حد (حذف القاعدة)", "bps": None},
}


def api_preset(mac, preset):
    rules = _read("downlimit_rules")["instances"]
    same = [r for r in rules if r.get("DestMAC", "").lower() == mac]
    p = PRESETS.get(preset)
    if not p:
        return {"ok": False, "error": "preset unknown"}
    if p["bps"] is None:
        for r in same:
            client.write(*SECTIONS["downlimit_rules"], if_action="Delete",
                         fields={"_InstID": r["_InstID"]})
        ok = not [r for r in _read("downlimit_rules")["instances"]
                  if r.get("DestMAC", "").lower() == mac]
        oplog("preset-free", mac)
        return {"ok": ok, "error": "SUCC" if ok else "FAIL"}
    bps = str(p["bps"])
    if same:
        r = client.write(*SECTIONS["downlimit_rules"], if_action="Apply",
                         fields={"_InstID": same[0]["_InstID"], "Alias": p["label"],
                                 "Enable": "1", "ManaType": "mac", "DestMAC": mac,
                                 "IPDest": "0.0.0.0", "IPDestMask": "0.0.0.0",
                                 "DestDevIF": same[0].get("DestDevIF", "DEV.BRIDGING.BR1.BRPORT2"),
                                 "DownBandwidth": bps})
    else:
        r = client.write(*SECTIONS["downlimit_rules"], if_action="Apply",
                         fields={"_InstID": "-1", "Alias": p["label"], "Enable": "1",
                                 "ManaType": "mac", "DestMAC": mac, "IPDest": "0.0.0.0",
                                 "IPDestMask": "0.0.0.0",
                                 "DestDevIF": "DEV.BRIDGING.BR1.BRPORT2",
                                 "DownBandwidth": bps})
    ok = client.check_ok(r)[0]
    invalidate()
    oplog("preset:" + preset, mac)
    return {"ok": ok, "error": client.check_ok(r)[1]}


# ---------------------------------------------------------------- backup / restore
BACKUP_SECTIONS = ["basic", "classification", "downlimit_global", "downlimit_rules",
                   "policing", "firewall", "urlfilter", "urlfilter_global", "macfilter"]


def api_backup():
    data = {"meta": {"app": "RouterControl", "t": int(time.time())}}
    for s in BACKUP_SECTIONS:
        try:
            data[s] = _read(s)["instances"]
        except Exception:
            data[s] = None
    try:
        data["wifi"] = wifi_aps()["aps"]
    except Exception:
        data["wifi"] = None
    data["names"] = _load_json(NAMES_FILE, {})
    return {"ok": True, "backup": data}


def api_restore(backup, apply_it):
    """Preview diff; when apply_it, re-create downlimit rules, urlfilter rules,
    QoS classification and global toggles. MAC rules replaced wholesale."""
    plan = []
    if backup.get("downlimit_rules"):
        cur = _read("downlimit_rules")["instances"]
        cur_ids = {r.get("Alias") for r in cur}
        for rule in backup["downlimit_rules"]:
            if rule.get("Alias") in cur_ids:
                continue
            plan.append(("downlimit", {k: rule.get(k) for k in
                        ("Alias", "Enable", "ManaType", "DestMAC", "DestDevIF",
                         "DownBandwidth", "IPDest", "IPDestMask") if k in rule}))
    if backup.get("urlfilter"):
        cur = _read("urlfilter")["instances"]
        have = {r.get("Url") for r in cur}
        for u in backup["urlfilter"]:
            if u.get("Url") in have:
                continue
            plan.append(("urlfilter", {"Name": u.get("Alias") or "restored", "Url": u.get("Url")}))
    if not apply_it:
        return {"ok": True, "plan": plan}
    done = 0
    for kind, fields in plan:
        if kind == "downlimit":
            fields.setdefault("_InstID", "-1")
            r = client.write(*SECTIONS["downlimit_rules"], if_action="Apply", fields=fields)
        else:
            r = client.write(*SECTIONS["urlfilter"], if_action="Apply",
                             fields={"_InstID": "-1", **fields})
        if client.check_ok(r)[0]:
            done += 1
    invalidate()
    oplog("restore", f"{done}/{len(plan)}")
    return {"ok": True, "restored": done, "planned": len(plan)}


# ---------------------------------------------------------------- wan / system
def api_wan():
    def fn():
        insts = client.parse_instances(client.read_endpoint(WAN_PAGE, WAN_EP))
        wan = insts[0] if insts else {}
        dsl = client.parse_instances(client.read_endpoint(WAN_PAGE, DSL_EP))
        d = dsl[0] if dsl else {}
        return {"ok": True,
                "wan": {k: wan.get(k) for k in ("ConnStatus", "ConnStatus6", "UpTime", "UserName",
                                                "TransType", "ConnError", "IPAddress", "DNS1") if k in wan},
                "dsl": {k: d.get(k) for k in ("Status", "Module_type", "CurrentProfile",
                                              "Downstream_current_rate", "Upstream_current_rate",
                                              "Downstream_max_rate", "Downstream_noise_margin",
                                              "Downstream_attenuation", "Upstream_noise_margin",
                                              "DownCrc_errors", "UpCrc_errors", "Showtime_start",
                                              "Link_retrain") if k in d}}
    return cached("wan", fn)


def api_dashboard():
    def fn():
        out = {"ok": True}
        f_b = EXECUTOR.submit(api_read, "basic")
        f_dg = EXECUTOR.submit(api_read, "downlimit_global")
        f_dv = EXECUTOR.submit(api_devices)
        f_w = EXECUTOR.submit(api_wan)
        f_i = EXECUTOR.submit(client.read_endpoint, INFO_PAGE, INFO_EP)
        b = f_b.result()
        out["qos_enabled"] = b["instances"][0].get("Enable") if b["instances"] else None
        dg = f_dg.result()
        out["downlimit"] = dg["instances"][0] if dg["instances"] else {}
        try:
            out["devices_count"] = len(f_dv.result(timeout=20)["devices"])
        except Exception:
            out["devices_count"] = 0
        w = f_w.result()
        out["wan"], out["dsl"] = w["wan"], w["dsl"]
        info = client.parse_instances(f_i.result())
        out["device_info"] = info[0] if info else {}
        tr = _traffic_state["series"]
        out["net"] = tr[-1] if tr else [0, 0]
        return out
    return cached("dash", fn)


def api_lan_status():
    def fn():
        xml = client.read_endpoint("Localnet_LocalnetStatusUser_t.lp", "lanStatus_lua.lua")
        ports = []
        for i in client.parse_instances(xml):
            if "AliasName" in i:
                ports.append({"name": i["AliasName"], "status": i.get("Status", ""),
                              "speed": i.get("LinkSpeed", "?"), "duplex": i.get("LinkDuplex", ""),
                              "rx": i.get("BytesReceived", "0"), "tx": i.get("BytesSent", "0")})
        return {"ok": True, "ports": ports}
    return cached("lanstatus", fn)


def api_dhcp_leases():
    def fn():
        xml = client.read_endpoint("Localnet_LanMgrIpv4_t.lp", "Localnet_LanMgrIpv4_DHCPHostInfo_lua.lua")
        names = _load_json(NAMES_FILE, {})
        leases = []
        for i in client.parse_instances(xml):
            mac = i.get("MACAddr", "").lower()
            leases.append({"host": names.get(mac) or i.get("HostName") or "(غير معروف)",
                           "ip": i.get("IPAddr", ""), "mac": mac,
                           "port": i.get("PhyPortName", ""), "expires": i.get("ExpiredTime", "")})
        return {"ok": True, "leases": leases}
    return cached("dhcpleases", fn)


def api_reboot():
    xml = client.write(SYS_PAGE, SYS_EP, {}, if_action="Restart")
    ok, err = client.check_ok(xml)
    oplog("reboot", "")
    return {"ok": ok, "error": err}


def api_wan_ctrl(on):
    """Disconnect / reconnect the PPPoE WAN link (live router control).
    Firmware action names: PPPCONNECT / PPPDISCONNECT (page JS line ~6817)."""
    act = "PPPCONNECT" if on else "PPPDISCONNECT"
    xml = client.write(WAN_PAGE, WAN_EP, {}, if_action=act)
    ok, err = client.check_ok(xml)
    invalidate()
    oplog("wan-" + act.lower(), "")
    return {"ok": ok, "error": err, "note": "اتصل" if on else "انقطع النت مؤقتاً"}


def api_ping(host, count=4):
    import subprocess
    host = re.sub(r"[^a-zA-Z0-9.\-:]", "", host)[:64]
    if not host:
        return {"ok": False, "error": "host invalid"}
    param = "-n" if os.name == "nt" else "-c"
    try:
        r = subprocess.run(["ping", param, str(count), host],
                           capture_output=True, text=True, timeout=count * 3 + 10)
        out = (r.stdout or "") + (r.stderr or "")
        ms = [int(x) for x in re.findall(r"time[=<](\d+)ms", out)]
        got = "TTL=" in out or "64 bytes" in out
        return {"ok": got, "host": host, "avg_ms": round(sum(ms)/len(ms), 1) if ms else None,
                "raw": out.strip()[:400]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def api_speedtest():
    """Download a test file via the router WAN and report real throughput."""
    import urllib.request
    urls = ["https://speed.cloudflare.com/__down?bytes=10000000",
            "http://speedtest.tele2.net/10MB.zip"]
    for url in urls:
        try:
            t0 = time.time()
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            n = 0
            with urllib.request.urlopen(req, timeout=25) as resp:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    n += len(chunk)
                    if time.time() - t0 > 15:
                        break
            dt = time.time() - t0
            if n > 1e5 and dt > 0.2:
                bps = n * 8 / dt
                oplog("speedtest", f"{int(bps/1e6)} Mbps")
                return {"ok": True, "mbps": round(bps / 1e6, 1), "bytes": n,
                        "seconds": round(dt, 1), "server": "cloudflare"}
        except Exception:
            continue
    return {"ok": False, "error": "مفيش سيرفر سرعة وصلناه — اختبرنت"}



def api_factory_reset():
    xml = client.write(SYS_PAGE, SYS_EP, {}, if_action="Restore")
    ok, err = client.check_ok(xml)
    return {"ok": ok, "error": err}


def api_device_info():
    def fn():
        insts = client.parse_instances(client.read_endpoint(INFO_PAGE, INFO_EP))
        return {"ok": True, "info": insts[0] if insts else {}}
    return cached("info", fn)


def api_ops():
    return {"ok": True, "log": _load_json(OPS_FILE, [])}


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _json_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path in ("/", "/index.html"):
                with open(os.path.join(UI_DIR, "index.html"), "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            if u.path == "/api/appstatus":
                peer = self.client_address[0]
                body = {"auth": AUTH["ok"], "user": AUTH["user"],
                        "router": "ZXHN H168N V3.5",
                        "lan": lan_ip(), "port": 8766}
                # prefill creds ONLY for the local machine (phone gets username only)
                if peer in ("127.0.0.1", "::1"):
                    body["user"] = body["user"] or client.username
                    body["pass"] = client.password
                return self._send(200, body)
            if not AUTH["ok"]:
                return self._send(401, {"ok": False, "error": "auth_required"})
            if u.path == "/api/login":
                with LOGIN_LOCK:
                    blocked = time.time() < getattr(client, "_login_blocked_until", 0)
                    if blocked and not client.logged_in:
                        return self._send(200, {"ok": False, "blocked": True})
                    ok = client.ensure_login()
                    return self._send(200, {"ok": ok, "router": "ZXHN H168N V3.5"})
            # Heavy GETs run concurrently: requests.Session is thread-safe and
            # the TTL cache collapses identical fan-out. Serializing them under
            # one global lock is what made phones crawl / time out.
            q = parse_qs(u.query)
            if u.path == "/api/status":
                return self._send(200, {"ok": bool(client.logged_in), "router": "ZXHN H168N V3.5"})
            if u.path == "/api/dashboard":
                return self._send(200, api_dashboard())
            if u.path == "/api/devices":
                return self._send(200, api_devices())
            if u.path == "/api/traffic":
                return self._send(200, api_traffic())
            if u.path == "/api/wifi":
                return self._send(200, api_wifi())
            if u.path == "/api/wifi/password":
                return self._send(200, api_wifi_password((q.get("ap") or ["DEV.WIFI.AP1"])[0]))
            if u.path == "/api/wan":
                return self._send(200, api_wan())
            if u.path == "/api/lanstatus":
                return self._send(200, api_lan_status())
            if u.path == "/api/ping":
                return self._send(200, api_ping((parse_qs(u.query).get("host") or [""])[0]))
            if u.path == "/api/speedtest":
                return self._send(200, api_speedtest())
            if u.path == "/api/dhcpleases":
                return self._send(200, api_dhcp_leases())
            if u.path == "/api/info":
                return self._send(200, api_device_info())
            if u.path == "/api/backup":
                return self._send(200, api_backup())
            if u.path == "/api/ops":
                return self._send(200, api_ops())
            if u.path.startswith("/api/qos/"):
                sec = u.path.rsplit("/", 1)[-1]
                if sec not in SECTIONS:
                    return self._send(404, {"ok": False, "error": "unknown section"})
                return self._send(200, api_read(sec))
            return self._send(404, {"ok": False, "error": "not found"})
        except Exception as e:
            return self._send(500, {"ok": False, "error": str(e)})

    def do_POST(self):
        u = urlparse(self.path)
        try:
            payload = self._json_body()
            if u.path == "/api/applogin":
                # validate against stored router credentials, then login ONCE
                user = str(payload.get("username", "")).strip()
                pwd = str(payload.get("password", ""))
                if not (user and pwd):
                    return self._send(200, {"ok": False, "error": "اكتب اليوزر والباسورد"})
                if user != client.username or pwd != client.password:
                    return self._send(200, {"ok": False, "error": "يوزر أو باسورد غلط", "wrong": True})
                with LOGIN_LOCK:
                    blocked = time.time() < getattr(client, "_login_blocked_until", 0)
                    if blocked and not client.logged_in:
                        left = int(getattr(client, "_login_blocked_until", 0) - time.time())
                        return self._send(200, {"ok": False,
                                                "error": f"الراوتر بيبرد لسه — استنى {left} ثانية"})
                    if not client.ensure_login():
                        return self._send(200, {"ok": False, "error": "الراوتر رفض الدخول — جرّب بعد شوية"})
                    AUTH["ok"] = True
                    AUTH["user"] = user
                    threading.Thread(target=_warm, daemon=True).start()
                    return self._send(200, {"ok": True})
            if not AUTH["ok"]:
                return self._send(401, {"ok": False, "error": "auth_required"})
            with LOCK:
                if u.path.startswith("/api/qos/"):
                    sec = u.path.rsplit("/", 1)[-1]
                    if sec not in SECTIONS:
                        return self._send(404, {"ok": False, "error": "unknown section"})
                    return self._send(200, api_write(sec, payload))
                if u.path == "/api/wifi/save":
                    return self._send(200, api_wifi_save(payload.get("apId"), payload.get("fields", {})))
                if u.path == "/api/wifi/radio":
                    return self._send(200, api_wifi_radio(bool(payload.get("on"))))
                if u.path == "/api/wifi/channel":
                    return self._send(200, api_wifi_channel(payload.get("channel", 1), payload.get("auto", True)))
                if u.path == "/api/devices/name":
                    return self._send(200, api_set_name(payload.get("mac", ""), payload.get("name", "")))
                if u.path == "/api/devices/block":
                    return self._send(200, api_block(payload.get("mac", "").lower(), bool(payload.get("block"))))
                if u.path == "/api/devices/preset":
                    return self._send(200, api_preset(payload.get("mac", "").lower(), payload.get("preset")))
                if u.path == "/api/restore":
                    return self._send(200, api_restore(payload.get("backup", {}), bool(payload.get("apply"))))
                if u.path == "/api/system/reboot":
                    return self._send(200, api_reboot())
                if u.path == "/api/wan/ctrl":
                    return self._send(200, api_wan_ctrl(bool(payload.get("on"))))
                if u.path == "/api/system/factory-reset":
                    return self._send(200, api_factory_reset())
            return self._send(404, {"ok": False, "error": "not found"})
        except Exception as e:
            return self._send(500, {"ok": False, "error": str(e)})


if __name__ == "__main__":
    port = 8766
    print(f"Router Control UI  ->  http://127.0.0.1:{port}")
    print(f"From your phone    ->  http://{lan_ip()}:{port}  (same wifi)")
    print("Router target      ->  http://192.168.1.1  (ZXHN H168N V3.5)")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()