# -*- coding: utf-8 -*-
"""Extract the full menu tree (meta_menu / menu_items / menu_subitems) from
the logged-in main frame JS into JSON."""
import json
import re

src = open("logged_main.html", encoding="utf-8", errors="replace").read()

# Grab the JS block containing meta_menu definitions
start = src.index("meta_menu = new Array();")
end = src.index("function ", start)  # next JS function after the menu block
block = src[start:end]

tree = {}
stack = []  # list of (varname, dict-ref)
pattern = re.compile(
    r"(\w+)\['([^']+)'\](?:\['([^']+)'\](?:\['([^']+)'\](?:\['([^']+)'\])?)?)?\s*=\s*(new Array\(\));?"
)

# Simpler: parse assignments line by line
cur = {}
lines = [l.strip() for l in block.splitlines() if l.strip()]
for ln in lines:
    m = re.match(r"(\w+)\['([^']+)'\]\s*=\s*new Array\(\)", ln)
    if m:
        container, key = m.group(1), m.group(2)
        level = {"meta_menu": 0, "menu_items": 1, "menu_subitems": 2}[container]
        # build node path
        parts = re.findall(r"\['([^']+)'\]", ln)
        # parts like ['mmInternet'] possibly nested
        node = tree.setdefault("meta_menu", {})
        # We'll instead track a flat list and reconstruct below
        continue

# Robust approach: evaluate assignments in order with nested dicts
root = {"meta_menu": {}, "menu_items": {}, "menu_subitems": {}}
# Ordered list of (container, path:list, value)
assigns = re.findall(
    r"(meta_menu|menu_items|menu_subitems)((?:\['[^']+'\])+)\s*=\s*new Array\(\)", block)
setters = re.findall(
    r"(meta_menu|menu_items|menu_subitems)((?:\['[^']+'\])+)\['(\w+)'\]\s*=\s*'([^']*)'", block)

def get_node(container, path):
    node = root[container]
    for k in path:
        node = node.setdefault(k, {})
    return node

paths_by_container = {}
for container, pathexpr in assigns:
    path = re.findall(r"\['([^']+)'\]", pathexpr)
    paths_by_container[(container, tuple(path))] = get_node(container, path)

# parent links: menu_items path starts with the meta key
for container, pathexpr, key, val in setters:
    path = re.findall(r"\['([^']+)'\]", pathexpr)
    node = get_node(container, path)
    node[key] = val

# Build a readable tree: meta -> items -> subitems keyed by their first path segment
def build():
    out = []
    for mkey, mval in root["meta_menu"].items():
        entry = {"id": mkey, "name": mval.get("langName"), "page": mval.get("page"),
                 "url": mval.get("URL"), "items": []}
        for ikey, ival in root["menu_items"].get(mkey, {}).items():
            item = {"id": ikey, "name": ival.get("langName"), "page": ival.get("page"),
                    "url": ival.get("URL"), "subitems": []}
            for skey, sval in root["menu_subitems"].get(mkey, {}).get(ikey, {}).items():
                if not isinstance(sval, dict):
                    continue
                item["subitems"].append({"id": skey, "name": sval.get("langName"),
                                         "page": sval.get("page"), "url": sval.get("URL")})
            entry["items"].append(item)
        out.append(entry)
    return out

result = build()
with open("menu_tree.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

for e in result:
    print(f"== {e['name']} ({e['page']})")
    for it in e["items"]:
        print(f"   - {it['name']} ({it['page']})")
        for s in it["subitems"]:
            print(f"        * {s['name']} ({s['page']})")
