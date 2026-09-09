# -*- coding: utf-8 -*-
"""Token-check probes WITHOUT attempting login (no lockout risk).
Figures out which _sessionTOKEN the server expects for our SID.
"""
import re

import requests

BASE = "http://192.168.1.1"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": BASE + "/"}

s = requests.Session()
s.headers.update(UA)
r0 = s.get(BASE + "/", timeout=10)
m = re.search(r"_sessionTmpToken = ['\"]([^'\"]+)['\"]", r0.text)
page_token = m.group(1).encode().decode("unicode_escape") if m else None
# it may be \x.. escaped; decode:
m2 = re.search(r"_sessionTmpToken = ['\"]((?:\\\\x[0-9a-fA-F]{2}|[^'\"])*)['\"]", r0.text)
raw = m2.group(1) if m2 else ""
try:
    page_token = raw.encode("latin-1").decode("unicode_escape")
except Exception:
    page_token = raw
print("page _sessionTmpToken =", repr(page_token))

for tok in [page_token, "531441325598595136689089", "bogus123"]:
    r = s.get(BASE + "/common_page/template_token_check.lua",
              params={"sessToken": tok}, timeout=10)
    print(f"token_check({tok[:10]}...) -> {r.status_code} {r.text[:120]!r}")

r1 = s.get(BASE + "/function_module/login_module/login_page/logintoken_lua.lua", timeout=10)
print("logintoken raw bytes:", r1.content[:200])
