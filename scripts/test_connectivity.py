import sys, os, time, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from zyvpn.storage import Storage
from zyvpn.core import CoreController
import requests

st = Storage()
core = CoreController()
node = st.get_selected_node()
print(f"Connecting to: {node.name} ({node.country}) | {node.protocol} - {node.transport}")
ok = core.start(node, st.settings)
print("Connected:", ok)
time.sleep(2)

proxies = {
    "http": f"http://127.0.0.1:{st.settings.http_port}",
    "https": f"http://127.0.0.1:{st.settings.http_port}"
}

targets = [
    ("IP Info", "https://ipinfo.io/json"),
    ("YouTube", "https://www.youtube.com"),
    ("Discord", "https://discord.com"),
    ("Telegram Web", "https://web.telegram.org"),
    ("Instagram", "https://www.instagram.com"),
    ("VK (Bypass RU)", "https://vk.com"),
    ("Yandex (Bypass RU)", "https://ya.ru")
]

for name, url in targets:
    try:
        t0 = time.time()
        res = requests.get(url, proxies=proxies, timeout=8)
        dt = int((time.time() - t0) * 1000)
        print(f"[{name}] -> Status {res.status_code} ({dt} ms)")
        if "ip" in name.lower():
            print(f"   Response: {res.text.strip()[:100]}")
    except Exception as e:
        print(f"[{name}] -> ERROR: {e}")

core.stop()
