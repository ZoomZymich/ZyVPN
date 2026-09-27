import os
import sys
import ctypes
import threading
import json
import multiprocessing

# PyInstaller binary compatibility
multiprocessing.freeze_support()

# Optimize Edge WebView2 RAM consumption
os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
    "--renderer-process-limit=1 "
    "--disk-cache-size=10485760 "
    "--js-flags=--max-old-space-size=128 "
    "--disable-features=Translate,OptimizationHints,MediaRouter"
)

# Ensure project root in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import zyvpn
import zyvpn.models
import zyvpn.paths
import zyvpn.storage
import zyvpn.core
import zyvpn.api
import zyvpn.generator
import zyvpn.parser
import zyvpn.tray
import zyvpn.sysproxy
import zyvpn.ping
import zyvpn.countries

def trim_process_memory():
    """Flush unreferenced memory pages from working set to keep RAM lean."""
    if sys.platform != "win32":
        return
    try:
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]
        psapi.EmptyWorkingSet.restype = wintypes.BOOL
        psapi.EmptyWorkingSet(k32.GetCurrentProcess())
    except Exception:
        pass

def start_memory_trimmer():
    def _trim_worker():
        import time
        time.sleep(3.0)
        trim_process_memory()
        while True:
            time.sleep(30.0)
            trim_process_memory()
    t = threading.Thread(target=_trim_worker, daemon=True)
    t.start()

MUTEX_NAME = "Local\\ZyVPN_SingleInstance_Mutex_ZYMA"
_instance_mutex = None

def check_single_instance() -> bool:
    """Ensure only one instance runs. If another exists, ping it to restore and exit immediately."""
    global _instance_mutex
    if sys.platform != "win32":
        return True
    kernel32 = ctypes.windll.kernel32
    _instance_mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    last_error = kernel32.GetLastError()
    # 183 = ERROR_ALREADY_EXISTS
    if last_error == 183:
        try:
            import urllib.request
            urllib.request.urlopen("http://127.0.0.1:18080/show", timeout=1.0)
        except Exception:
            pass
        return False
    return True

if not check_single_instance():
    sys.exit(0)

def is_admin() -> bool:
    """Check if the process is running with Windows Administrator privileges."""
    if sys.platform != "win32":
        return True
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def ensure_admin():
    """Relaunch process with Administrator privileges (UAC prompt) if not already elevated."""
    if is_admin():
        return
    # Allow bypassing elevation for headless tests or explicit debug flags
    if os.environ.get("ZYVPN_NO_ELEVATE") == "1" or "--no-elevation" in sys.argv:
        return

    if sys.platform == "win32":
        try:
            # Release single instance mutex so the elevated process can claim it
            global _instance_mutex
            if _instance_mutex:
                ctypes.windll.kernel32.CloseHandle(_instance_mutex)
                _instance_mutex = None

            if getattr(sys, 'frozen', False):
                exe = sys.executable
                params = " ".join([f'"{a}"' for a in sys.argv[1:]])
            else:
                exe = sys.executable
                script_path = os.path.abspath(sys.argv[0])
                args = [f'"{a}"' for a in sys.argv[1:]]
                params = f'"{script_path}" ' + " ".join(args)

            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params.strip(), BASE_DIR, 1)
            # Exit current non-elevated process
            sys.exit(0)
        except Exception as e:
            print(f"UAC elevation failed: {e}")
            sys.exit(1)

ensure_admin()

from zyvpn.storage import Storage
from zyvpn.core import CoreController
from zyvpn.api import VpnApi
from zyvpn.paths import get_ui_dir, get_data_dir
from zyvpn.tray import TrayController
from bottle import Bottle, static_file, request, response

storage = Storage()
core = CoreController()
api = VpnApi(storage, core)

# Lightweight Bottle Web Server for UI assets and HTTP API fallback
server = Bottle()
UI_DIR = get_ui_dir()
window = None
tray = None
is_quitting = False

def show_window():
    global window
    if window:
        try:
            window.show()
            window.restore()
        except Exception:
            pass

@server.route("/show")
def show_route():
    show_window()
    return "ok"

@server.route("/")
def index():
    return static_file("index.html", root=UI_DIR)

@server.route("/<filepath:path>")
def static_assets(filepath):
    return static_file(filepath, root=UI_DIR)

@server.hook("after_request")
def enable_cors():
    """Allow cross-origin requests from file:// and localhost origins."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"

@server.route("/api/<method>", method="OPTIONS")
def api_options(method):
    """Handle CORS preflight requests."""
    return ""

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

from wsgiref.simple_server import WSGIServer, make_server
from socketserver import ThreadingMixIn
import bottle

class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    timeout = 10.0

class ThreadingWSGIAdapter(bottle.ServerAdapter):
    def run(self, handler):
        srv = make_server(self.host, self.port, handler, server_class=ThreadingWSGIServer)
        srv.serve_forever()

def run_server():
    server.run(server=ThreadingWSGIAdapter(host="127.0.0.1", port=18080), quiet=True)

def main():
    global window, tray, is_quitting

    # Start local HTTP server in background thread
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    def on_exit():
        global is_quitting, _instance_mutex
        is_quitting = True
        try:
            core.stop()
        except Exception:
            pass
        if tray:
            try:
                tray.stop()
            except Exception:
                pass
        if window:
            try:
                window.destroy()
            except Exception:
                pass
        if _instance_mutex:
            try:
                ctypes.windll.kernel32.CloseHandle(_instance_mutex)
            except Exception:
                pass
            _instance_mutex = None
        os._exit(0)

    # Start memory trimmer loop in background
    start_memory_trimmer()

    # Initialize system tray
    tray = TrayController(api=api, on_show_window=show_window, on_exit=on_exit)
    api.set_tray(tray)
    tray.start()

    # Try launching PyWebView desktop window
    try:
        import webview
        icon_path = os.path.join(BASE_DIR, "zyvpn.ico")
        if not os.path.exists(icon_path):
            icon_path = None

        webview_data_dir = os.path.join(get_data_dir(), "webview")
        os.makedirs(webview_data_dir, exist_ok=True)

        window = webview.create_window(
            title="ZyVPN",
            url=os.path.join(UI_DIR, "index.html"),
            js_api=api,
            width=840,
            height=700,
            min_size=(680, 520),
            frameless=True,
            easy_drag=False,
            shadow=True,
            background_color="#090d16"
        )
        api.set_window(window)

        def on_closing():
            if is_quitting:
                return True
            try:
                window.hide()
                trim_process_memory()
                if tray:
                    tray.notify(
                        "ZyVPN свёрнут в трей",
                        "Приложение и VPN продолжают работать в фоне. Чтобы открыть — используйте иконку в трее."
                    )
                return False
            except Exception:
                return True

        window.events.closing += on_closing

        webview.start(
            gui="edgechromium",
            debug=False,
            storage_path=webview_data_dir,
            icon=icon_path
        )
    except Exception as e:
        print(f"PyWebView GUI error: {e}")
        print("Falling back to browser app mode: http://127.0.0.1:18080")
        import webbrowser
        webbrowser.open("http://127.0.0.1:18080")
        try:
            while not is_quitting:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    finally:
        on_exit()

if __name__ == "__main__":
    main()
