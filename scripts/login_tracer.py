# -*- coding: utf-8 -*-
"""Standalone one-shot server runner for the exe, with visible stderr logging.

Run inside the exe INSTEAD of importing server silently: every login attempt
and its result gets logged to %TEMP%\\routercontrol.log for diagnosis.
"""
import hashlib
import re
import time


def traced_login(client, log):
    """Reproduce zte_client.login() step-by-step with logging."""

    def L(msg):
        log(f"  {msg}")

    now = time.time()
    if now < getattr(client, "_login_blocked_until", 0):
        L(f"blocked until {client._login_blocked_until:.0f} (still {client._login_blocked_until-now:.0f}s)")
        return False
    wait = 10.0 - (now - client._last_login_attempt)
    if wait > 0:
        L(f"self-rate-limit: sleeping {wait:.1f}s")
        time.sleep(wait)
    client._last_login_attempt = time.time()

    L("GET /")
    r0 = client.s.get(client.base + "/", timeout=10)
    L(f"  status={r0.status_code} len={len(r0.text)}")
    toks = client.tokens(r0.text)
    L(f"  tokens={list(toks.keys())}")
    st = toks.get("loginFormLiteral") or toks.get("sessionTmpToken", "")
    L(f"  _sessionTOKEN={st!r}")

    m = re.search(r'var DiaplayLockTime = "?(\d+)"?;', r0.text)
    if m and int(m.group(1)) > 0:
        L(f"  router lockout={m.group(1)}s -> sleeping")
        time.sleep(min(int(m.group(1)) + 2, 90))

    L("GET logintoken_lua.lua")
    r1 = client.s.get("http://192.168.1.1/function_module/login_module/login_page/logintoken_lua.lua",
                      timeout=10)
    nonce = re.sub(r"<[^>]+>", "", r1.text).strip()
    L(f"  status={r1.status_code} nonce={nonce!r}")

    sha = hashlib.sha256((client.password + nonce).encode("utf-8")).hexdigest()
    L(f"  sha256(pass+nonce)={sha[:16]}...")

    L("POST / login")
    r2 = client.s.post(client.base + "/", data={
        "Username": client.username, "Password": sha,
        "action": "login", "_sessionTOKEN": st,
    }, timeout=10)
    L(f"  status={r2.status_code} len={len(r2.text)}")
    has_form = "frm_username" in r2.text.lower()
    L(f"  login_form_present={has_form}")
    mm = re.search(r"var login_err_msg = (.*?);", r2.text)
    if mm:
        import re as _re
        err = _re.sub(r"\\x([0-9a-fA-F]{2})", lambda x: chr(int(x.group(1), 16)), mm.group(1))
        L(f"  err_msg={err!r}")
    client.logged_in = not has_form
    if not client.logged_in:
        client._login_blocked_until = time.time() + 45
    L(f"  RESULT={client.logged_in}")
    return client.logged_in
