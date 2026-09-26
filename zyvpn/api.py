from typing import Dict, Any, Optional, List
from .storage import Storage
from .core import CoreController
from .ping import ping_node, ping_all_nodes

class VpnApi:
    """API exposed to JavaScript frontend in PyWebView or HTTP server."""
    def __init__(self, storage: Storage, core: CoreController):
        self.storage = storage
        self.core = core

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
