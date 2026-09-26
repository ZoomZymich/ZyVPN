import os
import sys
import threading
import json
from bottle import Bottle, static_file, request, response

# Ensure project root in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from zyvpn.storage import Storage
from zyvpn.core import CoreController
from zyvpn.api import VpnApi
from zyvpn.paths import get_ui_dir

storage = Storage()
core = CoreController()
api = VpnApi(storage, core)

# Lightweight Bottle Web Server for UI assets and HTTP API fallback
server = Bottle()
UI_DIR = get_ui_dir()

@server.route("/")
def index():
    return static_file("index.html", root=UI_DIR)

@server.route("/<filepath:path>")
def static_assets(filepath):
    return static_file(filepath, root=UI_DIR)

@server.post("/api/<method>")
def api_handler(method):
    response.content_type = "application/json"
    if hasattr(api, method):
        func = getattr(api, method)
        try:
            data = request.json or {}
            args = data.get("args", [])
            if isinstance(args, list):
                result = func(*args)
            elif isinstance(args, dict):
                result = func(**args)
            else:
                result = func()
            return json.dumps(result)
        except Exception as e:
            response.status = 500
            return json.dumps({"success": False, "error": str(e)})
    else:
        response.status = 404
        return json.dumps({"error": f"Method {method} not found"})

def run_server():
    server.run(host="127.0.0.1", port=18080, quiet=True)

def main():
    # Start local HTTP server in background thread
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    # Try launching PyWebView desktop window
    try:
        import webview
        window = webview.create_window(
            title="ZyVPN - Universal VPN Client",
            url=os.path.join(UI_DIR, "index.html"),
            js_api=api,
            width=800,
            height=660,
            min_size=(640, 500),
            background_color="#0c1017"
        )
        webview.start(gui="edgechromium", debug=False)
    except Exception as e:
        print(f"PyWebView GUI error: {e}")
        print("Falling back to browser app mode: http://127.0.0.1:18080")
        import webbrowser
        webbrowser.open("http://127.0.0.1:18080")
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    finally:
        core.stop()

if __name__ == "__main__":
    main()
