# -*- coding: utf-8 -*-
"""Log every login attempt to a file so we can see what the exe experiences."""
import time

from zte_client import ZteClient

LOG = "login_trace.log"


def run():
    lines = []
    c = ZteClient()
    lines.append(f"[{time.strftime('%H:%M:%S')}] login() starting, user={c.username}")
    ok = c.login()
    lines.append(f"[{time.strftime('%H:%M:%S')}] login result: {ok}")
    if ok:
        try:
            xml = c.read_endpoint("Internet_QoS_Basic_t.lp", "Internet_AdminQos_BasicCfg_lua.lua")
            lines.append(f"read: {c.check_ok(xml)} qos={c.parse_instances(xml)}")
        except Exception as e:
            lines.append(f"read error: {e!r}")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    run()
