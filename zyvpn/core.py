import os
import sys
import json
import time
import subprocess
import threading
import ctypes
from ctypes import wintypes
from collections import deque
from typing import Optional, List, Dict, Any, Tuple
from .models import VpnNode, AppSettings
from .generator import select_engine_and_generate_config
from .sysproxy import enable_system_proxy, disable_system_proxy
from .paths import get_bin_dir, get_data_dir

CREATE_NO_WINDOW = 0x08000000
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JobObjectExtendedLimitInformation = 9

class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('PerProcessUserTimeLimit', wintypes.LARGE_INTEGER),
        ('PerJobUserTimeLimit', wintypes.LARGE_INTEGER),
        ('LimitFlags', wintypes.DWORD),
        ('MinimumWorkingSetSize', ctypes.c_size_t),
        ('MaximumWorkingSetSize', ctypes.c_size_t),
        ('ActiveProcessLimit', wintypes.DWORD),
        ('Affinity', ctypes.c_size_t),
        ('PriorityClass', wintypes.DWORD),
        ('SchedulingClass', wintypes.DWORD),
    ]

class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ('ReadOperationCount', ctypes.c_uint64),
        ('WriteOperationCount', ctypes.c_uint64),
        ('OtherOperationCount', ctypes.c_uint64),
        ('ReadTransferCount', ctypes.c_uint64),
        ('WriteTransferCount', ctypes.c_uint64),
        ('OtherTransferCount', ctypes.c_uint64),
    ]

class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ('IoInfo', IO_COUNTERS),
        ('ProcessMemoryLimit', ctypes.c_size_t),
        ('JobMemoryLimit', ctypes.c_size_t),
        ('PeakProcessMemoryLimit', ctypes.c_size_t),
        ('PeakJobMemoryLimit', ctypes.c_size_t),
    ]

def create_kill_on_close_job():
    """Create a Windows Job Object that automatically terminates all child processes when ZyVPN exits."""
    if sys.platform != "win32":
        return None
    try:
        job = ctypes.windll.kernel32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        res = ctypes.windll.kernel32.SetInformationJobObject(
            job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)
        )
        return job if res else None
    except Exception:
        return None

def assign_proc_to_job(job, proc: Optional[subprocess.Popen]):
    if job and sys.platform == "win32" and proc:
        try:
            ctypes.windll.kernel32.AssignProcessToJobObject(job, proc._handle)
        except Exception:
            pass

