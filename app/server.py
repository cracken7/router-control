# -*- coding: utf-8 -*-
"""Router Control — local API server for ZTE ZXHN H168N V3.5 (protocol fully
reverse-engineered + live-verified, see QOS_REVERSE_ENGINEERING.md).
Serves ui/index.html and a JSON API that talks to the real router.
Port: 8766 (8765 is used by the user's AII app)."""
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "scripts"))
from zte_client import ZteClient

ROOT = _HERE
UI_DIR = os.path.join(os.path.dirname(ROOT), "ui")
LOCK = threading.RLock()

client = ZteClient()
_cache = {}          # key -> {"t": ts, "data": ...}
CACHE_TTL = 3.0      # seconds


# ---------------------------------------------------------------- sections
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
WIFI_CONF_EP = "Localnet_WlanBasicAd_WLANSSIDConf_EncryOption_lua.lua"
WIFI_ONOFF_EP = "Localnet_WlanBasicAd_OnOff_lua.lua"
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
    hit = _cache.get(key)
    if hit and now - hit["t"] < CACHE_TTL:
        return hit["data"]
    data = fn()
    _cache[key] = {"t": now, "data": data}
    return data


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
    _cache.clear()
    fresh = _read(section)
    # The router sometimes reports FAIL yet performs the op — read-back is the truth
    return {"ok": ok and fresh["ok"], "error": err, "instances": fresh["instances"]}


# ---------------------------------------------------------------- wifi
def wifi_aps():
    def fn():
        xml = client.read_endpoint(WIFI_PAGE, WIFI_CONF_EP)
        ok, err = client.check_ok(xml)
        insts = client.parse_instances(xml) if ok else []
        aps, psks = [], {}
        for i in insts:
            if re.match(r"^DEV\.WIFI\.AP\d+$", i["_InstID"]):
                aps.append(i)
            elif ".PSK" in i["_InstID"]:
                psks[i["_InstID"]] = i
        return {"ok": ok, "error": err, "aps": aps, "psks": psks}
    return cached("wifi:aps", fn)


def wifi_radio():
    def fn():
        xml = client.read_endpoint(WIFI_PAGE, WIFI_ONOFF_EP)
        ok, err = client.check_ok(xml)
        insts = [i for i in client.parse_instances(xml) if i["_InstID"] == "DEV.WIFI.RD1"]
        return {"ok": ok, "error": err, "radio": insts[0] if insts else {}}
    return cached("wifi:radio", fn)


def api_wifi():
    out = wifi_aps()
    out["radio"] = wifi_radio()["radio"]
    return out


def api_wifi_save(ap_id, fields):
    """Edit one AP: ESSID rename, hide toggle, security, password.
    Password changes need _InstID_PSK + _PSKCONIG=Y (verified on live fw)."""
    aps = [a for a in wifi_aps()["aps"] if a["_InstID"] == ap_id]
    if not aps:
        return {"ok": False, "error": "AP not found"}
    ap = aps[0]
    body = {
        "_InstID": ap["_InstID"],
        "Enable": ap.get("Enable", "1"),
        "ESSID": fields.get("ESSID", ap.get("ESSID", "")),
        "ESSIDHideEnable": str(fields.get("ESSIDHideEnable", ap.get("ESSIDHideEnable", "0"))),
        "BeaconType": fields.get("BeaconType", ap.get("BeaconType", "WPAand11i")),
    }
    pw = fields.get("KeyPassphrase")
    if pw:  # includes changing password
        body["_InstID_PSK"] = ap["_InstID"] + ".PSK1"
        body["_PSKCONIG"] = "Y"
        body["KeyPassphrase"] = pw
    xml = client.write(WIFI_PAGE, WIFI_CONF_EP, body, if_action="Apply")
    ok, err = client.check_ok(xml)
    _cache.clear()
    fresh = [a for a in wifi_aps()["aps"] if a["_InstID"] == ap_id]
    changed = fresh and fresh[0]["ESSID"] == body["ESSID"] and \
        fresh[0]["ESSIDHideEnable"] == body["ESSIDHideEnable"]
    return {"ok": ok and bool(changed), "error": err, "ap": fresh[0] if fresh else {}}


