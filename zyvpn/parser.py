import base64
import json
import re
import urllib.parse
from typing import List, Optional, Dict, Any
import requests
import yaml
from .models import VpnNode, Subscription

def clean_b64_decode(text: str) -> str:
    """Robust Base64 decode handling missing padding and URL-safe characters."""
    text = text.strip()
    # Normalize URL safe base64
    text = text.replace('-', '+').replace('_', '/')
    missing_padding = len(text) % 4
    if missing_padding:
        text += '=' * (4 - missing_padding)
    try:
        return base64.b64decode(text.encode('utf-8')).decode('utf-8', errors='ignore')
    except Exception:
        try:
            return base64.b64decode(text.encode('latin1')).decode('utf-8', errors='ignore')
        except Exception:
            return ""

def parse_vless_url(url: str, sub_id: str = "manual") -> Optional[VpnNode]:
    """Parse vless:// link including Reality and XHTTP over TCP."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme.lower() != "vless":
            return None
        
        uuid_str = parsed.username or ""
        host = parsed.hostname or ""
        port = parsed.port or 443
        name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else f"VLESS-{host}:{port}"
        
        query = urllib.parse.parse_qs(parsed.query)
        def get_q(key: str, default: str = "") -> str:
            vals = query.get(key, [])
            return vals[0] if vals else default

        transport = get_q("type", "tcp").lower()
        if transport in ("splithttp", "xhttp"):
            transport = "xhttp"
        
        security = get_q("security", "none").lower()
        flow = get_q("flow", "")
        
        # Security settings (Reality or TLS)
        sec_settings: Dict[str, Any] = {
            "sni": get_q("sni", host),
            "fp": get_q("fp", "chrome"),
            "alpn": [a.strip() for a in get_q("alpn").split(",") if a.strip()] if get_q("alpn") else ["h2", "http/1.1"],
            "allowInsecure": get_q("allowInsecure", "0") in ("1", "true")
        }
        if security == "reality":
            sec_settings["pbk"] = get_q("pbk")
            sec_settings["sid"] = get_q("sid")
            sec_settings["spx"] = get_q("spx", "/")
        
        # Transport settings (XHTTP, WS, gRPC, TCP)
        trans_settings: Dict[str, Any] = {}
        if transport == "xhttp":
            trans_settings["path"] = get_q("path", "/")
            trans_settings["host"] = get_q("host", sec_settings["sni"])
            trans_settings["mode"] = get_q("mode", "auto")
            extra_str = get_q("extra")
            if extra_str:
                try:
                    trans_settings["extra"] = json.loads(urllib.parse.unquote(extra_str))
                except Exception:
                    pass
        elif transport == "ws":
            trans_settings["path"] = get_q("path", "/")
            trans_settings["host"] = get_q("host", sec_settings["sni"])
        elif transport == "grpc":
            trans_settings["serviceName"] = get_q("serviceName", "")
            trans_settings["mode"] = get_q("mode", "gun")
        elif transport == "httpupgrade":
            trans_settings["path"] = get_q("path", "/")
            trans_settings["host"] = get_q("host", sec_settings["sni"])

        return VpnNode(
            sub_id=sub_id,
            name=name,
            protocol="vless",
            server=host,
            port=port,
            uuid=uuid_str,
            transport=transport,
            transport_settings=trans_settings,
            security=security,
            security_settings=sec_settings,
            flow=flow,
            raw_link=url
        )
    except Exception as e:
        print(f"Error parsing VLESS URL: {e}")
        return None

def parse_vmess_url(url: str, sub_id: str = "manual") -> Optional[VpnNode]:
    """Parse vmess:// link (base64 JSON)."""
    try:
        b64_content = url[8:] if url.startswith("vmess://") else url
        decoded = clean_b64_decode(b64_content)
        data = json.loads(decoded)
        
        host = data.get("add", "")
        port = int(data.get("port", 443))
        name = data.get("ps", f"VMess-{host}:{port}")
        uuid_str = data.get("id", "")
        net = str(data.get("net", "tcp")).lower()
        if net in ("splithttp", "xhttp"):
            net = "xhttp"
            
        tls_val = str(data.get("tls", "none")).lower()
        security = "tls" if tls_val in ("tls", "1", "true") else "none"
        
        sec_settings = {
            "sni": data.get("sni") or data.get("host") or host,
            "fp": data.get("fp", "chrome"),
            "alpn": [a.strip() for a in str(data.get("alpn", "")).split(",") if a.strip()]
        }
        
        trans_settings = {
            "path": data.get("path", "/"),
            "host": data.get("host", host),
            "mode": data.get("type", "auto") if net == "xhttp" else "auto"
        }
        
        return VpnNode(
            sub_id=sub_id,
            name=name,
            protocol="vmess",
            server=host,
            port=port,
            uuid=uuid_str,
            transport=net,
            transport_settings=trans_settings,
            security=security,
            security_settings=sec_settings,
            raw_link=url
        )
    except Exception as e:
        print(f"Error parsing VMess URL: {e}")
        return None

