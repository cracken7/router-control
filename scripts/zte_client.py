# -*- coding: utf-8 -*-
"""ZTE ZXHN H168N V3.5 web client — reverse-engineered from live firmware
V3.5.0_EG1T13_ET (ZTE web server 1.0, 2015).

Auth flow (verified working):
  1) GET  /           -> SID cookie, page renders _sessionTOKEN vars (per-fetch)
  2) GET  /function_module/login_module/login_page/logintoken_lua.lua -> 8-digit nonce
  3) POST /           form: Username, Password=sha256(password+nonce),
                      action=login, _sessionTOKEN=<token rendered on THIS fetch>

Rate limiting (discovered the hard way): wrong/expired-token logins trigger a
per-IP lockout with a visible countdown (DiaplayLockTime, up to ~60s+). The
client therefore rate-limits ITSELF: max 1 attempt per LOGIN_MIN_INTERVAL
seconds, and treats 'Username or password is error' + countdown as a
temporary lockout (retryable), distinct from bad credentials.
"""
import hashlib
import json
import os
import re
import time

import requests


def _load_config(base_default: str = "http://192.168.1.1") -> dict:
    """Config lookup order (first found wins):
    1. %APPDATA%/RouterControl/config.json  (canonical, survives exe rebuilds)
    2. config.json next to this file        (bundled / dev copy)
    The exe bundles a fallback copy; real credentials live OUTSIDE so changing
    the router password never requires rebuilding the exe."""
    cfg = {"base": base_default, "username": "", "password": ""}
    candidates = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(os.path.join(appdata, "RouterControl", "config.json"))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"))
    for cand in candidates:
        if os.path.exists(cand):
            try:
                with open(cand, encoding="utf-8") as f:
                    cfg.update(json.load(f))
            except Exception:
                pass
            break
    # If only the bundled copy exists (first run of a fresh exe), seed APPDATA
    # with it so the user can edit the external file later.
    if appdata and not os.path.exists(os.path.join(appdata, "RouterControl", "config.json")):
        try:
            bundled = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
            if os.path.exists(bundled):
                os.makedirs(os.path.join(appdata, "RouterControl"), exist_ok=True)
                with open(bundled, encoding="utf-8") as f:
                    content = f.read()
                with open(os.path.join(appdata, "RouterControl", "config.json"),
                          "w", encoding="utf-8") as f:
                    f.write(content)
        except Exception:
            pass
    return cfg


_CFG = _load_config()
BASE = _CFG["base"]
LOGIN_TOKEN_URL = BASE + "/function_module/login_module/login_page/logintoken_lua.lua"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": BASE + "/"}
LOGIN_MIN_INTERVAL = 10.0  # seconds between login ATTEMPTS (router locks on spam)


def unescape_zte(s: str) -> str:
    return re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), s)


def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


class ZteError(Exception):
    pass