def api_wifi_password(ap_id):
    """Read the CURRENT wifi password (firmware GetPassword action)."""
    xml = client.write(WIFI_PAGE, WIFI_CONF_EP,
                       {"_InstID_PASS": ap_id, "PASSTYPE": "PSK"}, if_action="GetPassword")
    m = re.search(r"<ParaName>KeyPassphrase</ParaName>\s*<ParaValue>(.*?)</ParaValue>", xml, re.S)
    ok, err = client.check_ok(xml)
    return {"ok": ok, "error": err, "password": m.group(1) if m else ""}


def api_wifi_radio(status):
    body = {"RadioStatus": "1" if status else "0", "_InstID": "DEV.WIFI.RD1",
            "Band": "2.4GHz", "Standard": "b,g,n", "BandWidth": "20MHz",
            "AutoChannelEnabled": "1", "Channel": "1"}
    xml = client.write(WIFI_PAGE, WIFI_ONOFF_EP, body, if_action="Apply")
    ok, err = client.check_ok(xml)
    _cache.clear()
    return {"ok": ok, "error": err, "radio": wifi_radio()["radio"]}


# ---------------------------------------------------------------- devices
def api_devices():
    def fn():
        devs = []
        for lp, ep, kind in DEV_EPS:
            xml = client.read_endpoint(lp, ep)
            for inst in client.parse_instances(xml):
                if "MACAddress" in inst:
                    devs.append({
                        "name": inst.get("HostName") or "(جهاز غير معروف)",
                        "ip": inst.get("IPAddress", ""),
                        "mac": inst.get("MACAddress", "").lower(),
                        "type": kind,
                        "ssid": inst.get("AliasName", ""),
                    })
        return {"ok": True, "devices": devs}
    return cached("devices", fn)


# ---------------------------------------------------------------- status / wan
def api_wan():
    def fn():
        xml = client.read_endpoint(WAN_PAGE, WAN_EP)
        ok, err = client.check_ok(xml)
        insts = client.parse_instances(xml) if ok else []
        dsl = client.parse_instances(client.read_endpoint(WAN_PAGE, DSL_EP))
        wan = insts[0] if insts else {}
        d = dsl[0] if dsl else {}
        return {"ok": ok, "error": err,
                "wan": {k: wan.get(k) for k in ("ConnStatus", "ConnStatus6", "UpTime", "UserName",
                                                "TransType", "WANCName", "ConnError") if k in wan},
                "dsl": {k: d.get(k) for k in ("Status", "Module_type", "CurrentProfile",
                                              "Downstream_current_rate", "Upstream_max_rate",
                                              "Downstream_noise_margin", "Downstream_attenuation",
                                              "Upstream_noise_margin", "Upstream_power",
                                              "DownCrc_errors", "UpCrc_errors", "Showtime_start") if k in d}}
    return cached("wan", fn)


def api_dashboard():
    def fn():
        out = {}
        b = api_read("basic")
        out["qos_enabled"] = b["instances"][0].get("Enable") if b["instances"] else None
        dg = api_read("downlimit_global")
        out["downlimit"] = dg["instances"][0] if dg["instances"] else {}
        d = api_devices()
        out["devices_count"] = len(d["devices"])
        w = api_wan()
        out["wan"] = w["wan"]
        out["dsl"] = {k: w["dsl"].get(k) for k in ("Status", "Downstream_current_rate", "CurrentProfile")}
        info = client.parse_instances(client.read_endpoint(INFO_PAGE, INFO_EP))
        out["device_info"] = info[0] if info else {}
        xml = client.read_endpoint("Internet_sntp_t.lp", "Internet_sntp_lua.lua")
        m = re.search(r"<ParaName>CurrentLocalTime</ParaName>\s*<ParaValue>(.*?)</ParaValue>", xml)
        out["router_time"] = m.group(1) if m else None
        out["ok"] = True
        return out
    return cached("dash", fn)