def parse_trojan_url(url: str, sub_id: str = "manual") -> Optional[VpnNode]:
    """Parse trojan:// link."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme.lower() != "trojan":
            return None
        password = parsed.username or ""
        host = parsed.hostname or ""
        port = parsed.port or 443
        name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else f"Trojan-{host}:{port}"
        
        query = urllib.parse.parse_qs(parsed.query)
        def get_q(k: str, d: str = "") -> str:
            v = query.get(k, [])
            return v[0] if v else d

        transport = get_q("type", "tcp").lower()
        if transport in ("splithttp", "xhttp"):
            transport = "xhttp"
        security = get_q("security", "tls").lower()
        
        sec_settings = {
            "sni": get_q("sni", host),
            "fp": get_q("fp", "chrome"),
            "alpn": [a.strip() for a in get_q("alpn").split(",") if a.strip()] if get_q("alpn") else ["h2", "http/1.1"],
            "allowInsecure": get_q("allowInsecure", "0") in ("1", "true")
        }
        
        trans_settings = {
            "path": get_q("path", "/"),
            "host": get_q("host", sec_settings["sni"]),
            "mode": get_q("mode", "auto")
        }
        
        return VpnNode(
            sub_id=sub_id,
            name=name,
            protocol="trojan",
            server=host,
            port=port,
            uuid=password,
            transport=transport,
            transport_settings=trans_settings,
            security=security,
            security_settings=sec_settings,
            raw_link=url
        )
    except Exception as e:
        print(f"Error parsing Trojan URL: {e}")
        return None

def parse_ss_url(url: str, sub_id: str = "manual") -> Optional[VpnNode]:
    """Parse Shadowsocks ss:// link (SIP002 or legacy base64)."""
    try:
        name = ""
        fragment = ""
        if "#" in url:
            url_part, fragment = url.split("#", 1)
            name = urllib.parse.unquote(fragment)
        else:
            url_part = url

        content = url_part[5:] if url_part.startswith("ss://") else url_part
        if "@" in content:
            # SIP002 format: ss://base64(method:password)@host:port
            user_part, host_port = content.split("@", 1)
            decoded_user = clean_b64_decode(user_part)
            if ":" in decoded_user:
                method, password = decoded_user.split(":", 1)
            else:
                method, password = "aes-256-gcm", decoded_user
            
            # handle query params if any
            if "?" in host_port:
                hp, query_str = host_port.split("?", 1)
            else:
                hp = host_port
                
            if ":" in hp:
                host, port_str = hp.split(":", 1)
                port = int(port_str)
            else:
                host, port = hp, 8388
        else:
            # Legacy format: ss://base64(method:password@host:port)
            decoded = clean_b64_decode(content)
            if "@" in decoded:
                user_part, host_port = decoded.split("@", 1)
                method, password = user_part.split(":", 1) if ":" in user_part else ("aes-256-gcm", user_part)
                host, port_str = host_port.split(":", 1)
                port = int(port_str)
            else:
                return None
                
        if not name:
            name = f"Shadowsocks-{host}:{port}"
            
        return VpnNode(
            sub_id=sub_id,
            name=name,
            protocol="shadowsocks",
            server=host,
            port=port,
            uuid=password,
            transport="tcp",
            transport_settings={"method": method},
            security="none",
            raw_link=url
        )
    except Exception as e:
        print(f"Error parsing SS URL: {e}")
        return None

