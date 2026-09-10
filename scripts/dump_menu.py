# -*- coding: utf-8 -*-
"""Login + dump the main page's menu structure (navigator HTML) for mapping."""
import re

from zte_client import ZteClient

c = ZteClient()
ok = c.login()
print("LOGIN:", ok)
main = c.get("/")
open("logged_main.html", "w", encoding="utf-8").write(main)
print("saved logged_main.html len=", len(main))

# menu items: mainNavigator links + FakeClass1MenuShow definitions
links = re.findall(r'openLink\("([^"]+)"\)', main)
print("\n--- openLink targets (unique) ---")
for l in sorted(set(links)):
    print(l)

# also the JS menu data (often a JS array of pid/nextpage/name)
m = re.findall(r'(pid=\d+&nextpage=[\w.]+)', main)
print("\n--- pid/nextpage refs ---")
for l in sorted(set(m)):
    print(l)
