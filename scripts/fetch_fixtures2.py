# -*- coding: utf-8 -*-
"""Fetch live fixtures for all NEW sections (wifi/lan/security/wan/system)."""
import os

from zte_client import ZteClient

JOBS = [
    # (lp page, endpoint)
    ("Internet_AdminInternetStatus_DSL_t.lp", "Internet_Internet_lua.lua?TypeUplink=1&pageType=1"),
    ("Internet_AdminInternetStatus_DSL_t.lp", "internet_dsl_interface_lua.lua"),
    ("Localnet_WlanBasicUser_t.lp", "Localnet_WlanBasicAd_WlanBasicAdConf_lua.lua"),
    ("Localnet_WlanBasicUser_t.lp", "Localnet_WlanBasicAd_OnOff_lua.lua"),
    ("Localnet_WlanBasicUser_t.lp", "Localnet_WlanBasicAd_WLANSSIDConf_EncryOption_lua.lua"),
    ("Localnet_WlanAdvanced_t.lp", "Localnet_WlanAdvanced_MACFilterRule_lua.lua"),
    ("Localnet_WlanAdvanced_t.lp", "Localnet_WlanAdvanced_MACFilterACLPolicy_lua.lua"),
    ("Localnet_LanMgrIpv4_t.lp", "Localnet_LanMgrIpv4_DHCPBasicCfg_lua.lua"),
    ("Localnet_LanMgrIpv4_t.lp", "Localnet_LanMgrIpv4_DHCPStaticRule_lua.lua"),
    ("Localnet_LanMgrIpv4_t.lp", "Localnet_LanMgrIpv4_DHCPHostInfo_lua.lua"),
    ("Localnet_LocalnetStatusUser_t.lp", "Localnet_WLAN_AccessDev_lua.lua"),
    ("Localnet_LocalnetStatusUser_t.lp", "lanStatus_lua.lua"),
    ("Localnet_LocalnetStatusUser_t.lp", "wlanStatus_lua.lua"),
    ("Internet_Security_Firewall_t.lp", "FirewallConf_lua.lua"),
    ("Internet_Security_SecFilter_t.lp", "URLFilter_lua.lua"),
    ("Internet_Security_SecFilter_t.lp", "SecurityGlobalCtl_lua.lua"),
    ("Internet_Parent_Ctrl_t.lp", "ParentCtrl_lua.lua"),
    ("ManagDiag_DeviceManag_t.lp", "deviceManag_lua.lua"),
    ("ManagDiag_StatusManag_t.lp", "ManagReg_lua.lua"),
]

c = ZteClient()
print("LOGIN:", c.login())
os.makedirs("fixtures", exist_ok=True)

for lp, ep in JOBS:
    try:
        c.page(1002, lp)
        body = c.get("/common_page/" + ep)
    except Exception as e:
        print(f"ERR {ep}: {e}")
        continue
    fn = ep.split("?")[0].replace("_lua.lua", "") + ".xml"
    ok = "ajax_response_xml_root" in body
    open(f"fixtures/{fn}", "w", encoding="utf-8", errors="replace").write(body)
    print(f"{'OK ' if ok else '404'} {ep:58} {len(body)}B")
