import time
import requests
import concurrent.futures
from typing import Dict, Any, Optional, List
from .storage import Storage
from .core import CoreController
from .ping import ping_node, ping_all_nodes
from .countries import get_country_details

CHECK_SERVICES = [
    {
        "id": "discord",
        "name": "Discord",
        "desc": "Голосовые каналы и чаты",
        "url": "https://discord.com/api/v9/gateway",
        "display_url": "discord.com"
    },
    {
        "id": "telegram",
        "name": "Telegram",
        "desc": "Мессенджер и каналы",
        "url": "https://web.telegram.org",
        "display_url": "web.telegram.org"
    },
    {
        "id": "youtube",
        "name": "YouTube",
        "desc": "Видеохостинг и стримы",
        "url": "https://www.youtube.com/generate_204",
        "display_url": "youtube.com"
    },
    {
        "id": "instagram",
        "name": "Instagram",
        "desc": "Фото, Reels, Stories (Meta)",
        "url": "https://www.instagram.com",
        "display_url": "instagram.com"
    },
    {
        "id": "x",
        "name": "Twitter / X",
        "desc": "Социальная сеть X",
        "url": "https://x.com",
        "display_url": "x.com"
    },
    {
        "id": "chatgpt",
        "name": "ChatGPT",
        "desc": "Нейросеть OpenAI",
        "url": "https://chatgpt.com",
        "display_url": "chatgpt.com"
    },
    {
        "id": "spotify",
        "name": "Spotify",
        "desc": "Музыкальный стриминг",
        "url": "https://www.spotify.com",
        "display_url": "spotify.com"
    },
    {
        "id": "wikipedia",
        "name": "Wikipedia",
        "desc": "Свободная энциклопедия",
        "url": "https://en.wikipedia.org",
        "display_url": "wikipedia.org"
    }
]

