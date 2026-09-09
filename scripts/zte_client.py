# -*- coding: utf-8 -*-
"""ZTE ZXHN H168N V3.5 web client — reverse-engineered from live firmware
V3.5.0_EG1T13_ET (ZTE web server 1.0, 2015).

Auth flow (verified working):
  1) GET  /           -> SID cookie, page renders _sessionTOKEN vars (per-fetch)
  2) GET  /function_module/login_module/login_page/logintoken_lua.lua -> 8-digit nonce
  3) POST /           form: Username, Password=sha256(password+nonce),
                      action=login, _sessionTOKEN=<token rendered on THIS fetch>

Data endpoints (verified): GET-only, but the session must FIRST visit the
corresponding .lp page (getpage.lua?pid=1002&nextpage=<PAGE>) — otherwise 404.
Writes: POST to the endpoint URL with body "IF_ACTION=<op>&<fields...>&
_sessionTOKEN=<token from the .lp page>" and header "Check: sha256(body)".
"""
import hashlib
import json
import os
import re
import time

import requests


def _load_config(base_default: str = "http://192.168.1.1") -> dict:
    cfg = {"base": base_default, "username": "", "password": ""}
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


_CFG = _load_config()
BASE = _CFG["base"]
LOGIN_TOKEN_URL = BASE + "/function_module/login_module/login_page/logintoken_lua.lua"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": BASE + "/"}


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

    # ---- token handling -------------------------------------------------
    def tokens(self, html: str) -> dict:
        toks = {}
        m = re.search(r'var _sessionTmpToken = "((?:\\x[0-9a-fA-F]{2})+)"', html)
        if m:
            toks["sessionTmpToken"] = unescape_zte(m.group(1))
        m = re.search(r"_sessionTmpToken = '((?:\\x[0-9a-fA-F]{2})+)'", html)
        if m:
            toks["langSwitchToken"] = unescape_zte(m.group(1))
        m = re.search(r'addParameter\("_sessionTOKEN",\s*"(\d+)"\)', html)
        if m:
            toks["loginFormLiteral"] = m.group(1)
        return toks

    def write_token(self, html: str) -> str:
        t = self.tokens(html)
        return t.get("langSwitchToken") or t.get("sessionTmpToken") or t.get("loginFormLiteral") or ""

    # ---- auth ------------------------------------------------------------
    def login(self) -> bool:
        r0 = self.s.get(self.base + "/", timeout=10)
        toks = self.tokens(r0.text)
        st = toks.get("loginFormLiteral") or toks.get("sessionTmpToken", "")
        r1 = self.s.get(LOGIN_TOKEN_URL, timeout=10)
        nonce = strip_tags(r1.text)
        sha = hashlib.sha256((self.password + nonce).encode("utf-8")).hexdigest()
        r2 = self.s.post(self.base + "/", data={
            "Username": self.username, "Password": sha,
            "action": "login", "_sessionTOKEN": st,
        }, timeout=10)
        self.logged_in = "frm_username" not in r2.text.lower()
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
                raise ZteError("login failed")

    # ---- reads -----------------------------------------------------------
    def get(self, path: str) -> str:
        url = path if path.startswith("http") else self.base + path
        r = self.s.get(url, timeout=15)
        return r.text

    def page(self, pid: str, nextpage: str) -> str:
        return self.get(f"/getpage.lua?pid={pid}&nextpage={nextpage}")

    def read_endpoint(self, lp_page: str, endpoint: str) -> str:
        """Visit the .lp page then GET the data endpoint (required pattern)."""
        self._ensure_login()
        self.page(1002, lp_page)
        body = self.get("/common_page/" + endpoint)
        if "SessionTimeout" in body or "404 Not Found" in body:
            # re-login once and retry
            self.logged_in = False
            self._ensure_login()
            self.page(1002, lp_page)
            body = self.get("/common_page/" + endpoint)
        return body

    # ---- writes ----------------------------------------------------------
    def write(self, lp_page: str, endpoint: str, fields: dict,
              if_action: str = "Apply", token: str | None = None) -> str:
        """POST IF_ACTION=<op>&fields...&_sessionTOKEN=... with Check: sha256(body).
        Session-activates the endpoint by visiting its page first."""
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
    def parse_instances(xml: str) -> list[dict]:
        """Parse <Instance><ParaName>k</ParaName><ParaValue>v</ParaValue>...</Instance>
        into a list of dicts (with _InstID included)."""
        out = []
        for inst in re.findall(r"<Instance>(.*?)</Instance>", xml, re.S):
            pairs = re.findall(r"<ParaName>(.*?)</ParaName>\s*<ParaValue>(.*?)</ParaValue>", inst, re.S)
            d = {k.strip(): v.strip() for k, v in pairs}
            if d:
                out.append(d)
        return out

    @staticmethod
    def check_ok(xml: str) -> tuple[bool, str]:
        m = re.search(r"<IF_ERRORSTR>(.*?)</IF_ERRORSTR>", xml, re.S)
        err = m.group(1).strip() if m else "?"
        return err == "SUCC", err
