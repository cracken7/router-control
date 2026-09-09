# -*- coding: utf-8 -*-
"""Inspect the login failure response for error message / lockout info."""
import hashlib
import re

import requests

BASE = "http://192.168.1.1"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": BASE + "/"}

s = requests.Session()
s.headers.update(UA)
s.get(BASE + "/", timeout=10)
r1 = s.get(BASE + "/function_module/login_module/login_page/logintoken_lua.lua", timeout=10)
token = re.sub(r"<[^>]+>", "", r1.text).strip()
sha = hashlib.sha256(("admin" + token).encode()).hexdigest()
r2 = s.post(BASE + "/", data={"Username": "admin", "Password": sha,
                              "action": "login", "_sessionTOKEN": "531441325598595136689089"},
            timeout=10)
body = r2.text
for pat in [r"var login_err_msg = (.*?);", r"var DiaplayLockTime = (.*?);",
            r"var prompt_msg = (.*?);"]:
    m = re.search(pat, body)
    print(pat, "=>", m.group(1) if m else "NOT FOUND")
print("len:", len(body))