class VpnApi:
    """API exposed to JavaScript frontend in PyWebView or HTTP server."""
    def __init__(self, storage: Storage, core: CoreController):
        self.storage = storage
        self.core = core
        self.window = None
        self._is_maximized = False

    def set_window(self, window):
        self.window = window

    def window_minimize(self) -> Dict[str, Any]:
        if self.window:
            try:
                self.window.minimize()
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False}

    def window_toggle_maximize(self) -> Dict[str, Any]:
        if self.window:
            try:
                if self._is_maximized:
                    self.window.restore()
                    self._is_maximized = False
                else:
                    self.window.maximize()
                    self._is_maximized = True
                return {"success": True, "maximized": self._is_maximized}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False}

    def window_close(self) -> Dict[str, Any]:
        if self.window:
            try:
                self.window.destroy()
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False}

    def get_initial_data(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.storage.nodes],
            "subscriptions": [s.to_dict() for s in self.storage.subscriptions],
            "settings": self.storage.settings.to_dict(),
            "status": self.core.get_status()
        }

    def connect(self, node_id: Optional[str] = None) -> Dict[str, Any]:
        if node_id:
            self.storage.set_selected_node(node_id)
        node = self.storage.get_selected_node()
        if not node:
            return {"success": False, "error": "No VPN node selected"}
        
        ok = self.core.start(node, self.storage.settings)
        return {"success": ok, "error": self.core.error_message, "status": self.core.get_status()}

    def disconnect(self) -> Dict[str, Any]:
        self.core.stop()
        return {"success": True, "status": self.core.get_status()}

    def select_node(self, node_id: str) -> Dict[str, Any]:
        self.storage.set_selected_node(node_id)
        node = self.storage.get_selected_node()
        return {"success": True, "selected_node": node.to_dict() if node else None}

    def add_subscription(self, url: str, name: Optional[str] = None) -> Dict[str, Any]:
        try:
            sub = self.storage.add_subscription(url, name)
            return {
                "success": True,
                "subscription": sub.to_dict(),
                "nodes_count": sub.nodes_count,
                "nodes": [n.to_dict() for n in self.storage.nodes]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def refresh_subscription(self, sub_id: str) -> Dict[str, Any]:
        try:
            count = self.storage.refresh_subscription(sub_id)
            return {
                "success": True,
                "nodes_count": count,
                "subscriptions": [s.to_dict() for s in self.storage.subscriptions],
                "nodes": [n.to_dict() for n in self.storage.nodes]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_subscription(self, sub_id: str) -> Dict[str, Any]:
        self.storage.delete_subscription(sub_id)
        return {
            "success": True,
            "subscriptions": [s.to_dict() for s in self.storage.subscriptions],
            "nodes": [n.to_dict() for n in self.storage.nodes]
        }

    def import_text(self, text: str) -> Dict[str, Any]:
        try:
            added = self.storage.import_text(text)
            return {
                "success": True,
                "nodes_added": added,
                "nodes": [n.to_dict() for n in self.storage.nodes]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_node(self, node_id: str) -> Dict[str, Any]:
        self.storage.delete_node(node_id)
        return {
            "success": True,
            "nodes": [n.to_dict() for n in self.storage.nodes]
        }

    def ping_single(self, node_id: str) -> Dict[str, Any]:
        node = next((n for n in self.storage.nodes if n.id == node_id), None)
        if not node:
            return {"success": False, "error": "Node not found"}
        ping_ms = ping_node(node)
        self.storage.save()
        return {"success": True, "ping_ms": ping_ms}

    def ping_all(self) -> Dict[str, Any]:
        results = ping_all_nodes(self.storage.nodes)
        self.storage.save()
        return {"success": True, "results": results}

    def update_settings(self, settings_dict: Dict[str, Any]) -> Dict[str, Any]:
        self.storage.update_settings(**settings_dict)
        return {"success": True, "settings": self.storage.settings.to_dict()}

    def get_status(self) -> Dict[str, Any]:
        return self.core.get_status()

    def get_connection_ip_info(self) -> Dict[str, Any]:
        """Fetch current external IP, country, and location through proxy or directly."""
        http_port = self.storage.settings.http_port
        is_connected = self.core.status == "connected"
        
        proxies = None
        if is_connected:
            proxies = {
                "http": f"http://127.0.0.1:{http_port}",
                "https": f"http://127.0.0.1:{http_port}"
            }
        
        # 1. Try ipwho.is (fast HTTPS geoip)
        ip_data = None
        try:
            r = requests.get(
                "https://ipwho.is/",
                proxies=proxies,
                timeout=5.0,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("success", True):
                    ip_data = {
                        "ip": data.get("ip", ""),
                        "country_code": (data.get("country_code") or "").lower(),
                        "city": data.get("city", "")
                    }
        except Exception:
            pass

        # 2. Try fallback: ipinfo.io
        if not ip_data or not ip_data.get("ip"):
            try:
                r = requests.get(
                    "https://ipinfo.io/json",
                    proxies=proxies,
                    timeout=5.0,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if r.status_code == 200:
                    data = r.json()
                    ip_data = {
                        "ip": data.get("ip", ""),
                        "country_code": (data.get("country") or "").lower(),
                        "city": data.get("city", "")
                    }
            except Exception:
                pass

        if ip_data and ip_data.get("ip"):
            details = get_country_details(ip_data["country_code"])
            return {
                "success": True,
                "connected": is_connected,
                "ip": ip_data["ip"],
                "country_code": details["country_code"],
                "country_name": details["name_ru"],
                "country_name_en": details["name_en"],
                "city": ip_data.get("city", ""),
                "flag_emoji": details["flag_emoji"],
                "flag_url": details["flag_url"]
            }

        # Fallback when lookup fails or disconnected
        selected = self.storage.get_selected_node()
        fallback_country = selected.country_code if (selected and is_connected) else "un"
        details = get_country_details(fallback_country)
        return {
            "success": False,
            "connected": is_connected,
            "ip": "—",
            "country_code": details["country_code"],
            "country_name": details["name_ru"] if is_connected else "Не подключено",
            "country_name_en": details["name_en"] if is_connected else "Disconnected",
            "city": "",
            "flag_emoji": details["flag_emoji"],
            "flag_url": details["flag_url"]
        }

    def check_blocked_services(self) -> Dict[str, Any]:
        """Test reachability of key blocked services through active proxy."""
        http_port = self.storage.settings.http_port
        is_connected = self.core.status == "connected"
        proxies = {
            "http": f"http://127.0.0.1:{http_port}",
            "https": f"http://127.0.0.1:{http_port}"
        } if is_connected else None

        results = []
        def _test_svc(svc):
            t0 = time.time()
            try:
                r = requests.get(
                    svc["url"],
                    proxies=proxies,
                    timeout=6.0,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                latency = int((time.time() - t0) * 1000)
                ok = r.status_code in (200, 204, 301, 302, 307, 308, 401, 403)
                return {
                    "id": svc["id"],
                    "name": svc["name"],
                    "desc": svc["desc"],
                    "display_url": svc["display_url"],
                    "ok": ok,
                    "status_code": r.status_code,
                    "latency_ms": latency
                }
            except Exception as e:
                latency = int((time.time() - t0) * 1000)
                return {
                    "id": svc["id"],
                    "name": svc["name"],
                    "desc": svc["desc"],
                    "display_url": svc["display_url"],
                    "ok": False,
                    "status_code": 0,
                    "latency_ms": latency,
                    "error": str(e)
                }

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_svc = {executor.submit(_test_svc, s): s for s in CHECK_SERVICES}
            for fut in concurrent.futures.as_completed(future_to_svc):
                results.append(fut.result())

        # Sort back into defined order
        id_order = {s["id"]: i for i, s in enumerate(CHECK_SERVICES)}
        results.sort(key=lambda x: id_order.get(x["id"], 99))

        return {
            "success": True,
            "connected": is_connected,
            "results": results
        }

    def check_single_service(self, service_id: str) -> Dict[str, Any]:
        """Test a single service by id."""
        svc = next((s for s in CHECK_SERVICES if s["id"] == service_id), None)
        if not svc:
            return {"success": False, "error": f"Service '{service_id}' not found"}
        http_port = self.storage.settings.http_port
        is_connected = self.core.status == "connected"
        proxies = {
            "http": f"http://127.0.0.1:{http_port}",
            "https": f"http://127.0.0.1:{http_port}"
        } if is_connected else None
        t0 = time.time()
        try:
            r = requests.get(
                svc["url"],
                proxies=proxies,
                timeout=6.0,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            latency = int((time.time() - t0) * 1000)
            ok = r.status_code in (200, 204, 301, 302, 307, 308, 401, 403)
            return {
                "success": True,
                "id": svc["id"],
                "name": svc["name"],
                "desc": svc["desc"],
                "display_url": svc["display_url"],
                "ok": ok,
                "status_code": r.status_code,
                "latency_ms": latency
            }
        except Exception as e:
            latency = int((time.time() - t0) * 1000)
            return {
                "success": True,
                "id": svc["id"],
                "name": svc["name"],
                "desc": svc["desc"],
                "display_url": svc["display_url"],
                "ok": False,
                "status_code": 0,
                "latency_ms": latency,
                "error": str(e)
            }

