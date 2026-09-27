import json
import os
from typing import Dict, Any, Tuple, Optional
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
                "routeOnly": False
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
                "routeOnly": False
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
                "domainStrategy": "AsIs"
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
            "ip": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8"]
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
        "inbounds": inbounds,
        "outbounds": outbounds,
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "rules": routing_rules
        }
    }
    return config

def generate_tun_helper_config(settings: AppSettings, node: Optional[VpnNode] = None) -> Dict[str, Any]:
    """Generate Sing-box TUN router configuration that captures all PC traffic (TCP & UDP) into local Xray SOCKS5."""
    dns_server = settings.dns_server or "1.1.1.1"

    ru_suffixes = [
        ".ru", ".su", ".xn--p1ai", "yandex.ru", "ya.ru", "vk.com",
        "gosuslugi.ru", "sberbank.ru", "tinkoff.ru", "ozon.ru",
        "wildberries.ru", "avito.ru", "mos.ru", "kinopoisk.ru",
        "mail.ru", "dzen.ru", "rutube.ru"
    ]

    # Rules are evaluated strictly in order top-to-bottom.
    # 1. CRITICAL: Process bypass MUST BE FIRST so xray and sing-box never loop into TUN!
    route_rules = [
        {"process_name": ["xray.exe", "xray", "sing-box.exe", "sing-box"], "outbound": "direct"},
        {"ip_cidr": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8"], "outbound": "direct"}
    ]
    dns_rules = []

    # 2. VPN server destination bypass (IP or domain)
    if node and node.server:
        import ipaddress
        is_ip = False
        try:
            ipaddress.ip_address(node.server)
            is_ip = True
        except ValueError:
            is_ip = False

        if is_ip:
            route_rules.append({"ip_cidr": [f"{node.server}/32"], "outbound": "direct"})
        else:
            route_rules.append({"domain": [node.server], "outbound": "direct"})
            dns_rules.append({"domain": [node.server], "server": "local-dns"})

    # 3. Russian traffic bypass (LAN & RU services)
    if settings.routing_mode == "bypass_ru_lan":
        route_rules.append({"domain_suffix": ru_suffixes, "outbound": "direct"})
        route_rules.append({"geosite": ["category-ru"], "outbound": "direct"})
        route_rules.append({"geoip": ["ru"], "outbound": "direct"})
        dns_rules.append({"domain_suffix": ru_suffixes, "server": "local-dns"})
        dns_rules.append({"geosite": ["category-ru"], "server": "local-dns"})

    # 4. Hijack DNS port 53 for all user applications (Discord, browsers, games)
    route_rules.append({"port": 53, "action": "hijack-dns"})

    # 5. Sniff protocols for domain extraction
    route_rules.append({"action": "sniff"})

    config = {
        "log": {"level": "warn"},
        "dns": {
            "servers": [
                {"tag": "remote-dns", "type": "udp", "server": dns_server, "detour": "proxy"},
                {"tag": "local-dns", "type": "udp", "server": "77.88.8.8", "detour": "direct"}
            ],
            "rules": dns_rules
        },
        "inbounds": [
            {
                "type": "tun",
                "tag": "tun-in",
                "interface_name": "zyvpn-tun",
                "address": ["172.19.0.1/30"],
                "auto_route": True,
                "strict_route": False,
                "stack": "mixed",
                "endpoint_independent_nat": True,
                "udp_timeout": 300
            }
        ],
        "outbounds": [
            {
                "type": "socks",
                "tag": "proxy",
                "server": "127.0.0.1",
                "server_port": settings.socks_port,
                "version": "5"
            },
            {"type": "direct", "tag": "direct"}
        ],
        "route": {
            "default_domain_resolver": "local-dns",
            "rules": route_rules,
            "final": "proxy",
            "auto_detect_interface": True
        }
    }
    return config


def generate_singbox_config(node: VpnNode, settings: AppSettings, enable_tun: bool = False) -> Dict[str, Any]:
    """Generate Sing-box JSON configuration for Hysteria 2 or TUIC."""
    dns_server = settings.dns_server or "1.1.1.1"

    inbounds = [
        {
            "type": "mixed",
            "tag": "mixed-in",
            "listen": "127.0.0.1",
            "listen_port": settings.socks_port
        }
    ]

    if enable_tun:
        inbounds.append({
            "type": "tun",
            "tag": "tun-in",
            "interface_name": "zyvpn-tun",
            "address": ["172.19.0.1/30"],
            "auto_route": True,
            "strict_route": False,
            "stack": "mixed",
            "endpoint_independent_nat": True,
            "udp_timeout": 300
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

    outbounds.append({"type": "direct", "tag": "direct"})

    ru_suffixes = [
        ".ru", ".su", ".xn--p1ai", "yandex.ru", "ya.ru", "vk.com",
        "gosuslugi.ru", "sberbank.ru", "tinkoff.ru", "ozon.ru",
        "wildberries.ru", "avito.ru", "mos.ru", "kinopoisk.ru",
        "mail.ru", "dzen.ru", "rutube.ru"
    ]

    route_rules = [
        {"process_name": ["sing-box.exe", "sing-box"], "outbound": "direct"},
        {"ip_cidr": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8"], "outbound": "direct"}
    ]
    dns_rules = []

    if node and node.server:
        import ipaddress
        is_ip = False
        try:
            ipaddress.ip_address(node.server)
            is_ip = True
        except ValueError:
            is_ip = False

        if is_ip:
            route_rules.append({"ip_cidr": [f"{node.server}/32"], "outbound": "direct"})
        else:
            route_rules.append({"domain": [node.server], "outbound": "direct"})
            dns_rules.append({"domain": [node.server], "server": "local-dns"})

    if settings.routing_mode == "bypass_ru_lan":
        route_rules.append({"domain_suffix": ru_suffixes, "outbound": "direct"})
        route_rules.append({"geosite": ["category-ru"], "outbound": "direct"})
        route_rules.append({"geoip": ["ru"], "outbound": "direct"})
        dns_rules.append({"domain_suffix": ru_suffixes, "server": "local-dns"})
        dns_rules.append({"geosite": ["category-ru"], "server": "local-dns"})

    route_rules.append({"port": 53, "action": "hijack-dns"})
    route_rules.append({"action": "sniff"})

    config = {
        "log": {"level": "warn"},
        "dns": {
            "servers": [
                {"tag": "remote-dns", "type": "udp", "server": dns_server, "detour": "proxy"},
                {"tag": "local-dns", "type": "udp", "server": "77.88.8.8", "detour": "direct"}
            ],
            "rules": dns_rules
        },
        "inbounds": inbounds,
        "outbounds": outbounds,
        "route": {
            "default_domain_resolver": "local-dns",
            "rules": route_rules,
            "final": "proxy",
            "auto_detect_interface": True
        }
    }
    return config


def select_engine_and_generate_config(node: VpnNode, settings: AppSettings) -> Tuple[str, Dict[str, Any], Optional[Tuple[str, Dict[str, Any]]]]:
    """Determine primary engine + config, and optional secondary helper engine (e.g. sing-box TUN helper)."""
    if node.protocol in ("hysteria2", "tuic"):
        # Sing-box natively handles Hysteria 2 / TUIC and TUN
        cfg = generate_singbox_config(node, settings, enable_tun=(settings.mode == "tun"))
        return "sing-box", cfg, None
    else:
        # Xray handles VLESS (Reality, XHTTP, Vision), VMess, Trojan, Shadowsocks
        xray_cfg = generate_xray_config(node, settings)
        tun_helper = None
        if settings.mode == "tun":
            # Sing-box runs as the TUN interface router, capturing whole-PC TCP/UDP into local Xray SOCKS5
            tun_cfg = generate_tun_helper_config(settings, node)
            tun_helper = ("sing-box", tun_cfg)
        return "xray", xray_cfg, tun_helper