def parse_hysteria2_url(url: str, sub_id: str = "manual") -> Optional[VpnNode]:
    """Parse hysteria2:// or hy2:// link."""
    try:
        parsed = urllib.parse.urlparse(url)
        auth = parsed.username or ""
        host = parsed.hostname or ""
        port = parsed.port or 443
        name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else f"Hysteria2-{host}:{port}"
        
        query = urllib.parse.parse_qs(parsed.query)
        def get_q(k: str, d: str = "") -> str:
            v = query.get(k, [])
            return v[0] if v else d

        sec_settings = {
            "sni": get_q("sni", host),
            "insecure": get_q("insecure", "0") in ("1", "true"),
            "pinSHA256": get_q("pinSHA256", "")
        }
        
        trans_settings = {
            "obfs": get_q("obfs", ""),
            "obfs-password": get_q("obfs-password", "")
        }
        
        return VpnNode(
            sub_id=sub_id,
            name=name,
            protocol="hysteria2",
            server=host,
            port=port,
            uuid=auth,
            transport="udp",
            transport_settings=trans_settings,
            security="tls",
            security_settings=sec_settings,
            raw_link=url
        )
    except Exception as e:
        print(f"Error parsing Hysteria2 URL: {e}")
        return None

def parse_tuic_url(url: str, sub_id: str = "manual") -> Optional[VpnNode]:
    """Parse tuic:// link."""
    try:
        parsed = urllib.parse.urlparse(url)
        uuid_str = parsed.username or ""
        password = parsed.password or ""
        host = parsed.hostname or ""
        port = parsed.port or 443
        name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else f"TUIC-{host}:{port}"
        
        query = urllib.parse.parse_qs(parsed.query)
        def get_q(k: str, d: str = "") -> str:
            v = query.get(k, [])
            return v[0] if v else d

        sec_settings = {
            "sni": get_q("sni", host),
            "alpn": [a.strip() for a in get_q("alpn").split(",") if a.strip()] if get_q("alpn") else ["h3"],
            "allowInsecure": get_q("allow_insecure", "0") in ("1", "true")
        }
        
        trans_settings = {
            "congestion_control": get_q("congestion_control", "bbr"),
            "udp_relay_mode": get_q("udp_relay_mode", "native"),
            "password": password
        }
        
        return VpnNode(
            sub_id=sub_id,
            name=name,
            protocol="tuic",
            server=host,
            port=port,
            uuid=uuid_str,
            transport="quic",
            transport_settings=trans_settings,
            security="tls",
            security_settings=sec_settings,
            raw_link=url
        )
    except Exception as e:
        print(f"Error parsing TUIC URL: {e}")
        return None

def parse_single_link(link: str, sub_id: str = "manual") -> Optional[VpnNode]:
    """Parse any single VPN URI string."""
    link = link.strip()
    if link.startswith("vless://"):
        return parse_vless_url(link, sub_id)
    elif link.startswith("vmess://"):
        return parse_vmess_url(link, sub_id)
    elif link.startswith("trojan://"):
        return parse_trojan_url(link, sub_id)
    elif link.startswith("ss://"):
        return parse_ss_url(link, sub_id)
    elif link.startswith("hysteria2://") or link.startswith("hy2://"):
        return parse_hysteria2_url(link, sub_id)
    elif link.startswith("tuic://"):
        return parse_tuic_url(link, sub_id)
    return None