# ---------------------------------------------------------------- system
def api_lan_status():
    def fn():
        xml = client.read_endpoint("Localnet_LocalnetStatusUser_t.lp", "lanStatus_lua.lua")
        ok, err = client.check_ok(xml)
        ports = []
        for i in (client.parse_instances(xml) if ok else []):
            if "AliasName" in i:
                ports.append({"name": i["AliasName"], "status": i.get("Status", ""),
                              "speed": i.get("LinkSpeed", "?"), "duplex": i.get("LinkDuplex", ""),
                              "rx": i.get("BytesReceived", "0"), "tx": i.get("BytesSent", "0")})
        return {"ok": ok, "error": err, "ports": ports}
    return cached("lanstatus", fn)


def api_dhcp_leases():
    def fn():
        xml = client.read_endpoint("Localnet_LanMgrIpv4_t.lp", "Localnet_LanMgrIpv4_DHCPHostInfo_lua.lua")
        ok, err = client.check_ok(xml)
        leases = []
        for i in (client.parse_instances(xml) if ok else []):
            leases.append({"host": i.get("HostName") or "(غير معروف)",
                           "ip": i.get("IPAddr", ""),
                           "mac": i.get("MACAddr", "").lower(),
                           "port": i.get("PhyPortName", ""),
                           "expires": i.get("ExpiredTime", "")})
        return {"ok": ok, "error": err, "leases": leases}
    return cached("dhcpleases", fn)


def api_reboot():
    xml = client.write(SYS_PAGE, SYS_EP, {}, if_action="Restart")
    ok, err = client.check_ok(xml)
    return {"ok": ok, "error": err, "note": "الراوتر بيعمل ريستارت دلوقتي (٥ دقايق تقريباً)"}


def api_factory_reset():
    xml = client.write(SYS_PAGE, SYS_EP, {}, if_action="Restore")
    ok, err = client.check_ok(xml)
    return {"ok": ok, "error": err, "note": "باعود لإعدادات المصنع — كل الإعدادات هتتمسح"}


def api_device_info():
    def fn():
        xml = client.read_endpoint(INFO_PAGE, INFO_EP)
        ok, err = client.check_ok(xml)
        insts = client.parse_instances(xml) if ok else []
        return {"ok": ok, "error": err, "info": insts[0] if insts else {}}
    return cached("info", fn)


# ---------------------------------------------------------------- HTTP layer
ROUTES_GET = {}
ROUTES_POST = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        # CORS: allow the GitHub Pages copy of the UI to drive this local server
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
            with LOCK:
                if u.path == "/api/status":
                    ok = client.logged_in or client.login()
                    return self._send(200, {"ok": ok, "router": "ZXHN H168N V3.5"})
                if u.path == "/api/dashboard":
                    return self._send(200, api_dashboard())
                if u.path == "/api/devices":
                    return self._send(200, api_devices())
                if u.path == "/api/wifi":
                    return self._send(200, api_wifi())
                if u.path == "/api/wifi/password":
                    ap = u.query or "DEV.WIFI.AP1"
                    return self._send(200, api_wifi_password(ap))
                if u.path == "/api/wan":
                    return self._send(200, api_wan())
                if u.path == "/api/lanstatus":
                    return self._send(200, api_lan_status())
                if u.path == "/api/dhcpleases":
                    return self._send(200, api_dhcp_leases())
                if u.path == "/api/info":
                    return self._send(200, api_device_info())
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
                if u.path == "/api/system/reboot":
                    return self._send(200, api_reboot())
                if u.path == "/api/system/factory-reset":
                    return self._send(200, api_factory_reset())
            return self._send(404, {"ok": False, "error": "not found"})
        except Exception as e:
            return self._send(500, {"ok": False, "error": str(e)})


if __name__ == "__main__":
    port = 8766
    print(f"Router Control UI  ->  http://127.0.0.1:{port}")
    print("Router target      ->  http://192.168.1.1  (ZXHN H168N V3.5)")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