class ZteClient:
    def __init__(self, base: str = None, username: str = None, password: str = None):
        self.base = base or _CFG["base"]
        self.username = username or _CFG["username"]
        self.password = password or _CFG["password"]
        self.s = requests.Session()
        self.s.headers.update(UA)
        self.logged_in = False
        self._last_login_attempt = 0.0

    # ---- token handling -------------------------------------------------
    def tokens(self, html: str) -> dict:
        toks = {}
        # The page assigns _sessionTmpToken several times (var decl at top,
        # plain re-assignments lower). The JS-effective value is the LAST
        # assignment in document order, regardless of quote style.
        assign = re.compile(r"(?:var\s+)?_sessionTmpToken\s*=\s*['\"]((?:\\x[0-9a-fA-F]{2})+)['\"]")
        occ = [(m.start(), unescape_zte(m.group(1))) for m in assign.finditer(html)]
        if occ:
            toks["sessionTmpToken"] = max(occ, key=lambda x: x[0])[1]
        m = re.search(r"_sessionTmpToken = '((?:\\x[0-9a-fA-F]{2})+)'", html)
        if m:
            toks["langSwitchToken"] = unescape_zte(m.group(1))
        m = re.search(r'addParameter\("_sessionTOKEN",\s*"(\d+)"\)', html)
        if m:
            toks["loginFormLiteral"] = m.group(1)
        return toks

    def write_token(self, html: str) -> str:
        """langSwitchToken first — that ordering is what every verified write on
        this firmware used. (ACL-policy endpoint additionally needs the FULL
        form body: _InstNum + all _InstID_i/ACLPolicy_i rows.)"""
        t = self.tokens(html)
        return t.get("langSwitchToken") or t.get("sessionTmpToken") or t.get("loginFormLiteral") or ""

    # ---- auth ------------------------------------------------------------
    def login(self) -> bool:
        """Single login attempt with strict self-rate-limiting.
        The router bans further attempts for ~30-60s after a failure, and every
        attempt during a ban extends it — so we back off hard instead of retrying."""
        now = time.time()
        if now < getattr(self, "_login_blocked_until", 0):
            return False
        wait = LOGIN_MIN_INTERVAL - (now - self._last_login_attempt)
        if wait > 0:
            time.sleep(wait)
        self._last_login_attempt = time.time()

        r0 = self.s.get(self.base + "/", timeout=10)
        toks = self.tokens(r0.text)
        st = toks.get("loginFormLiteral") or toks.get("sessionTmpToken", "")

        # respect an active router-side lockout countdown if present
        m = re.search(r"var DiaplayLockTime = \"?(\d+)\"?;", r0.text)
        if m and int(m.group(1)) > 0:
            time.sleep(min(int(m.group(1)) + 2, 90))

        r1 = self.s.get(LOGIN_TOKEN_URL, timeout=10)
        nonce = strip_tags(r1.text)
        sha = hashlib.sha256((self.password + nonce).encode("utf-8")).hexdigest()
        r2 = self.s.post(self.base + "/", data={
            "Username": self.username, "Password": sha,
            "action": "login", "_sessionTOKEN": st,
        }, timeout=10)
        self.logged_in = "frm_username" not in r2.text.lower()
        if not self.logged_in:
            # failed attempt ⇒ router will reject retries for a while. Back off 45s.
            self._login_blocked_until = time.time() + 45
        return self.logged_in

    def logoff(self):
        try:
            html = self.get("/")
            tok = self.write_token(html)
            self.s.post(self.base + "/", data={"IF_LogOff": "1", "sess_token": tok}, timeout=10)
        except Exception:
            pass
        self.logged_in = False

    def _ensure_login(self):
        if not self.logged_in:
            if not self.login():
                raise ZteError("login failed (router may be rate-limiting; retry shortly)")

    # ---- reads -----------------------------------------------------------
    def get(self, path: str) -> str:
        url = path if path.startswith("http") else self.base + path
        return self.s.get(url, timeout=15).text

    def page(self, pid: str, nextpage: str) -> str:
        return self.get(f"/getpage.lua?pid={pid}&nextpage={nextpage}")

    def read_endpoint(self, lp_page: str, endpoint: str) -> str:
        """Visit the .lp page then GET the data endpoint (required pattern)."""
        self._ensure_login()
        self.page(1002, lp_page)
        body = self.get("/common_page/" + endpoint)
        if "SessionTimeout" in body or "404 Not Found" in body:
            time.sleep(3)
            self.logged_in = False
            self._ensure_login()
            self.page(1002, lp_page)
            body = self.get("/common_page/" + endpoint)
        return body

    # ---- writes ----------------------------------------------------------
    def write(self, lp_page: str, endpoint: str, fields: dict,
              if_action: str = "Apply", token: str = None) -> str:
        """POST IF_ACTION=<op>&fields...&_sessionTOKEN=... with Check: sha256(body)."""
        self._ensure_login()
        page_html = self.page(1002, lp_page)
        tok = token or self.write_token(page_html)
        if not tok:
            raise ZteError("no _sessionTOKEN found on page " + lp_page)
        parts = [f"IF_ACTION={if_action}"]
        for k, v in fields.items():
            parts.append(f"{k}={v}")
        parts.append(f"_sessionTOKEN={tok}")
        body = "&".join(parts)
        headers = {
            "Check": hashlib.sha256(body.encode()).hexdigest(),
            "Referer": f"{self.base}/getpage.lua?pid=1002&nextpage={lp_page}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        url = self.base + "/common_page/" + endpoint
        r = self.s.post(url, data=body, headers=headers, timeout=20)
        text = r.text
        if "SessionTimeout" in text:
            time.sleep(3)
            self.logged_in = False
            self._ensure_login()
            page_html = self.page(1002, lp_page)
            tok = token or self.write_token(page_html)
            parts[-1] = f"_sessionTOKEN={tok}"
            body = "&".join(parts)
            headers["Check"] = hashlib.sha256(body.encode()).hexdigest()
            r = self.s.post(url, data=body, headers=headers, timeout=20)
            text = r.text
        return text

    # ---- XML parsing ------------------------------------------------------
    @staticmethod
    def parse_instances(xml: str) -> list:
        out = []
        for inst in re.findall(r"<Instance>(.*?)</Instance>", xml, re.S):
            pairs = re.findall(r"<ParaName>(.*?)</ParaName>\s*<ParaValue>(.*?)</ParaValue>", inst, re.S)
            d = {}
            for k, v in pairs:
                # decode common numeric entities the firmware emits (&#32; = space)
                v = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), v)
                d[k.strip()] = v.strip()
            if d:
                out.append(d)
        return out

    @staticmethod
    def check_ok(xml: str) -> tuple:
        m = re.search(r"<IF_ERRORSTR>(.*?)</IF_ERRORSTR>", xml, re.S)
        err = m.group(1).strip() if m else "?"
        return err == "SUCC", err
