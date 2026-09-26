import sys
import os
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from zyvpn.parser import parse_single_link, parse_subscription_content, parse_clash_yaml

def test_vless_xhttp_tcp():
    url = "vless://a1b2c3d4-e5f6-7890-abcd-ef1234567890@example.com:443?security=reality&sni=test.org&fp=chrome&pbk=fakekey123&sid=1234&type=xhttp&path=/xhttp-path&mode=auto#XHTTP-Reality-Node"
    node = parse_single_link(url)
    assert node is not None, "Failed to parse VLESS XHTTP link"
    assert node.protocol == "vless"
    assert node.transport == "xhttp", f"Expected xhttp, got {node.transport}"
    assert node.transport_settings.get("path") == "/xhttp-path"
    assert node.transport_settings.get("mode") == "auto"
    assert node.security == "reality"
    assert node.security_settings.get("pbk") == "fakekey123"
    assert node.name == "XHTTP-Reality-Node"
    print("✓ VLESS XHTTP over TCP test passed!")

def test_vless_vision():
    url = "vless://a1b2c3d4-e5f6-7890-abcd-ef1234567890@1.2.3.4:443?security=reality&sni=dl.google.com&fp=chrome&pbk=realpubkey&sid=abcd&type=tcp&flow=xtls-rprx-vision#Vision-Node"
    node = parse_single_link(url)
    assert node is not None
    assert node.flow == "xtls-rprx-vision"
    assert node.transport == "tcp"
    print("✓ VLESS Reality Vision test passed!")

def test_hysteria2():
    url = "hy2://password123@hy2.server.com:443?sni=hy2.server.com&insecure=1#Hysteria2-Server"
    node = parse_single_link(url)
    assert node is not None
    assert node.protocol == "hysteria2"
    assert node.uuid == "password123"
    print("✓ Hysteria 2 test passed!")

def test_tuic():
    url = "tuic://uuid-user:pass-tuic@tuic.server.com:8443?sni=tuic.server.com&congestion_control=bbr#TUIC-Server"
    node = parse_single_link(url)
    assert node is not None
    assert node.protocol == "tuic"
    assert node.uuid == "uuid-user"
    assert node.transport_settings.get("password") == "pass-tuic"
    print("✓ TUIC test passed!")

def test_clash_yaml_xhttp():
    yaml_text = """
proxies:
  - name: "Clash-XHTTP-Reality"
    type: vless
    server: 1.2.3.4
    port: 443
    uuid: test-uuid
    network: xhttp
    tls: true
    reality-opts:
      public-key: pbk-key
      short-id: sid-key
    xhttp-opts:
      path: /mypath
      mode: packet-up
"""
    nodes = parse_clash_yaml(yaml_text)
    assert len(nodes) == 1
    assert nodes[0].transport == "xhttp"
    assert nodes[0].transport_settings.get("path") == "/mypath"
    assert nodes[0].transport_settings.get("mode") == "packet-up"
    assert nodes[0].security == "reality"
    print("✓ Clash YAML with XHTTP test passed!")

if __name__ == "__main__":
    test_vless_xhttp_tcp()
    test_vless_vision()
    test_hysteria2()
    test_tuic()
    test_clash_yaml_xhttp()
    print("\nAll parser tests successfully passed!")
