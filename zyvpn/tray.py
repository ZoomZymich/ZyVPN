import os
import sys
import threading
from typing import Optional, Callable
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item, Menu

def create_shield_image(connected: bool = False) -> Image.Image:
    """Generate high-resolution shield icon for Windows System Tray."""
    img = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Green when connected, Indigo when disconnected
    accent = (16, 185, 129, 255) if connected else (99, 102, 241, 255)
    bg = (15, 23, 42, 255)

    # Outer shield
    draw.polygon([(32, 4), (58, 14), (58, 36), (32, 60), (6, 36), (6, 14)], fill=accent)
    # Inner dark cut
    draw.polygon([(32, 11), (51, 19), (51, 34), (32, 53), (13, 34), (13, 19)], fill=bg)
    # Inner emblem
    draw.polygon([(32, 18), (44, 24), (44, 33), (32, 45), (20, 33), (20, 24)], fill=accent)
    return img

class TrayController:
    def __init__(self, api, on_show_window: Callable, on_exit: Callable):
        self.api = api
        self.on_show_window = on_show_window
        self.on_exit = on_exit
        self.icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

    def _get_status_text(self) -> str:
        st = self.api._core.status
        if st == "connected":
            node = self.api._core.current_node
            name = node.name if node else "Сервер"
            return f"Подключено: {name}"
        elif st == "connecting":
            return "Подключение..."
        else:
            return "Отключено"

    def _is_connected(self) -> bool:
        return self.api._core.status == "connected"

    def _is_tun_mode(self) -> bool:
        return self.api._storage.settings.mode == "tun"

    def _is_proxy_mode(self) -> bool:
        return self.api._storage.settings.mode == "proxy"

    def _is_bypass_ru(self) -> bool:
        return self.api._storage.settings.routing_mode == "bypass_ru_lan"

    def _is_global(self) -> bool:
        return self.api._storage.settings.routing_mode == "global"

    def _action_toggle_connect(self, icon, item):
        if self._is_connected():
            self.api.disconnect()
        else:
            selected_id = self.api._storage.settings.selected_node_id
            self.api.connect(selected_id)
        self.update()

    def _action_set_mode_tun(self, icon, item):
        self.api.update_settings({"mode": "tun"})
        self.update()

    def _action_set_mode_proxy(self, icon, item):
        self.api.update_settings({"mode": "proxy"})
        self.update()

    def _action_set_routing_bypass(self, icon, item):
        self.api.update_settings({"routing_mode": "bypass_ru_lan"})
        self.update()

    def _action_set_routing_global(self, icon, item):
        self.api.update_settings({"routing_mode": "global"})
        self.update()

    def _action_show(self, icon, item):
        if self.on_show_window:
            self.on_show_window()

    def _action_exit(self, icon, item):
        if self.icon:
            self.icon.stop()
        if self.on_exit:
            self.on_exit()

    def _build_menu(self) -> Menu:
        status_label = f"ZyVPN: {self._get_status_text()}"
        toggle_label = "Отключить" if self._is_connected() else "Подключить"

        return Menu(
            item(status_label, lambda icon, item: None, enabled=False),
            item(toggle_label, self._action_toggle_connect),
            Menu.SEPARATOR,
            item(
                "Режим: VPN на весь ПК (TUN)",
                self._action_set_mode_tun,
                checked=lambda item: self._is_tun_mode()
            ),
            item(
                "Режим: Системный прокси",
                self._action_set_mode_proxy,
                checked=lambda item: self._is_proxy_mode()
            ),
            Menu.SEPARATOR,
            item(
                "Маршрут: Обход РФ и LAN",
                self._action_set_routing_bypass,
                checked=lambda item: self._is_bypass_ru()
            ),
            item(
                "Маршрут: Весь трафик (Global)",
                self._action_set_routing_global,
                checked=lambda item: self._is_global()
            ),
            Menu.SEPARATOR,
            item("Открыть окно ZyVPN", self._action_show, default=True),
            item("Выход (закрыть полностью)", self._action_exit)
        )

    def start(self):
        """Start tray icon in background thread."""
        img = create_shield_image(connected=self._is_connected())
        self.icon = pystray.Icon(
            name="ZyVPN",
            icon=img,
            title="ZyVPN",
            menu=self._build_menu()
        )
        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()

    def update(self):
        """Update tray menu state and icon image."""
        if self.icon:
            try:
                self.icon.icon = create_shield_image(connected=self._is_connected())
                self.icon.title = f"ZyVPN - {self._get_status_text()}"
                self.icon.menu = self._build_menu()
            except Exception:
                pass

    def notify(self, title: str, message: str):
        """Display Windows tray balloon notification."""
        if self.icon:
            try:
                self.icon.notify(message, title)
            except Exception:
                pass

    def stop(self):
        """Cleanly stop tray icon."""
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
