"""
OtoStoksBot - Institutional Autonomous Trading Terminal for Screen Stocks.
Main application entry point.
"""
import os
import sys
import time
import socket
import urllib.request
import threading
import webbrowser
import uvicorn

from core.config import find_available_port, get_base_dir
from core.state import AppState
from core.notifications import show_native_notification
from api.server import create_app

try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False


class UvicornServerThread(threading.Thread):
    """Runs Uvicorn ASGI server in a dedicated daemon thread."""
    def __init__(self, fastapi_app, host: str = "127.0.0.1", port: int = 8080):
        super().__init__(daemon=True, name="UvicornServerThread")
        self.host = host
        self.port = port
        config = uvicorn.Config(
            fastapi_app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False
        )
        self.server = uvicorn.Server(config)

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True


def wait_for_server(url: str, max_retries: int = 60, delay: float = 0.1) -> bool:
    """Blocks until local FastAPI server responds to health checks."""
    for _ in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=0.5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(delay)
    return False


def main():
    # 1. Initialize Thread-Safe Core State
    state = AppState()

    # 2. Allocate Dynamic Available Local Port
    port = find_available_port(8080)
    server_url = f"http://127.0.0.1:{port}"
    status_url = f"{server_url}/api/status"

    # 3. Create FastAPI Application & Start Background Server
    app = create_app(state)
    server_thread = UvicornServerThread(app, host="127.0.0.1", port=port)
    server_thread.start()

    # 4. Wait for Server to be Healthy
    if not wait_for_server(status_url):
        print(f"[!] Server failed to initialize on port {port}. Exiting.", flush=True)
        sys.exit(1)

    print(f"[+] OtoStoksBot engine running on {server_url}", flush=True)

    # 5. Launch Native GUI Window (pywebview) or Fallback Browser
    base_dir = get_base_dir()
    icon_path = os.path.join(base_dir, "assets", "icon.ico")
    if not os.path.exists(icon_path):
        icon_path = os.path.join(base_dir, "icon.ico")

    if HAS_WEBVIEW:
        try:
            window = webview.create_window(
                title="OtoStoksBot Pro",
                url=server_url,
                width=1420,
                height=880,
                min_size=(1024, 680),
                background_color="#070b13",
                text_select=True
            )
            webview.start(debug=False)
        except Exception as e:
            print(f"[!] PyWebView interface notice ({e}). Opening default system browser...", flush=True)
            webbrowser.open(server_url)
            server_thread.join()
    else:
        webbrowser.open(server_url)
        server_thread.join()

    # Opt-in Background Tracking Check
    if state.settings.get("background_tracking", False):
        print("[*] Background Tracking active. Keeping OtoStoksBot engine running in background.", flush=True)
        show_native_notification(
            "OtoStoksBot Pro",
            "OtoStoksBot is running in the background and tracking Screen Stocks market movements."
        )
        try:
            while state.running:
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass

    # Clean shutdown
    state.running = False
    server_thread.stop()


if __name__ == "__main__":
    main()
