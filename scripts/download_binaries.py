import os
import sys
import zipfile
import urllib.request
import shutil

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
os.makedirs(BIN_DIR, exist_ok=True)

DOWNLOADS = [
    {
        "name": "Xray-core",
        "url": "https://github.com/XTLS/Xray-core/releases/download/v26.3.27/Xray-windows-64.zip",
        "target_file": "xray.exe",
        "files_to_extract": ["xray.exe", "geoip.dat", "geosite.dat"]
    },
    {
        "name": "sing-box",
        "url": "https://github.com/SagerNet/sing-box/releases/download/v1.14.2/sing-box-1.14.2-windows-amd64.zip",
        "target_file": "sing-box.exe",
        "folder_search": "sing-box.exe"
    },
    {
        "name": "wintun",
        "url": "https://www.wintun.net/builds/wintun-0.14.1.zip",
        "target_file": "wintun.dll",
        "extract_path": "wintun/bin/amd64/wintun.dll"
    }
]

def download_file(url, dest):
    print(f"Downloading {url} -> {dest} ...")
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as out:
        shutil.copyfileobj(resp, out)
    print(f"Downloaded {dest} ({os.path.getsize(dest)} bytes)")

def process_item(item):
    name = item["name"]
    target = os.path.join(BIN_DIR, item["target_file"])
    if os.path.exists(target):
        print(f"[{name}] already exists at {target}, skipping.")
        return

    zip_path = os.path.join(BIN_DIR, f"{name}.zip")
    try:
        download_file(item["url"], zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()
            if "files_to_extract" in item:
                for fname in item["files_to_extract"]:
                    if fname in namelist:
                        zf.extract(fname, BIN_DIR)
                        print(f"Extracted {fname} to {BIN_DIR}")
            elif "folder_search" in item:
                search_target = item["folder_search"]
                for member in namelist:
                    if member.endswith(search_target):
                        with zf.open(member) as source, open(target, "wb") as dest:
                            shutil.copyfileobj(source, dest)
                        print(f"Extracted {search_target} to {target}")
                        break
            elif "extract_path" in item:
                with zf.open(item["extract_path"]) as source, open(target, "wb") as dest:
                    shutil.copyfileobj(source, dest)
                print(f"Extracted {item['extract_path']} to {target}")
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

def main():
    print(f"Downloading VPN core binaries into: {BIN_DIR}")
    for item in DOWNLOADS:
        try:
            process_item(item)
        except Exception as e:
            print(f"Error processing {item['name']}: {e}")
    print("Done downloading binaries.")

if __name__ == "__main__":
    main()
