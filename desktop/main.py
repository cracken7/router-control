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


def _http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
            return data.get("ok") is True and "router" in data
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
    if _http_ok(f"http://127.0.0.1:{PREFERRED_PORT}/api/status"):
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
    print(f"server starting on 127.0.0.1:{port} ui={server.UI_DIR}")
    ThreadingHTTPServer(("127.0.0.1", port), server.Handler).serve_forever()


def main():
    import webview
    port = pick_port()
    url = f"http://127.0.0.1:{port}"
    if port_free(port):
        threading.Thread(target=boot_server, args=(port,), daemon=True).start()
        for _ in range(60):
            if _http_ok(url + "/api/status"):
                break
            time.sleep(0.1)
    try:
        webview.create_window("Router Control — ZTE H168N", url,
                              width=1180, height=860, min_size=(900, 620))
        webview.start()
    except TypeError:
        webview.create_window("Router Control — ZTE H168N", url)
        webview.start()


if __name__ == "__main__":
    main()
