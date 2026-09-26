import json
import os
from typing import Dict, Any, Tuple
from .models import VpnNode, AppSettings

RU_DOMAINS = [
    "geosite:category-ru",
    "domain:ru",
    "domain:su",
    "domain:xn--p1ai",
    "domain:yandex.ru",
    "domain:ya.ru",
    "domain:vk.com",
    "domain:gosuslugi.ru",
    "domain:sberbank.ru",
    "domain:tinkoff.ru",
    "domain:ozon.ru",
    "domain:wildberries.ru",
    "domain:avito.ru",
    "domain:mos.ru",
    "domain:nalog.gov.ru",
    "domain:kinopoisk.ru",
    "domain:mail.ru",
    "domain:dzen.ru",
    "domain:rutube.ru"
]

def generate_xray_config(node: VpnNode, settings: AppSettings) -> Dict[str, Any]:
    """Generate complete Xray-core JSON configuration for VLESS (incl. XHTTP over TCP), VMess, Trojan, SS."""
    inbounds = [
        {
            "tag": "socks-in",
            "port": settings.socks_port,
            "listen": "127.0.0.1",
            "protocol": "socks",
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls", "quic"],
                "routeOnly": True
            },
            "settings": {
                "auth": "noauth",
                "udp": True
            }
        },
        {
            "tag": "http-in",
            "port": settings.http_port,
            "listen": "127.0.0.1",
            "protocol": "http",
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls"],
                "routeOnly": True
            },
            "settings": {
                "allowTransparent": False
            }
        }
    ]

    # Primary proxy outbound
    outbound_proxy: Dict[str, Any] = {
        "tag": "proxy"
    }

    if node.protocol == "vless":
        outbound_proxy["protocol"] = "vless"
        user_obj = {
            "id": node.uuid,
            "encryption": "none"
        }
        if node.flow:
            user_obj["flow"] = node.flow
        outbound_proxy["settings"] = {
            "vnext": [{
                "address": node.server,
                "port": node.port,
                "users": [user_obj]
            }]
        }
    elif node.protocol == "vmess":
        outbound_proxy["protocol"] = "vmess"
        outbound_proxy["settings"] = {
            "vnext": [{
                "address": node.server,
                "port": node.port,
                "users": [{
                    "id": node.uuid,
                    "alterId": 0,
                    "security": "auto"
                }]
            }]
        }
    elif node.protocol == "trojan":
        outbound_proxy["protocol"] = "trojan"
        outbound_proxy["settings"] = {
            "servers": [{
                "address": node.server,
                "port": node.port,
                "password": node.uuid
            }]
        }
    elif node.protocol == "shadowsocks":
        outbound_proxy["protocol"] = "shadowsocks"
        method = node.transport_settings.get("method", "aes-256-gcm")
        outbound_proxy["settings"] = {
            "servers": [{
                "address": node.server,
                "port": node.port,
                "method": method,
                "password": node.uuid
            }]
        }

    # Stream Settings (Transport + Security)
    stream_settings: Dict[str, Any] = {}
    network = node.transport
    if network in ("splithttp", "xhttp"):
        network = "xhttp"
    stream_settings["network"] = network

    # Security: reality / tls / none
    if node.security == "reality":
        stream_settings["security"] = "reality"
        stream_settings["realitySettings"] = {
            "show": False,
            "fingerprint": node.security_settings.get("fp", "chrome"),
            "serverName": node.security_settings.get("sni", node.server),
            "publicKey": node.security_settings.get("pbk", ""),
            "shortId": node.security_settings.get("sid", ""),
            "spiderX": node.security_settings.get("spx", "/")
        }
    elif node.security == "tls":
        stream_settings["security"] = "tls"
        stream_settings["tlsSettings"] = {
            "serverName": node.security_settings.get("sni", node.server),
            "fingerprint": node.security_settings.get("fp", "chrome"),
            "allowInsecure": node.security_settings.get("allowInsecure", False),
            "alpn": node.security_settings.get("alpn", ["h2", "http/1.1"])
        }
    else:
        stream_settings["security"] = "none"

    # Transport settings: xhttp / ws / grpc / httpupgrade / tcp
    if network == "xhttp":
        stream_settings["xhttpSettings"] = {
            "path": node.transport_settings.get("path", "/"),
            "host": node.transport_settings.get("host", node.security_settings.get("sni", "")),
            "mode": node.transport_settings.get("mode", "auto")
        }
        if "extra" in node.transport_settings:
            stream_settings["xhttpSettings"]["extra"] = node.transport_settings["extra"]
    elif network == "ws":
        stream_settings["wsSettings"] = {
            "path": node.transport_settings.get("path", "/"),
            "headers": {
                "Host": node.transport_settings.get("host", node.security_settings.get("sni", ""))
            }
        }
    elif network == "grpc":
        stream_settings["grpcSettings"] = {
            "serviceName": node.transport_settings.get("serviceName", ""),
            "multiMode": node.transport_settings.get("mode", "") == "multi"
        }
    elif network == "httpupgrade":
        stream_settings["httpupgradeSettings"] = {
            "path": node.transport_settings.get("path", "/"),
            "host": node.transport_settings.get("host", node.security_settings.get("sni", ""))
        }

    outbound_proxy["streamSettings"] = stream_settings

    # Outbounds list
    outbounds = [
        outbound_proxy,
        {
            "tag": "direct",
            "protocol": "freedom",
            "settings": {
                "domainStrategy": "UseIP"
            }
        },
        {
            "tag": "block",
            "protocol": "blackhole",
            "settings": {
                "response": {
                    "type": "http"
                }
            }
        }
    ]

    # Routing rules (Auto-Routing)
    routing_rules = [
        {
            "type": "field",
            "outboundTag": "direct",
            "ip": ["geoip:private"]
        }
    ]

    if settings.routing_mode == "bypass_ru_lan":
        # Bypass Russian sites, services and IPs
        routing_rules.append({
            "type": "field",
            "outboundTag": "direct",
            "domain": RU_DOMAINS
        })
        routing_rules.append({
            "type": "field",
            "outboundTag": "direct",
            "ip": ["geoip:ru"]
        })

    # Default rule: everything else through proxy
    routing_rules.append({
        "type": "field",
        "outboundTag": "proxy",
        "network": "tcp,udp"
    })

    config = {
        "log": {
            "loglevel": "warning"
        },
        "dns": {
            "servers": [
                settings.dns_server,
                "8.8.8.8",
                "localhost"
            ]
        },
        "inbounds": inbounds,
        "outbounds": outbounds,
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "rules": routing_rules
        }
    }
    return config

