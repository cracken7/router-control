# -*- coding: utf-8 -*-
"""RouterControl — desktop exe wrapper (pywebview).
Boots the local API server in a background thread, then opens a window on it.
If the server is already running (e.g. started by RouterControl.bat), reuses it."""
import socket
import sys
import threading
import time

PORT = 8766
URL = f"http://127.0.0.1:{PORT}"


def server_running() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def boot_server():
    import os
    app_dir = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "app")
    # PyInstaller: bundled server modules live in sys._MEIPASS/app
    if hasattr(sys, "_MEIPASS"):
        app_dir = os.path.join(sys._MEIPASS, "app")
    os.chdir(app_dir)
    sys.path.insert(0, app_dir)
    sys.path.insert(0, os.path.dirname(app_dir))
    import server
    server.UI_DIR = os.path.join(os.path.dirname(app_dir), "ui")
    if hasattr(sys, "_MEIPASS"):
        server.UI_DIR = os.path.join(sys._MEIPASS, "ui")
    print(f"server starting on {URL}, ui={server.UI_DIR}")
    from http.server import ThreadingHTTPServer
    ThreadingHTTPServer(("127.0.0.1", PORT), server.Handler).serve_forever()


def main():
    import webview
    if not server_running():
        threading.Thread(target=boot_server, daemon=True).start()
        for _ in range(50):
            if server_running():
                break
            time.sleep(0.1)
    try:
        webview.create_window("Router Control — ZTE H168N", URL,
                              width=1180, height=860, min_size=(900, 620))
        webview.start()
    except TypeError:
        webview.create_window("Router Control — ZTE H168N", URL)
        webview.start()


if __name__ == "__main__":
    main()