def parse_clash_yaml(content: str, sub_id: str = "manual") -> List[VpnNode]:
    """Parse Clash / Clash.Meta / Mihomo YAML subscription."""
    nodes: List[VpnNode] = []
    try:
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            return nodes
        
        proxies = data.get("proxies", [])
        for p in proxies:
            if not isinstance(p, dict):
                continue
            name = str(p.get("name", "Proxy"))
            ptype = str(p.get("type", "")).lower()
            server = str(p.get("server", ""))
            port = int(p.get("port", 443))
            
            if ptype == "vless":
                uuid_str = str(p.get("uuid", ""))
                flow = str(p.get("flow", ""))
                net = str(p.get("network", "tcp")).lower()
                if net in ("splithttp", "xhttp"):
                    net = "xhttp"
                
                tls = p.get("tls", False)
                reality = p.get("reality-opts", {})
                security = "reality" if reality else ("tls" if tls else "none")
                
                sec_settings = {
                    "sni": str(p.get("servername", server)),
                    "fp": str(p.get("client-fingerprint", "chrome")),
                    "alpn": p.get("alpn", ["h2", "http/1.1"])
                }
                if reality:
                    sec_settings["pbk"] = reality.get("public-key", "")
                    sec_settings["sid"] = reality.get("short-id", "")
                    sec_settings["spx"] = reality.get("spider-x", "/")
                    
                trans_settings = {}
                if net == "xhttp":
                    xopts = p.get("xhttp-opts", {}) or p.get("splithttp-opts", {})
                    trans_settings["path"] = xopts.get("path", "/")
                    trans_settings["host"] = xopts.get("host", sec_settings["sni"])
                    trans_settings["mode"] = xopts.get("mode", "auto")
                elif net == "ws":
                    wsopts = p.get("ws-opts", {})
                    trans_settings["path"] = wsopts.get("path", "/")
                    headers = wsopts.get("headers", {})
                    trans_settings["host"] = headers.get("Host", sec_settings["sni"]) if isinstance(headers, dict) else sec_settings["sni"]
                elif net == "grpc":
                    gopts = p.get("grpc-opts", {})
                    trans_settings["serviceName"] = gopts.get("grpc-service-name", "")
                    
                nodes.append(VpnNode(
                    sub_id=sub_id,
                    name=name,
                    protocol="vless",
                    server=server,
                    port=port,
                    uuid=uuid_str,
                    transport=net,
                    transport_settings=trans_settings,
                    security=security,
                    security_settings=sec_settings,
                    flow=flow
                ))
            elif ptype == "vmess":
                uuid_str = str(p.get("uuid", ""))
                net = str(p.get("network", "tcp")).lower()
                tls = p.get("tls", False)
                security = "tls" if tls else "none"
                sec_settings = {
                    "sni": str(p.get("servername", server)),
                    "alpn": p.get("alpn", [])
                }
                trans_settings = {}
                if net == "ws":
                    wsopts = p.get("ws-opts", {})
                    trans_settings["path"] = wsopts.get("path", "/")
                    headers = wsopts.get("headers", {})
                    trans_settings["host"] = headers.get("Host", server) if isinstance(headers, dict) else server
                elif net in ("xhttp", "splithttp"):
                    net = "xhttp"
                    xopts = p.get("xhttp-opts", {}) or p.get("splithttp-opts", {})
                    trans_settings["path"] = xopts.get("path", "/")
                    trans_settings["mode"] = xopts.get("mode", "auto")
                    
                nodes.append(VpnNode(
                    sub_id=sub_id,
                    name=name,
                    protocol="vmess",
                    server=server,
                    port=port,
                    uuid=uuid_str,
                    transport=net,
                    transport_settings=trans_settings,
                    security=security,
                    security_settings=sec_settings
                ))
            elif ptype == "trojan":
                password = str(p.get("password", ""))
                net = str(p.get("network", "tcp")).lower()
                sec_settings = {
                    "sni": str(p.get("sni", server)),
                    "alpn": p.get("alpn", ["h2", "http/1.1"])
                }
                nodes.append(VpnNode(
                    sub_id=sub_id,
                    name=name,
                    protocol="trojan",
                    server=server,
                    port=port,
                    uuid=password,
                    transport=net,
                    security="tls",
                    security_settings=sec_settings
                ))
            elif ptype in ("ss", "shadowsocks"):
                password = str(p.get("password", ""))
                cipher = str(p.get("cipher", "aes-256-gcm"))
                nodes.append(VpnNode(
                    sub_id=sub_id,
                    name=name,
                    protocol="shadowsocks",
                    server=server,
                    port=port,
                    uuid=password,
                    transport="tcp",
                    transport_settings={"method": cipher},
                    security="none"
                ))
            elif ptype == "hysteria2":
                password = str(p.get("password", ""))
                nodes.append(VpnNode(
                    sub_id=sub_id,
                    name=name,
                    protocol="hysteria2",
                    server=server,
                    port=port,
                    uuid=password,
                    transport="udp",
                    transport_settings={"obfs": p.get("obfs", ""), "obfs-password": p.get("obfs-password", "")},
                    security="tls",
                    security_settings={"sni": str(p.get("sni", server))}
                ))
            elif ptype == "tuic":
                uuid_str = str(p.get("uuid", ""))
                password = str(p.get("password", ""))
                nodes.append(VpnNode(
                    sub_id=sub_id,
                    name=name,
                    protocol="tuic",
                    server=server,
                    port=port,
                    uuid=uuid_str,
                    transport="quic",
                    transport_settings={"password": password, "congestion_control": p.get("congestion-controller", "bbr")},
                    security="tls",
                    security_settings={"sni": str(p.get("sni", server))}
                ))
    except Exception as e:
        print(f"Error parsing Clash YAML: {e}")
    return nodes

