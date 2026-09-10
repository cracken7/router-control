# -*- coding: utf-8 -*-
"""Which speedtest URL works from this machine? Also report system proxies."""
import urllib.request
import urllib.error

cands = [
    "https://speed.cloudflare.com/__down?bytes=5000000",
    "http://speedtest.tele2.net/5MB.zip",
    "https://proof.ovh.net/files/5Mb.dat",
    "http://ipv4.download.thinkbroadband.com/5MB.zip",
    "https://speed.hetzner.de/5MB.bin",
]
for u in cands:
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            n = len(r.read())
        print(f"OK   {u}  {n/1e6:.1f}MB")
    except Exception as e:
        print(f"FAIL {u}  {type(e).__name__}: {str(e)[:70]}")

import winreg
print("\n-- registry proxy --")
try:
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                       r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
    for name in ("ProxyEnable", "ProxyServer"):
        try:
            print(name, "=", winreg.QueryValueEx(k, name)[0])
        except FileNotFoundError:
            print(name, "= (not set)")
except Exception as e:
    print("reg err", e)
