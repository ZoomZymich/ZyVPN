import sys
import os
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from zyvpn.storage import Storage
from zyvpn.core import CoreController
from zyvpn.api import VpnApi

def test_full_flow():
    storage = Storage()
    core = CoreController()
    api = VpnApi(storage, core)

    # 1. Test importing single VLESS XHTTP node
    xhttp_link = (
        "vless://269c3a35-1886-4e5c-a5b8-5777ce404ea1@104.16.12.34:443"
        "?security=reality&sni=gateway.icloud.com&fp=chrome"
        "&pbk=YgqzLwqneyISerjCxpmmJ9caGKDE7X-qLbc-yQyyRmY&sid=1234"
        "&type=xhttp&path=%2Fcustom-xhttp-path&mode=auto"
        "#Netherlands-XHTTP-Reality"
    )
    res = api.import_text(xhttp_link)
    assert res["success"] is True
    assert res["nodes_added"] >= 1
    print("✓ Successfully imported VLESS XHTTP link into storage!")

    # 2. Test initial data retrieval
    data = api.get_initial_data()
    assert len(data["nodes"]) >= 1
    imported_node = next(n for n in data["nodes"] if "Netherlands-XHTTP-Reality" in n["name"])
    assert imported_node["transport"] == "xhttp"
    assert imported_node["security"] == "reality"
    print("✓ API returned valid node data with XHTTP transport and Reality security!")

    # 3. Test ping logic
    ping_res = api.ping_single(imported_node["id"])
    print(f"✓ TCP Handshake ping result: {ping_res}")

    # 4. Test settings update (auto-routing)
    api.update_settings({"routing_mode": "bypass_ru_lan", "mode": "proxy"})
    assert storage.settings.routing_mode == "bypass_ru_lan"
    print("✓ Auto-routing settings updated and verified!")

    print("\nAll integration tests passed successfully!")

if __name__ == "__main__":
    test_full_flow()
