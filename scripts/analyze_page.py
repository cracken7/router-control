# -*- coding: utf-8 -*-
"""Analyze a saved .lp page: forms, inputs, hidden fields, AJAX endpoints,
address div (server path), and page-specific JS hints."""
import re
import sys


def analyze(path):
    src = open(path, encoding="utf-8", errors="replace").read()
    print(f"===== {path} ({len(src)} bytes) =====")

    # address div = endpoint for page's dataPost
    for m in re.finditer(r'<address[^>]*>.*?<span[^>]*>([^<]*)</span>', src, re.S):
        print("ADDRESS:", m.group(1).strip())

    # forms
    for m in re.finditer(r'<form[^>]*>', src):
        print("FORM:", m.group(0))

    # inputs/selects inside template_* blocks with names/ids
    inputs = re.findall(
        r'<(input|select|textarea)[^>]*?name="([^"]+)"[^>]*?id="([^"]+)"[^>]*?>', src)
    seen = set()
    for tag, name, iid in inputs:
        key = (tag, name, iid)
        if key in seen:
            continue
        seen.add(key)
        # extract full tag for type/value
        fm = re.search(r'<' + tag + r'[^>]*name="' + re.escape(name) +
                       r'"[^>]*id="' + re.escape(iid) + r'"[^>]*>', src)
        full = fm.group(0) if fm else ""
        typ = re.search(r'type="([^"]+)"', full)
        val = re.search(r'value="([^"]*)"', full)
        print(f"  INPUT {tag:8} type={typ.group(1) if typ else '-':9} "
              f"name={name:40} id={iid:40} value={val.group(1) if val else ''}")

    # selects options
    for m in re.finditer(r'<select[^>]*name="([^"]+)"[^>]*id="([^"]+)"[^>]*>(.*?)</select>', src, re.S):
        opts = re.findall(r'<option[^>]*value=\'([^\']*)\'[^>]*>([^<]*)', m.group(3))
        if opts:
            print(f"  SELECT {m.group(2)} ({m.group(1)}): {opts[:12]}")

    # dataTransfer / ajax URLs
    urls = set(re.findall(r'"(/[^"]*(?:lua|gch)[^"]*)"', src)) | set(
        re.findall(r"'(/[^']*(?:lua|gch)[^']*)'", src))
    for u in sorted(urls):
        print("  AJAX-URL:", u)

    # IF_ACTION hidden or set values
    for m in re.finditer(r'id="IF_ACTION"[^>]*value="([^"]*)"', src):
        print("  IF_ACTION default:", m.group(1))
    acts = set(re.findall(r'IF_ACTION[=:]\s*"(\w+)"', src)) | set(
        re.findall(r"IF_ACTION[=:]\s*'(\w+)'", src))
    if acts:
        print("  IF_ACTION values seen:", sorted(acts))

    # OBJ ids (response para names)
    objs = sorted(set(re.findall(r'find\("([A-Z][A-Z0-9_]+)"\)', src)))
    print("  XML-OBJ ids:", objs)

    print()


for p in sys.argv[1:]:
    analyze(p)
