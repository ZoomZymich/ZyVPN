import os
import sys

def get_base_dir() -> str:
    """Return the base directory of the application (where .exe or run.py resides)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def get_bundle_dir() -> str:
    """Return the PyInstaller internal extraction directory or project root."""
    if hasattr(sys, '_MEIPASS'):
        return getattr(sys, '_MEIPASS')
    return get_base_dir()

def get_bin_dir() -> str:
    """Return path to binaries directory (xray.exe, sing-box.exe, etc.)."""
    return os.path.join(get_base_dir(), "bin")

def get_data_dir() -> str:
    """Return path to persistent user data directory (in %APPDATA%/ZyVPN on Windows)."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            data_dir = os.path.join(appdata, "ZyVPN")
            os.makedirs(data_dir, exist_ok=True)
            return data_dir
    data_dir = os.path.join(get_base_dir(), "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def get_ui_dir() -> str:
    """Return path to UI web assets."""
    for candidate in [
        os.path.join(get_bundle_dir(), "ui"),
        os.path.join(get_bundle_dir(), "zyvpn", "ui"),
        os.path.join(get_base_dir(), "ui"),
        os.path.join(get_base_dir(), "zyvpn", "ui"),
    ]:
        if os.path.exists(os.path.join(candidate, "index.html")):
            return candidate
    return os.path.join(get_base_dir(), "zyvpn", "ui")
