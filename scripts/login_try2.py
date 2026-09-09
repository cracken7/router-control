# -*- coding: utf-8 -*-
"""Login attempt using the CURRENT page-render session token as _sessionTOKEN.
Single attempt with user/etis. Compares server reaction vs the constant token.
"""
import hashlib
import re

import requests

BASE = "http://192.168.1.1"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": BASE + "/"}


def render_token(session):
    r0 = session.get(BASE + "/", timeout=10)
    m = re.search(r"_sessionTmpToken = ['\"]([^'\"]+)['\"]", r0.text)
    raw = m.group(1)
    try:
        return raw.encode("latin-1").decode("unicode_escape"), r0
    except Exception:
        return raw, r0


def try_login(user, pwd, token):
    s = requests.Session()
    s.headers.update(UA)
    page_tok, r0 = render_token(s)
    use_tok = page_tok if token is None else token
    r1 = s.get(BASE + "/function_module/login_module/login_page/logintoken_lua.lua",
               timeout=10)
    lt = re.sub(r"<[^>]+>", "", r1.text).strip()
    sha = hashlib.sha256((pwd + lt).encode()).hexdigest()
    r2 = s.post(BASE + "/", data={"Username": user, "Password": sha, "action": "login",
                                  "_sessionTOKEN": use_tok}, timeout=10)
    err = re.search(r'var login_err_msg = (.*?);', r2.text)
    err_val = err.group(1) if err else "?"
    # decode hex escapes if present
    try:
        err_dec = err_val.strip().strip('"').encode("latin-1").decode("unicode_escape")
    except Exception:
        err_dec = err_val
    is_login_page = "frm_username" in r2.text.lower()
    print(f"pageTok={page_tok[:8]}... useTok={use_tok[:8]}... loginTok={lt} "
          f"-> len={len(r2.text)} loginPage={is_login_page}")
    print(f"  err_msg={err_dec!r}")
    return s if not is_login_page else None


sess = try_login("user", "etis", None)
print("SESSION:", "LOGGED IN" if sess else "still login page")
