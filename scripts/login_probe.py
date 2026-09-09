# -*- coding: utf-8 -*-
"""Login for ZTE ZXHN H168N V3.5 @ http://192.168.1.1/ — v2
_sessionTOKEN is extracted per-fetch from the rendered page (hex-escaped JS var),
not hardcoded: the server validates it against the SID's rendered token.
"""
import hashlib
import re
import sys

import requests

BASE = "http://192.168.1.1"
LOGIN_TOKEN_URL = BASE + "/function_module/login_module/login_page/logintoken_lua.lua"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": BASE + "/"}


def unescape_zte(s: str) -> str:
    return re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), s)


def extract_tokens(html: str) -> dict:
    toks = {}
    m = re.search(r'var _sessionTmpToken = "((?:\\x[0-9a-fA-F]{2})+)"', html)
    if m:
        toks["sessionTmpToken"] = unescape_zte(m.group(1))
    m = re.search(r'addParameter\("_sessionTOKEN",\s*"(\d+)"\)', html)
    if m:
        toks["loginFormLiteral"] = m.group(1)
    m = re.search(r"_sessionTmpToken = '((?:\\x[0-9a-fA-F]{2})+)'", html)
    if m:
        toks["langSwitchToken"] = unescape_zte(m.group(1))
    return toks


def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def probe(username: str, password: str) -> dict:
    s = requests.Session()
    s.headers.update(UA)
    r0 = s.get(BASE + "/", timeout=10)
    toks = extract_tokens(r0.text)
    print(f"[1] page tokens: {toks}")
    st = toks.get("loginFormLiteral") or toks.get("sessionTmpToken")

    r1 = s.get(LOGIN_TOKEN_URL, timeout=10)
    token = strip_tags(r1.text)
    print(f"[2] logintoken -> {token}")

    sha = hashlib.sha256((password + token).encode("utf-8")).hexdigest()
    data = {"Username": username, "Password": sha, "action": "login", "_sessionTOKEN": st}
    r2 = s.post(BASE + "/", data=data, timeout=10)
    body = r2.text
    m = re.search(r'var login_err_msg = ((?:"(?:[^"\\]|\\.)*")|""|\'[^\']*\');', body)
    err = unescape_zte(m.group(1).strip("'\"")) if m else "?"
    print(f"[3] POST -> {r2.status_code} err_msg={err!r} len={len(body)}")

    m = re.search(r'var DiaplayLockTime = "?([^";]*)"?;', body)
    lock = m.group(1) if m else "?"
    lower = body.lower()
    ok = ("frm_username" not in lower)
    print(f"    lock={lock} login_form_present={not ok}")
    if ok:
        r3 = s.get(BASE + "/getpage.lua?pid=1002&nextpage=status_lsid_lua.lua", timeout=10)
        print(f"[4] authenticated status page -> {r3.status_code} len={len(r3.text)}")
        return {"ok": True, "sid": s.cookies.get("SID")}
    return {"ok": False, "err": err, "lock": lock}


if __name__ == "__main__":
    user = sys.argv[1] if len(sys.argv) > 1 else "user"
    pwd = sys.argv[2] if len(sys.argv) > 2 else "etis"
    res = probe(user, pwd)
    print("RESULT:", "LOGIN OK" if res["ok"] else f"FAILED err={res.get('err')} lock={res.get('lock')}")
