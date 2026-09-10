# -*- coding: utf-8 -*-
"""RouterControl — desktop exe wrapper (pywebview).
Boots the local API server in a background thread, then opens a window on it.
If something already listens on the port, verifies it's OUR healthy server;
otherwise picks a free port and starts a fresh server there."""
import json
import os
import socket
import sys
import threading
import time
import urllib.request

PREFERRED_PORT = 8766


def _log(msg: str):
    """Append to %APPDATA%/RouterControl/app.log — windowed exe has no console."""
    try:
        d = os.path.join(os.environ.get("APPDATA", "."), "RouterControl")
        os.makedirs(d, exist_ok=True)
        import datetime
        with open(os.path.join(d, "app.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%F %T} {msg}" + chr(10))
    except Exception:
        pass


def _http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
            return "router" in data or data.get("ok") is True
    except Exception:
        return False


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) != 0


def pick_port() -> int:
    """Preferred port if free; else a healthy existing instance; else a fresh free port."""
    if port_free(PREFERRED_PORT):
        return PREFERRED_PORT
    if _http_ok(f"http://127.0.0.1:{PREFERRED_PORT}/api/appstatus"):
        return PREFERRED_PORT  # healthy instance already running — reuse
    # occupied by something else (dead/stale): find another port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def boot_server(port: int):
    app_dir = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "app")
    if hasattr(sys, "_MEIPASS"):
        app_dir = os.path.join(sys._MEIPASS, "app")
    else:
        # running from source: try desktop/app, repo-root/app
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"),
            app_dir,
        ]
        app_dir = next((c for c in candidates if os.path.isdir(c)), app_dir)
    os.chdir(app_dir)
    sys.path.insert(0, app_dir)
    sys.path.insert(0, os.path.dirname(app_dir))
    import server
    server.UI_DIR = os.path.join(os.path.dirname(app_dir), "ui")
    if hasattr(sys, "_MEIPASS"):
        server.UI_DIR = os.path.join(sys._MEIPASS, "ui")
    from http.server import ThreadingHTTPServer
    print(f"server starting on 0.0.0.0:{port} ui={server.UI_DIR}")
    ThreadingHTTPServer(("0.0.0.0", port), server.Handler).serve_forever()


def server_loop(port: int):
    """serve_forever should never die; if it does, log and restart on same port."""
    while True:
        try:
            boot_server(port)
        except OSError as e:
            _log(f"bind fail {port}: {e}")
            time.sleep(3)
        except Exception as e:
            _log(f"server crash: {e!r}")
            time.sleep(2)


def main():
    try:
        import webview
    except Exception as e:
        _log(f"webview import failed: {e!r}; running server-only")
        _log(f"LAN URL for phones: see /api/appstatus")
        boot_server(PREFERRED_PORT)
        return

    port = pick_port()
    url = f"http://127.0.0.1:{port}"
    server_alive = False
    if port_free(port):
        t = threading.Thread(target=server_loop, args=(port,), daemon=False)
        t.start()
        for _ in range(100):
            if _http_ok(url + "/api/appstatus"):
                server_alive = True
                break
            time.sleep(0.1)
    else:
        server_alive = _http_ok(url + "/api/appstatus")
    _log(f"launching on port {port} (server={server_alive})")

    # Try to show a native window; user-closing must exit, GUI-failure must not.
    state = {"closed_by_user": False}
    t_launch = time.time()
    for attempt in range(1, 4):
        try:
            win = webview.create_window("Router Control — ZTE H168N", url,
                                        width=1180, height=860, min_size=(900, 620))
            try:
                win.events.closed += (lambda: state.__setitem__("closed_by_user", True))
            except Exception:
                pass
            webview.start()
        except TypeError:
            try:
                webview.create_window("Router Control — ZTE H168N", url)
                webview.start()
            except Exception as e:
                _log(f"attempt {attempt} typefail: {e!r}")
                continue
        except Exception as e:
            _log(f"attempt {attempt} window fail: {e!r}")
        ran_s = time.time() - t_launch
        if state["closed_by_user"] or ran_s > 2:
            _log("window closed by user — exiting")
            os._exit(0)
        # start() returned without a user close => GUI failed; retry then headless
        time.sleep(1.5)

    # headless fallback: open the system browser, keep server on main thread
    _log("GUI unavailable — opening default browser (headless mode)")
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
