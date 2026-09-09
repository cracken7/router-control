# ROUTER_DISCOVERY_REPORT.md — ZTE ZXHN H168N V3.5 @ 192.168.1.1
All findings below are **verified against the live router** (not assumed). Date: session 2026-09.

## 1. Identity
- Server header: `ZTE web server 1.0 ZTE corp 2015.`
- Title: `ZXHN H168N V3.5`, footer version: `V3.5.0_EG1T13_ET`
- Cookies: `SID` (HttpOnly) + `_TESTCOOKIESUPPORT=1` on first GET /
- Security headers: X-Frame-Options SAMEORIGIN, CSP `frame-ancestors 'self'; img-src 'self' data:`, nosniff, XSS-Protection

## 2. Authentication flow (VERIFIED working, incl. live write)
1. `GET /` → SID cookie; login page renders `_sessionTmpToken` (hex-escaped JS string, 24 digits, changes per fetch)
2. `GET /function_module/login_module/login_page/logintoken_lua.lua` → XML with 8-digit nonce
3. `POST /` (form-urlencoded):
   - `Username=<user>`
   - `Password=sha256(<password> + <nonce>)` (lowercase hex)
   - `action=login`
   - `_sessionTOKEN=` the 24-digit token rendered on the **same fetch** as step 1
   - success ⇒ page without `Frm_Username` (main frame)
- Failure modes seen: wrong/expired `_sessionTOKEN` ⇒ "This page has expired, please refresh and try again."
- Logout: `POST /` with `IF_LogOff=1&sess_token=<token>`
- User account used: `user` (ETISALAT default). Admin creds not provided by owner.

## 3. Page/frame model
- Outer frame: `/getpage.lua?pid=1002&nextpage=<NAME>_t.lp` (menu is built in JS from
  `meta_menu/menu_items/menu_subitems` arrays — full tree extracted to scripts/menu_tree.json)
- Session-scoped endpoint activation: **a data endpoint under /common_page/ answers GET only
  after its .lp page has been visited in the same session**; otherwise 404.
  (Verified: direct GET = 404; GET after visiting page = XML data.)

## 4. Read pattern (verified)
`GET /common_page/<X>_lua.lua` after visiting `getpage.lua?pid=1002&nextpage=<X>_t.lp`
→ XML: `<ajax_response_xml_root>...<OBJ_..._ID><Instance><ParaName>k</ParaName><ParaValue>v</ParaValue>...</Instance>...`

## 5. Write pattern (VERIFIED by live round-trip test on QoS Basic)
`POST /common_page/<X>_lua.lua` with:
- body: `IF_ACTION=Apply&<field>=<value>...&_sessionTOKEN=<24-digit token from the .lp page>`
- header: `Check: sha256(body_utf8)` (lowercase hex)
- Content-Type: `application/x-www-form-urlencoded`
- response: `<IF_ERRORSTR>SUCC</IF_ERRORSTR>` on success; read-back confirmed change.

Instance operations (standard ZTE soho framework, present in page JS):
- Add: `IF_ACTION=Add&_InstID=-1&...fields`
- Delete: `IF_ACTION=Delete&_InstID=<id>`
- Apply (edit/enable): `IF_ACTION=Apply&_InstID=<id>&...`
- Inst switch: `IF_ACTION=Apply&<ParamName>=<value>&_InstID=<id>`

## 6. Full menu tree (from meta_menu JS)
See scripts/menu_tree.json. Top: Home / Internet / Local Network / Management & Diagnosis.
Internet → QoS pages:
| Menu name | .lp page | Data endpoint | OBJ id |
|---|---|---|---|
| QoS Global Configuration | Internet_QoS_Basic_t.lp | /common_page/Internet_AdminQos_BasicCfg_lua.lua | OBJ_QOSQB_ID |
| Classification | Internet_QoS_type_t.lp | /common_page/Internet_QoS_type_lua.lua | OBJ_QOSQC_ID |
| Congestion Management | Internet_QoS_Congestion_t.lp | /common_page/Internet_AdminQos_Congestion_lua.lua | OBJ_QOSQQ_ID (+ OBJ_QOSQQSTATS_ID stats) |
| Traffic Policing | Internet_QoS_speed_t.lp | /common_page/Internet_QoS_speed_lua.lua | OBJ_QOSQP_ID |
| Traffic Shaping | Internet_QoS_shaper_t.lp | /common_page/Internet_QoS_shaper_lua.lua | OBJ_QOSSHAPER_CONF_ID |
| Downside speed limit | Internet_QoS_DownLimit_t.lp | /common_page/Internet_QoS_Down_Port_lua.lua + /common_page/Internet_QoS_IPDownList_lua.lua | OBJ_QOS_COMBINE_ID / OBJ_QOS_COMBINE_IP_ID |

## 7. Live state snapshot (read 2026-09, this session)
- QoS global: **Enable=1**
- Classification (QC1): "Total_bandwidth_limit_QC", Enable=1, Order=1, DevIn=WAN,
  PolicerQueue=DEV.QOS.QP1, all match fields empty/-1 (catch-all → QP1)
- Policers (QP): QP1 Total_bandwidth_limit_QP 100000000 bps (Enable=0),
  QP2 "aboya" 100000000 (Enable=0), QP3 "ana" 100000000 (Enable=0);
  MeterType=SimpleTokenBucket, CBS=12500000, Conforming=Null, NonConforming=Drop
- Congestion (QQ): empty (no queues returned)
- Shaper: empty
- DownLimit: global IGD Enable=1 DownBandwidth=0;
  IPDownList: QCDownlimit1 "aboya" (MAC 74:8a:28:35:e4:c6, 8192 kbps?, Enable=0),
  QCDownlimit2 "ana" (MAC 60:0f:6b:96:e4:5f, 4000000, Enable=0)
- Devices seen (home_wlanDevice): realme-6-Pro, Redmi-Note-11, android-…, almw, +2 unknown

## 8. Secrets handling
- Credentials live only in `scripts/zte_client.py` constructor defaults (local file, git-ignored via `.gitignore`? — add before commit)
- No credentials/tokens in reports; fixtures contain only config data