class CoreController:
    def __init__(self):
        self.bin_dir = get_bin_dir()
        self.run_dir = os.path.join(get_data_dir(), "run")
        os.makedirs(self.run_dir, exist_ok=True)
        self.primary_process: Optional[subprocess.Popen] = None
        self.secondary_process: Optional[subprocess.Popen] = None # Sing-box TUN helper
        self.status: str = "disconnected" # "disconnected", "connecting", "connected", "error"
        self.error_message: str = ""
        self.current_node: Optional[VpnNode] = None
        self.current_mode: str = "tun"
        self.start_time: float = 0
        self.logs: deque = deque(maxlen=300)
        self._lock = threading.Lock()
        self._job = create_kill_on_close_job()

        # Clean any stale orphan processes from previous crashes or task manager kills
        self.cleanup_stale_processes()

    def cleanup_stale_processes(self):
        """Kill any lingering xray.exe or sing-box.exe processes to prevent port conflicts."""
        if sys.platform != "win32":
            return
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "xray.exe", "/T"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW
            )
            subprocess.run(
                ["taskkill", "/F", "/IM", "sing-box.exe", "/T"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW
            )
        except Exception:
            pass

    def log(self, message: str, level: str = "info"):
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] [{level.upper()}] {message}"
        with self._lock:
            self.logs.append(entry)
        print(entry)

    def _stream_output(self, proc: subprocess.Popen, name: str):
        try:
            for line in iter(proc.stdout.readline, ''):
                if line:
                    clean_line = line.strip()
                    if clean_line:
                        self.log(f"[{name}] {clean_line}")
            proc.stdout.close()
        except Exception:
            pass

    def start(self, node: VpnNode, settings: AppSettings) -> bool:
        self.stop()
        self.status = "connecting"
        self.error_message = ""
        self.current_node = node
        self.current_mode = settings.mode

        try:
            # Ensure clean ports
            self.cleanup_stale_processes()
            time.sleep(0.2)

            engine_name, config_dict, tun_helper = select_engine_and_generate_config(node, settings)
            self.log(f"Preparing connection to '{node.name}' via {node.protocol.upper()} ({node.transport.upper()}) [Engine: {engine_name.upper()}, Mode: {settings.mode.upper()}]...")

            cfg_path = os.path.join(self.run_dir, f"{engine_name}_config.json")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)

            if engine_name == "xray":
                exe_path = os.path.join(self.bin_dir, "xray.exe")
                cmd = [exe_path, "run", "-config", cfg_path]
            else:
                exe_path = os.path.join(self.bin_dir, "sing-box.exe")
                cmd = [exe_path, "run", "-c", cfg_path]

            if not os.path.exists(exe_path):
                raise FileNotFoundError(f"Engine binary not found: {exe_path}")

            self.log(f"Launching primary engine: {os.path.basename(exe_path)}")
            self.primary_process = subprocess.Popen(
                cmd,
                cwd=self.bin_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=CREATE_NO_WINDOW
            )
            assign_proc_to_job(self._job, self.primary_process)

            # Start thread to read logs
            t1 = threading.Thread(target=self._stream_output, args=(self.primary_process, engine_name), daemon=True)
            t1.start()

            # Check if primary engine stayed up
            time.sleep(0.8)
            if self.primary_process.poll() is not None:
                ret = self.primary_process.returncode
                raise RuntimeError(f"Engine process exited immediately with code {ret}")

            # If TUN helper is requested (Dual-Engine architecture)
            if tun_helper:
                helper_engine, helper_cfg = tun_helper
                helper_cfg_path = os.path.join(self.run_dir, f"{helper_engine}_tun_config.json")
                with open(helper_cfg_path, "w", encoding="utf-8") as f:
                    json.dump(helper_cfg, f, indent=2, ensure_ascii=False)

                helper_exe = os.path.join(self.bin_dir, f"{helper_engine}.exe")
                self.log(f"Starting whole-PC TUN router ({os.path.basename(helper_exe)} + Wintun)...")
                self.secondary_process = subprocess.Popen(
                    [helper_exe, "run", "-c", helper_cfg_path],
                    cwd=self.bin_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=CREATE_NO_WINDOW
                )
                assign_proc_to_job(self._job, self.secondary_process)

                t2 = threading.Thread(target=self._stream_output, args=(self.secondary_process, f"{helper_engine}-tun"), daemon=True)
                t2.start()

                time.sleep(1.0)
                if self.secondary_process.poll() is not None:
                    ret = self.secondary_process.returncode
                    raise RuntimeError(f"TUN router exited with code {ret}. Убедитесь, что приложение запущено с правами Администратора.")

            # Apply System Mode
            if settings.mode == "proxy":
                self.log(f"Configuring Windows System Proxy (HTTP: {settings.http_port})...")
                enable_system_proxy(http_port=settings.http_port, socks_port=settings.socks_port)
            elif settings.mode == "tun":
                # TUN handles all PC traffic (TCP & UDP) at the network adapter level
                disable_system_proxy()
                self.log("TUN mode active: all PC traffic (TCP & UDP, Discord Voice) routed via VPN adapter.")

            self.status = "connected"
            self.start_time = time.time()
            self.log(f"Successfully connected to {node.name}!")
            return True

        except Exception as e:
            self.log(f"Connection failed: {e}", level="error")
            self.status = "error"
            self.error_message = str(e)
            self.stop()
            return False

    def stop(self):
        self.log("Disconnecting...")
        if self.secondary_process:
            try:
                self.secondary_process.terminate()
                self.secondary_process.wait(timeout=1.5)
            except Exception:
                try:
                    self.secondary_process.kill()
                except Exception:
                    pass
            self.secondary_process = None

        if self.primary_process:
            try:
                self.primary_process.terminate()
                self.primary_process.wait(timeout=1.5)
            except Exception:
                try:
                    self.primary_process.kill()
                except Exception:
                    pass
            self.primary_process = None

        # Clean up system proxy and any stray processes
        disable_system_proxy()
        self.cleanup_stale_processes()
        self.status = "disconnected"
        self.current_node = None
        self.start_time = 0
        self.log("Disconnected successfully.")

    def get_status(self) -> Dict[str, Any]:
        uptime_sec = int(time.time() - self.start_time) if self.start_time > 0 and self.status == "connected" else 0
        with self._lock:
            logs_list = list(self.logs)
        return {
            "status": self.status,
            "error_message": self.error_message,
            "node": self.current_node.to_dict() if self.current_node else None,
            "mode": self.current_mode,
            "uptime_seconds": uptime_sec,
            "logs": logs_list
        }