def parse_subscription_content(content: str, sub_id: str = "manual") -> List[VpnNode]:
    """Universal parser for subscription content (Base64 link list, Clash YAML, or plain URI list)."""
    content = content.strip()
    if not content:
        return []

    # 1. Try Clash YAML if it has 'proxies:'
    if "proxies:" in content:
        nodes = parse_clash_yaml(content, sub_id)
        if nodes:
            return nodes

    # 2. Try plain lines first (if already starting with vless://, vmess://, etc.)
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if any(line.startswith(("vless://", "vmess://", "trojan://", "ss://", "hysteria2://", "hy2://", "tuic://")) for line in lines):
        nodes = []
        for line in lines:
            node = parse_single_link(line, sub_id)
            if node:
                nodes.append(node)
        if nodes:
            return nodes

    # 3. Try Base64 decoding
    decoded = clean_b64_decode(content)
    if decoded:
        # Check if decoded is YAML
        if "proxies:" in decoded:
            nodes = parse_clash_yaml(decoded, sub_id)
            if nodes:
                return nodes
        # Split decoded lines
        d_lines = [line.strip() for line in decoded.splitlines() if line.strip()]
        nodes = []
        for line in d_lines:
            node = parse_single_link(line, sub_id)
            if node:
                nodes.append(node)
        if nodes:
            return nodes

    # 4. Fallback: single link
    node = parse_single_link(content, sub_id)
    if node:
        return [node]

    return []

from .hwid import get_subscription_headers
from .countries import detect_country

def enrich_node(node: VpnNode) -> VpnNode:
    """Enrich node with country name, ISO country code, and flag emoji."""
    if not node.country or not node.flag or not node.country_code:
        c_name, c_code, flag_emoji, display_name = detect_country(node.name)
        node.country = c_name
        node.country_code = c_code
        node.flag = flag_emoji
        if display_name and len(display_name) >= 2:
            node.name = display_name
    return node

def is_dummy_node(node: VpnNode) -> bool:
    """Detect if a node is an informational dummy node (e.g. error message from VPN panel)."""
    if node.server in ("0.0.0.0", "127.0.0.1") and node.port in (1, 0):
        return True
    lower_name = node.name.lower()
    if any(k in lower_name for k in ["не поддерживается", "передачу hwid", "превышено кол-во"]):
        return True
    return False

