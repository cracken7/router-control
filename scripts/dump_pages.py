# -*- coding: utf-8 -*-
"""Fetch every known content page + the JS/AJAX endpoints they reference.
Saves raw HTML under pages/ for offline endpoint analysis."""
import os
import re

from zte_client import ZteClient

PAGES = [
    "home_t.lp",
    "Internet_AdminInternetStatus_DSL_t.lp",
    "Internet_Dsl_t.lp",
    "Internet_Internet3G_t.lp",
    "Internet_InternetStatus_Internet3GStatus_t.lp",
    "Internet_Parent_Ctrl_t.lp",
    "Internet_QoS_Basic_t.lp",
    "Internet_QoS_Congestion_t.lp",
    "Internet_QoS_DownLimit_t.lp",
    "Internet_QoS_shaper_t.lp",
    "Internet_QoS_speed_t.lp",
    "Internet_QoS_type_t.lp",
    "Internet_Security_Firewall_t.lp",
    "Internet_Security_SecFilter_t.lp",
    "Internet_sntp_t.lp",
    "Localnet_LanMgrIpv4_t.lp",
    "Localnet_LocalnetStatusUser_t.lp",
    "Localnet_WlanAdvanced_t.lp",
    "Localnet_WlanBasicUser_t.lp",
    "Localnet_WlanBasicUser_t.lp&internetgateway_id=1",
    "Localnet_ftp_t.lp",
    "ManagDiag_AccountManag_t.lp",
    "ManagDiag_DeviceManag_t.lp",
    "ManagDiag_LanManag_t.lp",
    "ManagDiag_LoginTimeout_t.lp",
    "ManagDiag_StatusManag_t.lp",
    # WAN / port forwarding candidates (standard ZTE names)
    "Internet_WANInterfaceConfig_t.lp",
    "Internet_PortForward_t.lp",
    "Internet_PortTriggering_t.lp",
    "Internet_DDNS_t.lp",
    "Internet_DMZ_t.lp",
    "Internet_UPnP_t.lp",
    "Localnet_DHCPServer_t.lp",
    "Localnet_DHCP_t.lp",
    "Localnet_StaticDhcp_t.lp",
    "Localnet_MACFilter_t.lp",
    "Localnet_WlanFilter_t.lp",
    "Localnet_WlanAdvance_t.lp",
    "Localnet_WlanMultipleSSIDs_t.lp",
    "Internet_Alarm_t.lp",
    "ManagDiag_Telnet_t.lp",
    "ManagDiag_USBBackup_t.lp",
    "ManagDiag_SysLog_t.lp",
    "ManagDiag_PingTest_t.lp",
    "ManagDiag_TracerouteTest_t.lp",
    "ManagDiag_DiagPing_t.lp",
]

c = ZteClient()
print("LOGIN:", c.login())
os.makedirs("pages", exist_ok=True)

results = {}
for p in PAGES:
    name = p.split("&")[0]
    try:
        html = c.page(1002, p)
    except Exception as e:
        print(f"{p}: ERROR {e}")
        continue
    login_page = "frm_username" in html.lower()
    results[p] = (len(html), login_page)
    with open(f"pages/{name}", "w", encoding="utf-8", errors="replace") as f:
        f.write(html)
    flag = " [LOGIN PAGE - not found]" if login_page else ""
    print(f"{p}: {len(html)} bytes{flag}")

print("\n--- summary ---")
for p, (n, lp) in results.items():
    print(f"{'X' if lp else 'OK':>2} {p} {n}")
