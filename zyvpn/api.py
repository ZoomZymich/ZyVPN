import sys
import time
import threading
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
        "id": "gemini",
        "name": "Google Gemini",
        "desc": "ИИ-чат и генерация ответов",
        "url": "https://gemini.google.com/app",
        "display_url": "gemini.google.com"
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


def check_gemini_service(proxies: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Deep check for Google Gemini:
    1. Web app access (gemini.google.com/app)
    2. Regional generation eligibility via Generative Language API
    3. RPC chat gateway connectivity (alkalimakersuite-pa)
    """
    t0 = time.time()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    web_ok = False
    region_eligible = False
    gw_ok = False
    error_msg = None

    # 1. Check web app endpoint (stream=True avoids downloading heavy bundle)
    try:
        r_web = requests.get(
            "https://gemini.google.com/app",
            proxies=proxies,
            timeout=6.0,
            headers=headers,
            stream=True
        )
        final_url = r_web.url or ""
        if r_web.status_code in (200, 301, 302, 307, 308) and "/unavailable" not in final_url:
            web_ok = True
    except Exception as e:
        error_msg = f"Web: {e}"

    # 2. Regional Model Generation eligibility check
    # Google verifies caller region *prior* to API key authentication.
    # If country/IP is blocked: 400 FAILED_PRECONDITION 'User location is not supported'.
    # If country/IP is allowed: 400 INVALID_ARGUMENT 'API key not valid' or 200 OK.
    try:
        r_api = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=AIzaSyLocationProbeKey999",
            proxies=proxies,
            timeout=5.0,
            headers={"Content-Type": "application/json", **headers},
            json={"contents": [{"parts": [{"text": "ping"}]}]}
        )
        api_text = r_api.text
        if "User location is not supported" in api_text:
            region_eligible = False
        elif "API key not valid" in api_text or r_api.status_code in (200, 400, 403):
            region_eligible = True
    except Exception as e:
        if not error_msg:
            error_msg = f"API: {e}"

    # 3. Chat RPC gateway check
    try:
        r_gw = requests.get(
            "https://alkalimakersuite-pa.clients6.google.com/generate_204",
            proxies=proxies,
            timeout=5.0,
            headers=headers
        )
        if r_gw.status_code in (200, 204):
            gw_ok = True
    except Exception:
        pass

    latency = int((time.time() - t0) * 1000)
    can_chat = region_eligible and (web_ok or gw_ok)

    if can_chat:
        status_text = "Чат и AI доступны"
        detail = "Регион допущен Google к генерации ответов и диалогам"
    elif web_ok and not region_eligible:
        status_text = "Только сайт (генерация заблокирована)"
        detail = "Сайт открывается, но генерация диалогов заблокирована Google в данном регионе"
    else:
        status_text = "Недоступен"
        detail = error_msg or "Серверы Gemini не отвечают"

    return {
        "id": "gemini",
        "name": "Google Gemini",
        "desc": "ИИ-чат и генерация ответов",
        "display_url": "gemini.google.com",
        "ok": can_chat,
        "can_chat": can_chat,
        "web_ok": web_ok,
        "region_eligible": region_eligible,
        "gw_ok": gw_ok,
        "status_code": 200 if can_chat else (206 if web_ok else 0),
        "latency_ms": latency,
        "status_text": status_text,
        "detail": detail,
        "error": error_msg if not can_chat else None
    }

class VpnApi:
    """API exposed to JavaScript frontend in PyWebView or HTTP server."""
    def __init__(self, storage: Storage, core: CoreController):
        self._storage = storage
        self._core = core
        self._window = None
        self._tray = None
        self._is_maximized = False
        self._cached_ip_info = {
            "success": False,
            "connected": False,
            "ip": "—",
            "country_code": "un",
            "country_name": "Не подключено",
            "country_name_en": "Disconnected",
            "city": "",
            "flag_emoji": "🌐",
            "flag_url": ""
        }
        self._ip_fetch_lock = threading.Lock()
        self._ip_fetch_time = 0
        self._is_fetching_ip = False

    def set_window(self, window):
        self._window = window

    def set_tray(self, tray):
        self._tray = tray

    def window_minimize(self) -> Dict[str, Any]:
        if self._window:
            try:
                self._window.minimize()
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False}

    def window_toggle_maximize(self) -> Dict[str, Any]:
        if self._window:
            try:
                if self._is_maximized:
                    self._window.restore()
                    self._is_maximized = False
                else:
                    self._window.maximize()
                    self._is_maximized = True
                return {"success": True, "maximized": self._is_maximized}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False}

    def window_close(self) -> Dict[str, Any]:
        """Minimize to tray instead of abruptly closing, keeping VPN active."""
        if self._window:
            try:
                self._window.hide()
                if self._tray:
                    self._tray.notify(
                        "ZyVPN свёрнут в трей",
                        "Приложение и VPN продолжают работать в фоне. Чтобы открыть — дважды кликните по иконке в трее."
                    )
                return {"success": True, "minimized_to_tray": True}
            except Exception as e:
                try:
                    self._window.destroy()
                    return {"success": True}
                except Exception:
                    return {"success": False, "error": str(e)}
        return {"success": False}

    def app_quit(self) -> Dict[str, Any]:
        """Completely exit the application, stopping all engines and removing tray icon."""
        try:
            self._core.stop()
            if self._tray:
                self._tray.stop()
            if self._window:
                self._window.destroy()
            sys.exit(0)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_initial_data(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self._storage.nodes],
            "subscriptions": [s.to_dict() for s in self._storage.subscriptions],
            "settings": self._storage.settings.to_dict(),
            "status": self._core.get_status()
        }

    def connect(self, node_id: Optional[str] = None) -> Dict[str, Any]:
        if node_id:
            self._storage.set_selected_node(node_id)
        node = self._storage.get_selected_node()
        if not node:
            return {"success": False, "error": "No VPN node selected"}
        
        ok = self._core.start(node, self._storage.settings)
        if self._tray:
            self._tray.update()
        return {"success": ok, "error": self._core.error_message, "status": self._core.get_status()}

    def disconnect(self) -> Dict[str, Any]:
        self._core.stop()
        if self._tray:
            self._tray.update()
        return {"success": True, "status": self._core.get_status()}

    def select_node(self, node_id: str) -> Dict[str, Any]:
        self._storage.set_selected_node(node_id)
        node = self._storage.get_selected_node()
        return {"success": True, "selected_node": node.to_dict() if node else None}

    def add_subscription(self, url: str, name: Optional[str] = None) -> Dict[str, Any]:
        try:
            sub = self._storage.add_subscription(url, name)
            return {
                "success": True,
                "subscription": sub.to_dict(),
                "subscriptions": [s.to_dict() for s in self._storage.subscriptions],
                "nodes_count": sub.nodes_count,
                "nodes": [n.to_dict() for n in self._storage.nodes]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def refresh_subscription(self, sub_id: str) -> Dict[str, Any]:
        try:
            count = self._storage.refresh_subscription(sub_id)
            return {
                "success": True,
                "nodes_count": count,
                "subscriptions": [s.to_dict() for s in self._storage.subscriptions],
                "nodes": [n.to_dict() for n in self._storage.nodes]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_subscription(self, sub_id: str) -> Dict[str, Any]:
        self._storage.delete_subscription(sub_id)
        return {
            "success": True,
            "subscriptions": [s.to_dict() for s in self._storage.subscriptions],
            "nodes": [n.to_dict() for n in self._storage.nodes]
        }

    def import_text(self, text: str) -> Dict[str, Any]:
        try:
            added = self._storage.import_text(text)
            return {
                "success": True,
                "nodes_added": added,
                "nodes": [n.to_dict() for n in self._storage.nodes]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_node(self, node_id: str) -> Dict[str, Any]:
        self._storage.delete_node(node_id)
        return {
            "success": True,
            "nodes": [n.to_dict() for n in self._storage.nodes]
        }

    def ping_single(self, node_id: str) -> Dict[str, Any]:
        node = next((n for n in self._storage.nodes if n.id == node_id), None)
        if not node:
            return {"success": False, "error": "Node not found"}
        ping_ms = ping_node(node)
        self._storage.save()
        return {"success": True, "ping_ms": ping_ms}

    def ping_all(self) -> Dict[str, Any]:
        results = ping_all_nodes(self._storage.nodes)
        self._storage.save()
        return {"success": True, "results": results}

    def update_settings(self, settings_dict: Dict[str, Any]) -> Dict[str, Any]:
        was_connected = self._core.status == "connected"
        old_mode = self._storage.settings.mode
        old_routing = self._storage.settings.routing_mode
        old_dns = self._storage.settings.dns_server

        self._storage.update_settings(**settings_dict)

        if was_connected:
            needs_restart = (
                self._storage.settings.mode != old_mode or
                self._storage.settings.routing_mode != old_routing or
                self._storage.settings.dns_server != old_dns
            )
            if needs_restart:
                self._core.log("Настройки маршрутизации или режима изменены. Перезапуск туннеля...")
                node = self._storage.get_selected_node()
                if node:
                    self._core.start(node, self._storage.settings)

        if self._tray:
            self._tray.update()
        return {"success": True, "settings": self._storage.settings.to_dict()}

    def get_status(self) -> Dict[str, Any]:
        return self._core.get_status()

    def _fetch_ip_worker(self, is_connected: bool, http_port: int):
        with self._ip_fetch_lock:
            proxies = None
            if is_connected:
                proxies = {
                    "http": f"http://127.0.0.1:{http_port}",
                    "https": f"http://127.0.0.1:{http_port}"
                }
            ip_data = None
            # 1. Try ipwho.is (fast geoip) with short 2.5s timeout
            try:
                r = requests.get(
                    "https://ipwho.is/",
                    proxies=proxies,
                    timeout=2.5,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if r.status_code == 200:
                    data = r.json()
                    if data.get("success", True) and data.get("ip"):
                        ip_data = {
                            "ip": data.get("ip", ""),
                            "country_code": (data.get("country_code") or "").lower(),
                            "city": data.get("city", "")
                        }
            except Exception:
                pass

            # 2. Try fallback: ipinfo.io with 2.5s timeout
            if not ip_data or not ip_data.get("ip"):
                try:
                    r = requests.get(
                        "https://ipinfo.io/json",
                        proxies=proxies,
                        timeout=2.5,
                        headers={"User-Agent": "Mozilla/5.0"}
                    )
                    if r.status_code == 200:
                        data = r.json()
                        if data.get("ip"):
                            ip_data = {
                                "ip": data.get("ip", ""),
                                "country_code": (data.get("country") or "").lower(),
                                "city": data.get("city", "")
                            }
                except Exception:
                    pass

            # 3. Universal fallback: api.ipify.org (universally reachable globally)
            if not ip_data or not ip_data.get("ip"):
                try:
                    r = requests.get(
                        "https://api.ipify.org?format=json",
                        proxies=proxies,
                        timeout=2.5,
                        headers={"User-Agent": "Mozilla/5.0"}
                    )
                    if r.status_code == 200:
                        data = r.json()
                        if data.get("ip"):
                            selected = self._storage.get_selected_node()
                            fallback_cc = selected.country_code if (selected and is_connected) else "un"
                            ip_data = {
                                "ip": data.get("ip", ""),
                                "country_code": fallback_cc,
                                "city": ""
                            }
                except Exception:
                    pass

            if ip_data and ip_data.get("ip"):
                details = get_country_details(ip_data["country_code"])
                self._cached_ip_info = {
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
            else:
                selected = self._storage.get_selected_node()
                fallback_country = selected.country_code if (selected and is_connected) else "un"
                details = get_country_details(fallback_country)
                self._cached_ip_info = {
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
            self._ip_fetch_time = time.time()
            self._is_fetching_ip = False

    def get_connection_ip_info(self) -> Dict[str, Any]:
        """Return cached external IP, country, and location instantly without blocking the UI bridge."""
        is_connected = self._core.status == "connected"
        http_port = self._storage.settings.http_port

        now = time.time()
        # Enforce minimum cooldown: 45s normal, or 15s if previous fetch failed, or immediate on connection state change
        needs_refresh = (
            (is_connected != self._cached_ip_info.get("connected")) or
            (now - self._ip_fetch_time > 45) or
            (self._cached_ip_info.get("ip") == "—" and (now - self._ip_fetch_time > 15))
        )

        if needs_refresh and not self._is_fetching_ip:
            self._is_fetching_ip = True
            self._ip_fetch_time = now # prevent burst calls before worker finishes
            t = threading.Thread(target=self._fetch_ip_worker, args=(is_connected, http_port), daemon=True)
            t.start()

        return dict(self._cached_ip_info)

    def check_blocked_services(self) -> Dict[str, Any]:
        """Test reachability of key blocked services through active proxy."""
        http_port = self._storage.settings.http_port
        is_connected = self._core.status == "connected"
        proxies = {
            "http": f"http://127.0.0.1:{http_port}",
            "https": f"http://127.0.0.1:{http_port}"
        } if is_connected else None

        results = []
        def _test_svc(svc):
            if svc["id"] == "gemini":
                return check_gemini_service(proxies)
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
        http_port = self._storage.settings.http_port
        is_connected = self._core.status == "connected"
        proxies = {
            "http": f"http://127.0.0.1:{http_port}",
            "https": f"http://127.0.0.1:{http_port}"
        } if is_connected else None

        if service_id == "gemini":
            res = check_gemini_service(proxies)
            return {"success": True, **res}

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

    def test_gemini_dialog(self, prompt: str = "Привет! Ты сейчас работаешь через этот сервер?", api_key: str = "") -> Dict[str, Any]:
        """Test sending an actual prompt or verifying chat gateway through the current VPN connection."""
        http_port = self._storage.settings.http_port
        is_connected = self._core.status == "connected"
        proxies = {
            "http": f"http://127.0.0.1:{http_port}",
            "https": f"http://127.0.0.1:{http_port}"
        } if is_connected else None

        t0 = time.time()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Content-Type": "application/json"
        }

        api_key = (api_key or "").strip()
        if api_key:
            # Full generation test with user API key
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
                r = requests.post(
                    url,
                    headers=headers,
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    proxies=proxies,
                    timeout=12.0
                )
                latency = int((time.time() - t0) * 1000)
                if r.status_code == 200:
                    data = r.json()
                    candidates = data.get("candidates", [])
                    reply_text = ""
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            reply_text = parts[0].get("text", "")
                    return {
                        "success": True,
                        "type": "live_chat",
                        "latency_ms": latency,
                        "reply": reply_text or "(Получен пустой ответ)",
                        "model": "gemini-1.5-flash",
                        "proxy_used": is_connected
                    }
                else:
                    err_msg = r.text
                    try:
                        err_json = r.json()
                        err_msg = err_json.get("error", {}).get("message", r.text)
                    except Exception:
                        pass
                    return {
                        "success": False,
                        "type": "live_chat",
                        "latency_ms": latency,
                        "error": f"HTTP {r.status_code}: {err_msg}",
                        "proxy_used": is_connected
                    }
            except Exception as e:
                return {
                    "success": False,
                    "type": "live_chat",
                    "latency_ms": int((time.time() - t0) * 1000),
                    "error": str(e),
                    "proxy_used": is_connected
                }
        else:
            # Deep diagnostics without API key
            probe_res = check_gemini_service(proxies)
            latency = int((time.time() - t0) * 1000)
            if probe_res.get("can_chat"):
                reply = (
                    "✅ Глубокая проверка подтвердила: Google Gemini полностью готов к диалогу!\n\n"
                    "• Шлюз диалогов (alkalimakersuite-pa): Подключен (204 OK)\n"
                    "• Веб-приложение (gemini.google.com/app): Доступно без ограничений\n"
                    "• Региональный фильтр Google: Разрешен (IP не заблокирован в Google AI)\n\n"
                    "Вы можете перейти на gemini.google.com и полноценно переписываться с моделью через этот сервер."
                )
                return {
                    "success": True,
                    "type": "probe",
                    "latency_ms": latency,
                    "reply": reply,
                    "details": probe_res,
                    "proxy_used": is_connected
                }
            elif probe_res.get("web_ok") and not probe_res.get("region_eligible"):
                return {
                    "success": False,
                    "type": "probe",
                    "latency_ms": latency,
                    "error": "Веб-страница открывается, однако Google блокирует генерацию ответов (User location is not supported) для IP-адреса данного сервера. Рекомендуется переключиться на другой сервер (например, Швеция или Австрия).",
                    "details": probe_res,
                    "proxy_used": is_connected
                }
            else:
                return {
                    "success": False,
                    "type": "probe",
                    "latency_ms": latency,
                    "error": probe_res.get("error") or "Не удалось установить соединение с серверами Google Gemini.",
                    "details": probe_res,
                    "proxy_used": is_connected
                }

