import os
import json
import time
from typing import List, Optional, Dict, Any
from .models import VpnNode, Subscription, AppSettings
from .parser import fetch_and_parse_subscription, parse_single_link, parse_subscription_content

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

class Storage:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.settings: AppSettings = AppSettings()
        self.subscriptions: List[Subscription] = []
        self.nodes: List[VpnNode] = []
        self.load()

    def load(self):
        if not os.path.exists(CONFIG_FILE):
            self.save()
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.settings = AppSettings.from_dict(data.get("settings", {}))
            self.subscriptions = [Subscription.from_dict(s) for s in data.get("subscriptions", [])]
            self.nodes = [VpnNode.from_dict(n) for n in data.get("nodes", [])]
        except Exception as e:
            print(f"Error loading config.json: {e}")

    def save(self):
        data = {
            "settings": self.settings.to_dict(),
            "subscriptions": [s.to_dict() for s in self.subscriptions],
            "nodes": [n.to_dict() for n in self.nodes]
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_subscription(self, url: str, name: Optional[str] = None) -> Subscription:
        url = url.strip()
        sub = Subscription(
            name=name or f"Sub-{len(self.subscriptions) + 1}",
            url=url,
            last_updated=time.strftime("%Y-%m-%d %H:%M")
        )
        self.subscriptions.append(sub)
        self.refresh_subscription(sub.id)
        return sub

    def refresh_subscription(self, sub_id: str) -> int:
        sub = next((s for s in self.subscriptions if s.id == sub_id), None)
        if not sub:
            return 0
        try:
            new_nodes = fetch_and_parse_subscription(sub.url, sub_id=sub.id)
            # Remove old nodes from this sub
            self.nodes = [n for n in self.nodes if n.sub_id != sub.id]
            self.nodes.extend(new_nodes)
            sub.nodes_count = len(new_nodes)
            sub.last_updated = time.strftime("%Y-%m-%d %H:%M")
            self.save()
            return len(new_nodes)
        except Exception as e:
            print(f"Failed to refresh subscription {sub.name}: {e}")
            raise

    def delete_subscription(self, sub_id: str):
        self.subscriptions = [s for s in self.subscriptions if s.id != sub_id]
        self.nodes = [n for n in self.nodes if n.sub_id != sub_id]
        if self.settings.selected_node_id and not any(n.id == self.settings.selected_node_id for n in self.nodes):
            self.settings.selected_node_id = self.nodes[0].id if self.nodes else None
        self.save()

    def import_text(self, text: str) -> int:
        """Import nodes from text (can be single link or multi-line base64 / YAML)."""
        nodes = parse_subscription_content(text, sub_id="manual")
        count = 0
        for n in nodes:
            # avoid exact duplicates
            if not any(existing.server == n.server and existing.port == n.port and existing.uuid == n.uuid for existing in self.nodes):
                self.nodes.append(n)
                count += 1
        if count > 0:
            if not self.settings.selected_node_id and self.nodes:
                self.settings.selected_node_id = self.nodes[0].id
            self.save()
        return count

    def delete_node(self, node_id: str):
        self.nodes = [n for n in self.nodes if n.id != node_id]
        if self.settings.selected_node_id == node_id:
            self.settings.selected_node_id = self.nodes[0].id if self.nodes else None
        self.save()

    def get_selected_node(self) -> Optional[VpnNode]:
        if not self.settings.selected_node_id:
            if self.nodes:
                self.settings.selected_node_id = self.nodes[0].id
                return self.nodes[0]
            return None
        return next((n for n in self.nodes if n.id == self.settings.selected_node_id), None)

    def set_selected_node(self, node_id: str):
        if any(n.id == node_id for n in self.nodes):
            self.settings.selected_node_id = node_id
            self.save()

    def update_settings(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self.settings, k):
                setattr(self.settings, k, v)
        self.save()
