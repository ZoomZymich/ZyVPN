import socket
import time
from typing import Optional, List, Dict
import concurrent.futures
from .models import VpnNode

def tcp_ping(host: str, port: int, timeout: float = 2.0) -> Optional[int]:
    """Perform a connect handshake ping to host:port and measure time in milliseconds (supports IPv4 & IPv6)."""
    try:
        start_time = time.perf_counter()
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        return max(1, elapsed_ms)
    except Exception:
        return None

def ping_node(node: VpnNode, timeout: float = 2.0) -> Optional[int]:
    """Test ping for a single node and update its ping_ms field."""
    res = tcp_ping(node.server, node.port, timeout)
    # If node is UDP-only (Hysteria2 / TUIC) and port is not TCP, try pinging standard HTTPS port 443 as latency probe
    if res is None and node.protocol in ("hysteria2", "tuic") and node.port != 443:
        res = tcp_ping(node.server, 443, timeout)
    node.ping_ms = res
    return res

def ping_all_nodes(nodes: List[VpnNode], max_workers: int = 20, timeout: float = 2.0) -> Dict[str, Optional[int]]:
    """Test ping concurrently for a list of nodes."""
    results: Dict[str, Optional[int]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_node = {executor.submit(ping_node, n, timeout): n for n in nodes}
        for future in concurrent.futures.as_completed(future_to_node):
            node = future_to_node[future]
            try:
                results[node.id] = future.result()
            except Exception:
                results[node.id] = None
    return results
