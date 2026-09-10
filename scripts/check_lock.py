# -*- coding: utf-8 -*-
"""Check router login lockout state WITHOUT logging in (read login page vars)."""
import re

import requests

s = requests.Session()
r = s.get("http://192.168.1.1/", timeout=10)
body = r.text
m = re.search(r"var login_err_msg = (.*?);", body)
m2 = re.search(r"var DiaplayLockTime = (.*?);", body)


def unesc(x):
    return re.sub(r"\\x([0-9a-fA-F]{2})", lambda mm: chr(int(mm.group(1), 16)), x or "").strip('"')


print("err_msg:", unesc(m.group(1)) if m else "none")
print("lock:", m2.group(1).strip('"') if m2 else "none")
