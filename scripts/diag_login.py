# -*- coding: utf-8 -*-
"""Definitive single-attempt login diagnostic (raw string regexes)."""
import hashlib
import re
import sys

import requests

sys.path.insert(0, ".")
from zte_client import _CFG, BASE, LOGIN_TOKEN_URL, UA, strip_tags

s = requests.Session()
s.headers.update(UA)
r0 = s.get(BASE + "/", timeout=10)
m2 = re.search(r'var _sessionTmpToken = "((?:\\x[0-9a-fA-F]{2})+)"', r0.text)
m3 = re.search(r'addParameter\("_sessionTOKEN",\s*"(\d+)"\)', r0.text)
lit = m3.group(1) if m3 else ""
r1 = s.get(LOGIN_TOKEN_URL, timeout=10)
nonce = strip_tags(r1.text)
sha = hashlib.sha256((_CFG["password"] + nonce).encode()).hexdigest()
r2 = s.post(BASE + "/", data={
    "Username": _CFG["username"], "Password": sha,
    "action": "login", "_sessionTOKEN": lit}, timeout=10)
ok = "frm_username" not in r2.text.lower()
mm = re.search(r"var login_err_msg = (.*?);", r2.text)


def unesc(x):
    return re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), x or "").strip('"')


print("token:", lit, "| nonce:", nonce, "| sha head:", sha[:10])
print("LOGIN:", ok)
if not ok:
    print("err:", unesc(mm.group(1)) if mm else "?")