def generate_singbox_config(node: VpnNode, settings: AppSettings, enable_tun: bool = False) -> Dict[str, Any]:
    """Generate Sing-box JSON configuration for Hysteria 2, TUIC, or TUN mode."""
    inbounds = [
        {
            "type": "mixed",
            "tag": "mixed-in",
            "listen": "127.0.0.1",
            "listen_port": settings.socks_port,
            "sniff": True
        }
    ]

    if enable_tun:
        inbounds.append({
            "type": "tun",
            "tag": "tun-in",
            "interface_name": "zyvpn-tun",
            "address": ["172.19.0.1/30"],
            "auto_route": True,
            "strict_route": True,
            "stack": "mixed",
            "sniff": True
        })

    outbounds = []

    if node.protocol == "hysteria2":
        ob = {
            "type": "hysteria2",
            "tag": "proxy",
            "server": node.server,
            "server_port": node.port,
            "password": node.uuid,
            "tls": {
                "enabled": True,
                "server_name": node.security_settings.get("sni", node.server),
                "insecure": node.security_settings.get("insecure", False)
            }
        }
        obfs = node.transport_settings.get("obfs")
        if obfs:
            ob["obfs"] = {
                "type": obfs,
                "password": node.transport_settings.get("obfs-password", "")
            }
        outbounds.append(ob)
    elif node.protocol == "tuic":
        outbounds.append({
            "type": "tuic",
            "tag": "proxy",
            "server": node.server,
            "server_port": node.port,
            "uuid": node.uuid,
            "password": node.transport_settings.get("password", ""),
            "congestion_control": node.transport_settings.get("congestion_control", "bbr"),
            "udp_relay_mode": node.transport_settings.get("udp_relay_mode", "native"),
            "tls": {
                "enabled": True,
                "server_name": node.security_settings.get("sni", node.server),
                "alpn": node.security_settings.get("alpn", ["h3"]),
                "insecure": node.security_settings.get("allowInsecure", False)
            }
        })
    elif node.protocol in ("vless", "vmess", "trojan", "shadowsocks"):
        # When using Sing-box TUN to route through local Xray-core SOCKS5
        outbounds.append({
            "type": "socks",
            "tag": "proxy",
            "server": "127.0.0.1",
            "server_port": settings.socks_port
        })

    outbounds.append({"type": "direct", "tag": "direct"})
    outbounds.append({"type": "block", "tag": "block"})

    route_rules = [
        {"ip_is_private": True, "outbound": "direct"}
    ]
    if settings.routing_mode == "bypass_ru_lan":
        route_rules.append({
            "geosite": ["category-ru"],
            "outbound": "direct"
        })
        route_rules.append({
            "geoip": ["ru"],
            "outbound": "direct"
        })

    config = {
        "log": {"level": "warn"},
        "dns": {
            "servers": [
                {"tag": "remote-dns", "address": "https://1.1.1.1/dns-query", "detour": "proxy"},
                {"tag": "local-dns", "address": "77.88.8.8", "detour": "direct"}
            ]
        },
        "inbounds": inbounds,
        "outbounds": outbounds,
        "route": {
            "rules": route_rules,
            "final": "proxy",
            "auto_detect_interface": True
        }
    }
    return config

def select_engine_and_generate_config(node: VpnNode, settings: AppSettings) -> Tuple[str, Dict[str, Any]]:
    """Determine whether to run Xray or Sing-box and generate the config."""
    if node.protocol in ("hysteria2", "tuic"):
        return "sing-box", generate_singbox_config(node, settings, enable_tun=(settings.mode == "tun"))
    else:
        return "xray", generate_xray_config(node, settings)
