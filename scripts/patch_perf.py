# -*- coding: utf-8 -*-
"""One-shot perf patch for server.py: unblock GET fan-out (no global LOCK),
add LOGIN_LOCK + ensure_login, parallelize dashboard."""
import re

src = open("../app/server.py", encoding="utf-8").read()

# --- imports + globals ---
src = src.replace("import threading\n",
                  "import threading\nfrom concurrent.futures import ThreadPoolExecutor\n", 1)
src = src.replace('AUTH = {"ok": False, "user": ""}',
                  'AUTH = {"ok": False, "user": ""}\n'
                  'LOGIN_LOCK = threading.Lock()\n'
                  'EXECUTOR = ThreadPoolExecutor(max_workers=4)')

# --- GET: login serialized on its own lock, everything else concurrent ---
old_login = '''            if u.path == "/api/login":
                with LOCK:
                    if client.logged_in:
                        return self._send(200, {"ok": True, "router": "ZXHN H168N V3.5"})
                    blocked = time.time() < getattr(client, "_login_blocked_until", 0)
                    if blocked:
                        return self._send(200, {"ok": False, "blocked": True})
                    ok = client.login()
                    return self._send(200, {"ok": ok, "router": "ZXHN H168N V3.5"})
            with LOCK:'''
new_login = '''            if u.path == "/api/login":
                with LOGIN_LOCK:
                    blocked = time.time() < getattr(client, "_login_blocked_until", 0)
                    if blocked and not client.logged_in:
                        return self._send(200, {"ok": False, "blocked": True})
                    ok = client.ensure_login()
                    return self._send(200, {"ok": ok, "router": "ZXHN H168N V3.5"})
            # Heavy GETs run concurrently: requests.Session is thread-safe and
            # the TTL cache collapses identical fan-out. Serializing them under
            # one global lock is what made phones crawl / time out.'''
assert old_login in src
src = src.replace(old_login, new_login)

# dedent the ex-'with LOCK:' GET body by 4 spaces (16 -> 12)
start = src.index(new_login) + len(new_login)
end = src.index("    def do_POST", start)
body = re.sub(r"^ {16}", " " * 12, src[start:end], flags=re.M)
src = src[:start] + body + src[end:]

# --- applogin on LOGIN_LOCK with ensure_login ---
old_app = '''                with LOCK:
                    blocked = time.time() < getattr(client, "_login_blocked_until", 0)
                    if blocked and not client.logged_in:
                        left = int(getattr(client, "_login_blocked_until", 0) - time.time())
                        return self._send(200, {"ok": False,
                                                "error": f"الراوتر بيبرد لسه — استنى {left} ثانية"})
                    if not client.logged_in:
                        if not client.login():
                            return self._send(200, {"ok": False, "error": "الراوتر رفض الدخول — جرّب بعد شوية"})'''
new_app = '''                with LOGIN_LOCK:
                    blocked = time.time() < getattr(client, "_login_blocked_until", 0)
                    if blocked and not client.logged_in:
                        left = int(getattr(client, "_login_blocked_until", 0) - time.time())
                        return self._send(200, {"ok": False,
                                                "error": f"الراوتر بيبرد لسه — استنى {left} ثانية"})
                    if not client.ensure_login():
                        return self._send(200, {"ok": False, "error": "الراوتر رفض الدخول — جرّب بعد شوية"})'''
assert old_app in src
src = src.replace(old_app, new_app)

# --- parallelize dashboard fan-out ---
old_dash = '''    def fn():
        out = {"ok": True}
        b = api_read("basic")
        out["qos_enabled"] = b["instances"][0].get("Enable") if b["instances"] else None
        dg = api_read("downlimit_global")
        out["downlimit"] = dg["instances"][0] if dg["instances"] else {}
        out["devices_count"] = len(api_devices()["devices"])
        w = api_wan()
        out["wan"], out["dsl"] = w["wan"], w["dsl"]
        info = client.parse_instances(client.read_endpoint(INFO_PAGE, INFO_EP))
        out["device_info"] = info[0] if info else {}
        tr = _traffic_state["series"]
        out["net"] = tr[-1] if tr else [0, 0]
        return out'''
new_dash = '''    def fn():
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
        out["devices_count"] = len(f_dv.result()["devices"])
        w = f_w.result()
        out["wan"], out["dsl"] = w["wan"], w["dsl"]
        info = client.parse_instances(f_i.result())
        out["device_info"] = info[0] if info else {}
        tr = _traffic_state["series"]
        out["net"] = tr[-1] if tr else [0, 0]
        return out'''
assert old_dash in src
src = src.replace(old_dash, new_dash)

open("../app/server.py", "w", encoding="utf-8").write(src)
print("server.py patched OK")

# --- client: ensure_login (idempotent, raises nothing) ---
c = open("../scripts/zte_client.py", encoding="utf-8").read()
if "def ensure_login" not in c:
    c = c.replace('''    def _ensure_login(self):
        if not self.logged_in:
            if not self.login():
                raise ZteError("login failed (router may be rate-limiting; retry shortly)")''',
'''    def _ensure_login(self):
        if not self.logged_in:
            if not self.login():
                raise ZteError("login failed (router may be rate-limiting; retry shortly)")

    def ensure_login(self) -> bool:
        """Bool variant used by the API server's serialized login path."""
        try:
            self._ensure_login()
            return True
        except Exception:
            return False''')
    open("../scripts/zte_client.py", "w", encoding="utf-8").write(c)
    print("zte_client ensure_login OK")
else:
    print("ensure_login already present")