def fetch_subscription_data(url: str, headers: dict) -> Optional[requests.Response]:
    """Fetch subscription URL with SSL-fallback and local proxy retry."""
    try:
        return requests.get(url, headers=headers, timeout=15)
    except requests.exceptions.SSLError:
        try:
            return requests.get(url, headers=headers, timeout=15, verify=False)
        except Exception:
            pass
    except Exception as e:
        # If direct failed or blocked, try via local socks/http proxy if active
        try:
            proxies = {"http": "http://127.0.0.1:10809", "https": "http://127.0.0.1:10809"}
            return requests.get(url, headers=headers, timeout=15, proxies=proxies, verify=False)
        except Exception:
            pass
    return None

def fetch_and_parse_subscription(url: str, sub_id: str = "manual") -> List[VpnNode]:
    """
    Download subscription from URL using dual-UA technique:
    1. Primary fetch using Clash/Meta UA (downloads structured Clash YAML).
    2. Secondary fetch using v2rayNG UA (fetches XHTTP/VLESS Reality nodes that panels hide from Clash).
    3. Merge both node lists, deduplicating and preferring richest transport (e.g. XHTTP).
    """
    headers = get_subscription_headers()
    
    # 1. Fetch Primary
    primary_nodes: List[VpnNode] = []
    try:
        resp = fetch_subscription_data(url, headers)
        if resp and resp.headers.get("X-Hwid-Max-Devices-Reached") == "true":
            raise ValueError("Превышен лимит устройств для этой подписки. Освободите устройство в боте или увеличьте лимит.")
        if resp and resp.status_code == 200:
            primary_nodes = parse_subscription_content(resp.text, sub_id)
    except Exception as e:
        print(f"Primary subscription fetch warning: {e}")

    # 2. Fetch Secondary (v2rayNG UA - discovers XHTTP and native VLESS endpoints)
    secondary_nodes: List[VpnNode] = []
    try:
        v2ray_headers = dict(headers)
        v2ray_headers["User-Agent"] = "v2rayNG/1.8.5"
        resp2 = fetch_subscription_data(url, v2ray_headers)
        if resp2 and resp2.status_code == 200 and resp2.text:
            secondary_nodes = parse_subscription_content(resp2.text, sub_id)
    except Exception as e:
        print(f"Secondary v2rayNG subscription fetch warning: {e}")

    # 3. Merge intelligently
    combined_nodes: List[VpnNode] = []
    seen_keys = set()

    def get_node_key(n: VpnNode) -> str:
        # Key by server:port:uuid, or server:port:transport
        return f"{n.server.strip().lower()}:{n.port}:{n.transport.lower()}"

    # If secondary returned richer nodes (especially XHTTP nodes), prioritize them
    for n in secondary_nodes:
        if not is_dummy_node(n):
            key = get_node_key(n)
            if key not in seen_keys:
                seen_keys.add(key)
                combined_nodes.append(enrich_node(n))

    # Add any primary nodes not already covered
    for n in primary_nodes:
        if not is_dummy_node(n):
            key = get_node_key(n)
            # Also check if same server:port was added with tcp instead of xhttp
            server_port_key = f"{n.server.strip().lower()}:{n.port}"
            existing_servers = [k.split(":", 2)[0] + ":" + k.split(":", 2)[1] for k in seen_keys if ":" in k]
            if key not in seen_keys and server_port_key not in existing_servers:
                seen_keys.add(key)
                combined_nodes.append(enrich_node(n))

    # If combined is empty, check if all nodes were dummy/error messages
    if not combined_nodes:
        all_raw = primary_nodes + secondary_nodes
        if all_raw:
            msg = " ".join(n.name for n in all_raw if n.name)
            raise ValueError(f"Сервер подписки вернул сообщение: {msg}")
        raise ValueError("Не удалось получить серверы из подписки. Проверьте ссылку и доступность интернета.")

    return combined_nodes

