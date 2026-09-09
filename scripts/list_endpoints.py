# -*- coding: utf-8 -*-
"""Extract address spans + ajax urls from all dumped .lp pages."""
import glob
import re

for path in sorted(glob.glob("pages/*.lp")):
    src = open(path, encoding="utf-8", errors="replace").read()
    addrs = re.findall(r'<address[^>]*>\s*<span[^>]*>([^<]*)</span>', src)
    if not addrs:
        continue
    name = path.split("/")[-1].split("\\")[-1]
    print(f"== {name}")
    for a in sorted(set(addrs)):
        print("   ", a.strip())
