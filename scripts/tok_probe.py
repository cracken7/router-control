# -*- coding: utf-8 -*-
"""Which _sessionTmpToken occurrence does the page actually end up with?"""
import re
import sys

sys.path.insert(0, ".")
from zte_client import ZteClient, unescape_zte

c = ZteClient()
print("login:", c.login())
html = c.page(1002, "Localnet_WlanAdvanced_t.lp")
pat = re.compile(r'_sessionTmpToken\s*=\s*"((?:\\x[0-9a-fA-F]{2})+)"')
occ = pat.findall(html)
print("occurrences:", len(occ))
vals = [unescape_zte(o) for o in occ]
for i, v in enumerate(vals):
    print(f"  [{i}] {v}")
print("unique:", len(set(vals)))
