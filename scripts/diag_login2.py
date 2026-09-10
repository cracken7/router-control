# -*- coding: utf-8 -*-
"""Compare: same flow from source vs what the exe would do. Print everything."""
import hashlib
import re
import sys

import requests

sys.path.insert(0, ".")
from zte_client import _CFG, BASE, LOGIN_TOKEN_URL, UA, strip_tags

s = requests.Session()
s.headers.update(UA)
r0 = s.get(BASE + "/", timeout=10)
m3 = re.search(r'addParameter\("_sessionTOKEN",\s*"(\d+)"\)', r0.text)
lit = m3.group(1) if m3 else ""
m2 = re.search(r'var _sessionTmpToken = "((?:\\x[0-9a-fA-F]{2})+)"', r0.text)
page_tok = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), m2.group(1)) if m2 else ""
r1 = s.get(LOGIN_TOKEN_URL, timeout=10)
nonce = strip_tags(r1.text)
sha = hashlib.sha256((_CFG["password"] + nonce).encode()).hexdigest()
r2 = s.post(BASE + "/", data={
    "Username": _CFG["username"], "Password": sha,
    "action": "login", "_sessionTOKEN": lit}, timeout=10)
ok = "frm_username" not in r2.text.lower()
print(f"user={_CFG['username']!r} pass_len={len(_CFG['password'])} pass={_CFG['password']!r}")
print(f"form_token={lit} page_token={page_tok} nonce={nonce}")
print("LOGIN:", ok)
if not ok:
    mm = re.search(r"var login_err_msg = (.*?);", r2.text)
    lock = re.search(r"var DiaplayLockTime = (.*?);", r2.text)
    print("err:", mm.group(1) if mm else "?", "| lock:", lock.group(1) if lock else "?")
