import os
import sys
import hashlib
import ctypes
import platform
import winreg

_cached_hwid = None

def get_machine_guid() -> str:
    """Read Windows MachineGuid from Registry."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as k:
            guid, _ = winreg.QueryValueEx(k, "MachineGuid")
            if guid:
                return str(guid).strip()
    except Exception:
        pass
    return ""

def get_hwid() -> str:
    """
    Calculate hardware ID compatible with modern VPN panels (SnowVPN, FlClash, Happ, Incy, Marzban, Sub-Guard).
    Formula: SHA256(COMPUTERNAME-MachineGuid-Cores-RAM_MB)[:32].upper()
    """
    global _cached_hwid
    if _cached_hwid:
        return _cached_hwid

    comp_name = os.environ.get("COMPUTERNAME", "") or platform.node()
    guid = get_machine_guid()
    cores = os.cpu_count() or 4

    # Get Total Physical RAM in MB
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        mem_mb = stat.ullTotalPhys // (1024 * 1024)
    except Exception:
        mem_mb = 8192

    device_id = f"{comp_name}-{guid}-{cores}-{mem_mb}"
    _cached_hwid = hashlib.sha256(device_id.encode("utf-8")).hexdigest()[:32].upper()
    return _cached_hwid

def get_subscription_headers() -> dict:
    """Headers required for downloading subscriptions from modern VPN panels with HWID verification."""
    hwid = get_hwid()
    return {
        "User-Agent": "Clash/Meta; SnowVPN/v5.1.0 Platform/windows",
        "Accept": "*/*",
        "x-hwid": hwid,
        "x-device-os": "Windows",
        "x-ver-os": platform.release(),
        "x-device-model": "PC",
        "Device-Id": hwid,
        "X-Device-Id": hwid
    }
