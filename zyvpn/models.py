import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List

@dataclass
class VpnNode:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    sub_id: str = "manual"
    name: str = "VPN Server"
    protocol: str = "vless"           # vless, vmess, trojan, shadowsocks, hysteria2, tuic, wireguard
    server: str = ""
    port: int = 443
    uuid: str = ""                    # uuid or password or auth
    transport: str = "tcp"            # tcp, ws, grpc, xhttp, splithttp, httpupgrade, quic
    transport_settings: Dict[str, Any] = field(default_factory=dict)
    # For XHTTP: {"path": "/...", "host": "...", "mode": "auto", "extra": {...}}
    security: str = "none"            # none, tls, reality
    security_settings: Dict[str, Any] = field(default_factory=dict)
    # For Reality: {"sni": "...", "pbk": "...", "sid": "...", "fp": "chrome", "spx": "..."}
    flow: str = ""                    # xtls-rprx-vision
    ping_ms: Optional[int] = None
    raw_link: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VpnNode":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Subscription:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "My Subscription"
    url: str = ""
    last_updated: str = ""
    nodes_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subscription":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AppSettings:
    mode: str = "proxy"               # "tun" (full VPN) or "proxy" (system proxy)
    routing_mode: str = "bypass_ru_lan" # "bypass_ru_lan" (auto bypass Russian sites & LAN) or "global" (everything via VPN)
    socks_port: int = 10808
    http_port: int = 10809
    selected_node_id: Optional[str] = None
    auto_connect: bool = False
    dns_server: str = "1.1.1.1"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppSettings":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
