# -*- coding: utf-8 -*-
"""RouterControl always-on service runner (started by Task Scheduler at boot).
Never dies: any crash logs + restarts the server within 3s."""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "app")
SCRIPTS = os.path.join(HERE, "scripts")
sys.path.insert(0, APP)
sys.path.insert(0, SCRIPTS)
os.chdir(APP)

LOG = os.path.join(r"C:\ProgramData", "RouterControl", "service.log")


def log(msg):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%F %T ") + msg + "\n")
    except Exception:
        pass


def main():
    log("service runner started")
    while True:
        try:
            from http.server import ThreadingHTTPServer
            import server
            log("serving on 0.0.0.0:8766")
            ThreadingHTTPServer(("0.0.0.0", 8766), server.Handler).serve_forever()
        except Exception as e:
            log(f"crash: {e!r} — restarting in 3s")
            time.sleep(3)


if __name__ == "__main__":
    main()
