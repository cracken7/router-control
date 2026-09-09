# QOS_REVERSE_ENGINEERING.md — verified parameter reference
All values confirmed against live router (reads + one verified write round-trip on Basic Enable).

## Global activation pattern
- READ:  visit `getpage.lua?pid=1002&nextpage=<LP>` once, then `GET /common_page/<EP>` → XML
- WRITE: `POST /common_page/<EP>` body `IF_ACTION=<op>&<fields>&_sessionTOKEN=<tok>` + header `Check: sha256(body)`
- `<tok>` = `_sessionTmpToken` rendered inside the .lp page HTML (24 digits)

---

## 1) QoS Global Configuration — Internet_QoS_Basic_t.lp
EP: `Internet_AdminQos_BasicCfg_lua.lua` · OBJ: `OBJ_QOSQB_ID` · singleton `_InstID=IGD`
| Param | Type | Values | Meaning |
|---|---|---|---|
| Enable | radio | 1/0 | QoS engine master switch (**write-verified**) |
| (implicit) | — | — | No other fields posted by UI Apply (form has only Enable) |

UI write = `IF_ACTION=Apply&Enable=<0|1>&_sessionTOKEN=...`

## 2) Classification — Internet_QoS_type_t.lp
EP: `Internet_QoS_type_lua.lua` · OBJ: `OBJ_QOSQC_ID` · multi-instance (list; _InstID=DEV.QOS.QCn)
Full param set (from XML + form):
| Param | Type | Values / format |
|---|---|---|
| Alias | text | rule name (e.g. `Total_bandwidth_limit_QC`) |
| Enable | radio | 1/0 |
| Order | int | rule priority order (1 = first) |
| AllInterface | radio | 1 = any interface, 0 = restrict to DevIn |
| DevIn | select | interface path: WAN / `DEV.IP.IF3`(Route_3G) / `DEV.IP.IF4` INTERNET_TR069_R_0_35 / `DEV.IP.IF7` TR069 / `DEV.IP.IF8` Mgt.2_R_8_88 / `DEV.IP.IF9` Mgt.1_R_5_55 / `DEV.BRIDGING.BR1.BRPORT2..6` = LAN1..4,SSID1..3 |
| MACSrc / MACDest | mac6 | `AA:BB:CC:DD:EE:FF` or 00:…:00 = ignore (form splits into sub_MACSrc0..5) |
| IPSrc + IPSrcMask / IPDest + IPDestMask | ip4+mask | dotted; empty = ignore |
| SrcPort + SrcPortMax / DestPort + DestPortMax | int | -1 = ignore; range = port..portMax |
| VlanID | int | -1 = ignore |
| VlanPrio | select | -1 = ignore (0-7 available) |
| VlanPrioMark | select | mark priority on egress (-1 default) |
| DSCPCheck | int | -1 = ignore |
| DscpMark | int | -1 = no remark |
| L2Protocol | select | empty = any (IPoE, PPPoE available in form) |
| L3ProtocolList | select | empty = any (TCP/UDP/ICMP available) |
| TcpAck | radio | 1 = match TCP ACK only, 0 = any |
| TrafficClass | int | -1 default; queue class binding |
| PolicerQueue | select | policer to attach: empty / `DEV.QOS.QP1..3` |

UI write shapes:
- Add:    `IF_ACTION=Add&_InstID=-1&Alias=...&Enable=1&...`
- Apply:  `IF_ACTION=Apply&_InstID=DEV.QOS.QC1&...` (enable toggle may omit other fields: `Enable=1&_InstID=...`)
- Delete: `IF_ACTION=Delete&_InstID=DEV.QOS.QCn`

## 3) Congestion Management — Internet_QoS_Congestion_t.lp
EP: `Internet_AdminQos_Congestion_lua.lua` · OBJ: `OBJ_QOSQQ_ID` (empty on this unit)
| Param | Type | Values |
|---|---|---|
| InterfaceFilter | select | LAN1..4 (BRPORT2..5) — queue direction interface |
| QueueNum | select | queue index |
| SchedulerAlgorithm | select | scheduling algo (SP/WFQ family) |
| DefaultQueue | radio | 1/0 |
| NeedStats | radio | 1/0 |
| InterfaceFilter2 | select | LAN1..4 (stats filter UI) |
Stats endpoint: `Internet_AdminQos_QoSStatistics_lua.lua` (OBJ_QOSQQSTATS_ID)
Instance ops same Add/Apply/Delete pattern with `_InstID`.

## 4) Traffic Policing — Internet_QoS_speed_t.lp
EP: `Internet_QoS_speed_lua.lua` · OBJ: `OBJ_QOSQP_ID` · instances DEV.QOS.QP1..3 (live: Total_bandwidth_limit_QP, aboya, ana — all Enable=0)
| Param | Live value | Meaning |
|---|---|---|
| Alias | e.g. aboya | policer name |
| Enable | 0 | policer active |
| MeterType | SimpleTokenBucket | meter algorithm |
| CommittedRate | 100000000 | **rate in bps** (100 Mbit/s) |
| CommittedBurstSize | 12500000 | burst bytes (12.5 MB) |
| PeakRate / PeakBurstSize / ExcessBurstSize | 0 | two-rate meter params (unused in SimpleTokenBucket) |
| ConformingAction | Null | in-profile action |
| PartialConformingAction | Drop | partially conforming |
| NonConformingAction | Drop | out-of-profile ⇒ drop |

## 5) Traffic Shaping — Internet_QoS_shaper_t.lp
EP: `Internet_QoS_shaper_lua.lua` · OBJ: `OBJ_QOSSHAPER_CONF_ID` (empty on this unit — no shaper instances yet)

## 6) Downside speed limit — Internet_QoS_DownLimit_t.lp (TWO endpoints)
### 6a. Global/PORT — `Internet_QoS_Down_Port_lua.lua` · OBJ_QOS_COMBINE_ID (singleton IGD)
| Param | Live | Meaning |
|---|---|---|
| Enable | 1 | down-limit feature master |
| DownBandwidth | 0 | global down cap (kbps; 0 = off) |
### 6b. Per-host rules — `Internet_QoS_IPDownList_lua.lua` · OBJ_QOS_COMBINE_IP_ID
Live: QCDownlimit1 "aboya" (DestMAC 74:8a:28:35:e4:c6, DownBandwidth=8192, Enable=0),
QCDownlimit2 "ana" (60:0f:6b:96:e4:5f, 4000000, Enable=0)
| Param | Meaning |
|---|---|
| Alias | rule name |
| Enable | 1/0 |
| ManaType | `mac` or `ip` (checkboxes TrafficType_MAC/IP/LAN in form) |
| DestMAC | target host MAC (lowercase, colon-separated) |
| IPDest + IPDestMask | target host IP (0.0.0.0 when MAC mode) |
| DestDevIF | LAN port where host sits: `DEV.BRIDGING.BR1.BRPORTn` |
| DownBandwidth | cap in **kbps** (8192 = 8 Mbit/s) |

## Units cheat-sheet
- Policer CommittedRate = bps. DownLimit DownBandwidth = kbps. Burst = bytes.

## Verified write example (live, round-trip PASS)
```
POST /common_page/Internet_AdminQos_BasicCfg_lua.lua
Check: sha256(body)
Content-Type: application/x-www-form-urlencoded

IF_ACTION=Apply&Enable=0&_sessionTOKEN=123344027765338325179041
→ <IF_ERRORSTR>SUCC</IF_ERRORSTR> … read-back Enable=0 … restore Enable=1 → SUCC
```
