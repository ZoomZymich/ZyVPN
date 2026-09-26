import winreg
import ctypes
from ctypes import wintypes
import atexit

INTERNET_OPTION_SETTINGS_CHANGED = 39
INTERNET_OPTION_REFRESH = 37

wininet = ctypes.windll.wininet
InternetSetOptionW = wininet.InternetSetOptionW
InternetSetOptionW.argtypes = [wintypes.LPVOID, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD]
InternetSetOptionW.restype = wintypes.BOOL

REG_INTERNET_SETTINGS = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

def notify_system_proxy_change():
    """Notify Windows system that internet proxy settings changed."""
    try:
        InternetSetOptionW(None, INTERNET_OPTION_SETTINGS_CHANGED, None, 0)
        InternetSetOptionW(None, INTERNET_OPTION_REFRESH, None, 0)
    except Exception as e:
        print(f"Error notifying proxy change: {e}")

def enable_system_proxy(http_port: int = 10809, socks_port: int = 10808, bypass: str = "<local>;*.ru;*.su;*.xn--p1ai;*.yandex.*;*.vk.com;*.gosuslugi.ru;*.sberbank.ru;*.tinkoff.ru") -> bool:
    """Enable Windows system proxy for HTTP and SOCKS."""
    try:
        proxy_server = f"http=127.0.0.1:{http_port};https=127.0.0.1:{http_port};socks=127.0.0.1:{socks_port}"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_INTERNET_SETTINGS, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_server)
            if bypass:
                winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, bypass)
        notify_system_proxy_change()
        return True
    except Exception as e:
        print(f"Failed to enable system proxy: {e}")
        return False

def disable_system_proxy() -> bool:
    """Disable Windows system proxy."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_INTERNET_SETTINGS, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        notify_system_proxy_change()
        return True
    except Exception as e:
        print(f"Failed to disable system proxy: {e}")
        return False

def is_system_proxy_enabled() -> bool:
    """Check if Windows system proxy is currently enabled."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_INTERNET_SETTINGS, 0, winreg.KEY_QUERY_VALUE) as key:
            val, _ = winreg.QueryValueEx(key, "ProxyEnable")
            return bool(val)
    except Exception:
        return False

# Register exit handler to clean up proxy on exit
atexit.register(disable_system_proxy)
