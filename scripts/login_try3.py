# -*- coding: utf-8 -*-
"""Diagnose token binding + single login attempt with full browser headers."""
import hashlib
import re

import requests

BASE = "http://192.168.1.1"
H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Origin": BASE,
    "Referer": BASE + "/",
    "Cache-Control": "max-age=0",
}

s = requests.Session()
s.headers.update(H)

# ---- free diagnostics: token rotation per SID ----
r0 = s.get(BASE + "/", timeout=10)
t1 = re.sub(r"<[^>]+>", "", s.get(
    BASE + "/function_module/login_module/login_page/logintoken_lua.lua",
    timeout=10).text).strip()
t2 = re.sub(r"<[^>]+>", "", s.get(
    BASE + "/function_module/login_module/login_page/logintoken_lua.lua",
    timeout=10).text).strip()
print(f"diag: SID={s.cookies.get('SID')[:8]}... tok1={t1} tok2={t2} "
      f"rotates={t1 != t2}")

# ---- single login attempt: full browser headers ----
tok = re.sub(r"<[^>]+>", "", s.get(
    BASE + "/function_module/login_module/login_page/logintoken_lua.lua",
    timeout=10).text).strip()
sha = hashlib.sha256(("etis" + tok).encode()).hexdigest()
r2 = s.post(BASE + "/", data={"Username": "user", "Password": sha,
                              "action": "login",
                              "_sessionTOKEN": "531441325598595136689089"},
            timeout=10, allow_redirects=True)
body = r2.text
err = re.search(r'var login_err_msg = (.*?);', body)
err_dec = ""
if err:
    try:
        err_dec = err.group(1).strip().strip('"').encode("latin-1").decode("unicode_escape")
    except Exception:
        err_dec = err.group(1)
lock = re.search(r'var DiaplayLockTime = (.*?);', body)
is_login = "frm_username" in body.lower()
loguser = re.search(r'id="logUser"[^>]*>\s*([^<]*)', body)
print(f"login: err={err_dec!r} lock={lock.group(1) if lock else '?'} "
      f"loginPage={is_login} logUser={loguser.group(1) if loguser else '?'}")
print("RESULT:", "LOGIN OK" if not is_login else "FAILED")
