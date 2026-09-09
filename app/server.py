# -*- coding: utf-8 -*-
"""Router Control — local API server for ZTE ZXHN H168N V3.5 (verified protocol).
Serves ui/index.html and a JSON API that talks to the real router.
Port: 8766 (8765 is used by the user's AII app)."""
import json
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "scripts"))
from zte_client import ZteClient

ROOT = _HERE
UI_DIR = os.path.join(os.path.dirname(ROOT), "ui")
LOCK = threading.Lock()

client = ZteClient()

SECTIONS = {
    "basic": ("Internet_QoS_Basic_t.lp", "Internet_AdminQos_BasicCfg_lua.lua"),
    "classification": ("Internet_QoS_type_t.lp", "Internet_QoS_type_lua.lua"),
    "congestion": ("Internet_QoS_Congestion_t.lp", "Internet_AdminQos_Congestion_lua.lua"),
    "policing": ("Internet_QoS_speed_t.lp", "Internet_QoS_speed_lua.lua"),
    "shaping": ("Internet_QoS_shaper_t.lp", "Internet_QoS_shaper_lua.lua"),
    "downlimit_global": ("Internet_QoS_DownLimit_t.lp", "Internet_QoS_Down_Port_lua.lua"),
    "downlimit_rules": ("Internet_QoS_DownLimit_t.lp", "Internet_QoS_IPDownList_lua.lua"),
}

DEV_SOURCES = [
    ("home_t.lp", "home_wlanDevice_lua.lua", "wifi"),
    ("home_t.lp", "home_lanDevice_lua.lua", "lan"),
    ("home_t.lp", "home_usbDevice_lua.lua", "usb"),
]


def api_read(section):
    lp, ep = SECTIONS[section]
    xml = client.read_endpoint(lp, ep)
    ok, err = client.check_ok(xml)
    insts = client.parse_instances(xml) if ok else []
    return {"ok": ok, "error": err, "instances": insts}


def api_write(section, payload):
    lp, ep = SECTIONS[section]
    action = payload.get("action", "Apply")
    fields = dict(payload.get("fields", {}))
    inst_id = payload.get("instId")
    if inst_id is not None:
        fields["_InstID"] = str(inst_id)
    xml = client.write(lp, ep, fields, if_action=action)
    ok, err = client.check_ok(xml)
    # read-back: fresh state after write
    fresh = api_read(section) if ok else {"instances": []}
    return {"ok": ok, "error": err, "instances": fresh.get("instances", [])}


def api_devices():
    devs = []
    for lp, ep, kind in DEV_SOURCES:
        xml = client.read_endpoint(lp, ep)
        for inst in client.parse_instances(xml):
            if "MACAddress" in inst:
                devs.append({
                    "name": inst.get("HostName") or "(جهاز غير معروف)",
                    "ip": inst.get("IPAddress", ""),
                    "mac": inst.get("MACAddress", ""),
                    "type": kind,
                    "ssid": inst.get("AliasName", ""),
                })
    return {"ok": True, "devices": devs}


def api_dashboard():
    out = {}
    try:
        b = api_read("basic")
        out["qos_enabled"] = b["instances"][0].get("Enable") if b["instances"] else None
        dg = api_read("downlimit_global")
        out["downlimit"] = dg["instances"][0] if dg["instances"] else {}
        d = api_devices()
        out["devices_count"] = len(d["devices"])
        xml = client.read_endpoint("Internet_sntp_t.lp", "Internet_sntp_lua.lua")
        m = re.search(r"<ParaName>CurrentLocalTime</ParaName>\s*<ParaValue>(.*?)</ParaValue>", xml)
        out["router_time"] = m.group(1) if m else None
        out["ok"] = True
    except Exception as e:
        out["ok"] = False
        out["error"] = str(e)
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep console clean

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(
            body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path in ("/", "/index.html"):
                p = os.path.join(UI_DIR, "index.html")
                with open(p, "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            with LOCK:
                if u.path == "/api/status":
                    ok = client.logged_in or client.login()
                    return self._send(200, {"ok": ok, "router": "ZXHN H168N V3.5"})
                if u.path == "/api/dashboard":
                    return self._send(200, api_dashboard())
                if u.path == "/api/devices":
                    return self._send(200, api_devices())
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
            return self._send(404, {"ok": False, "error": "not found"})
        except Exception as e:
            return self._send(500, {"ok": False, "error": str(e)})


if __name__ == "__main__":
    port = 8766
    print(f"Router Control UI  ->  http://127.0.0.1:{port}")
    print("Router target      ->  http://192.168.1.1  (ZXHN H168N V3.5)")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
