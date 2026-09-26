import os
import sys
import json
import time
import subprocess
import threading
from collections import deque
from typing import Optional, List, Dict, Any, Tuple
from .models import VpnNode, AppSettings
from .generator import select_engine_and_generate_config, generate_singbox_config, generate_xray_config
from .sysproxy import enable_system_proxy, disable_system_proxy
from .paths import get_bin_dir, get_data_dir

CREATE_NO_WINDOW = 0x08000000

class CoreController:
    def __init__(self):
        self.bin_dir = get_bin_dir()
        self.run_dir = os.path.join(get_data_dir(), "run")
        os.makedirs(self.run_dir, exist_ok=True)
        self.primary_process: Optional[subprocess.Popen] = None
        self.secondary_process: Optional[subprocess.Popen] = None # For TUN helper if needed
        self.status: str = "disconnected" # "disconnected", "connecting", "connected", "error"
        self.error_message: str = ""
        self.current_node: Optional[VpnNode] = None
        self.current_mode: str = "proxy"
        self.start_time: float = 0
        self.logs: deque = deque(maxlen=300)
        self._lock = threading.Lock()

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
            engine_name, config_dict = select_engine_and_generate_config(node, settings)
            self.log(f"Preparing connection to '{node.name}' via {node.protocol.upper()} ({node.transport.upper()}) using {engine_name.upper()}...")
            
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

            self.log(f"Launching engine: {os.path.basename(exe_path)}")
            self.primary_process = subprocess.Popen(
                cmd,
                cwd=self.bin_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=CREATE_NO_WINDOW
            )

            # Start thread to read logs
            t = threading.Thread(target=self._stream_output, args=(self.primary_process, engine_name), daemon=True)
            t.start()

            # Check if process is still running after 1 second
            time.sleep(1.0)
            if self.primary_process.poll() is not None:
                ret = self.primary_process.returncode
                raise RuntimeError(f"Engine process exited immediately with code {ret}")

            # Apply System Mode
            if settings.mode == "proxy":
                self.log(f"Configuring Windows System Proxy (HTTP: {settings.http_port})...")
                enable_system_proxy(http_port=settings.http_port, socks_port=settings.socks_port)
            elif settings.mode == "tun":
                self.log("TUN mode enabled.")

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
        if self.primary_process:
            try:
                self.primary_process.terminate()
                self.primary_process.wait(timeout=2)
            except Exception:
                try:
                    self.primary_process.kill()
                except Exception:
                    pass
            self.primary_process = None

        if self.secondary_process:
            try:
                self.secondary_process.terminate()
                self.secondary_process.wait(timeout=2)
            except Exception:
                try:
                    self.secondary_process.kill()
                except Exception:
                    pass
            self.secondary_process = None

        # Clean up system proxy
        disable_system_proxy()
        self.status = "disconnected"
        self.current_node = None
        self.start_time = 0
        self.log("Disconnected and system proxy disabled.")

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
