import os
import sys
import shutil
import subprocess

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PYTHON_EXE = sys.executable

def build():
    print(f"Building ZyVPN.exe using Python: {PYTHON_EXE}...")
    
    # Terminate any running instances so files are not locked
    try:
        try:
            import urllib.request
            urllib.request.urlopen("http://127.0.0.1:18080/api/app_quit", timeout=0.5)
        except Exception:
            pass
        subprocess.run(["taskkill", "/F", "/IM", "ZyVPN.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["taskkill", "/F", "/IM", "xray.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["taskkill", "/F", "/IM", "sing-box.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    ui_dir = os.path.join(BASE_DIR, "zyvpn", "ui")
    add_data_arg = f"{ui_dir};ui"
    
    release_dist = os.path.join(BASE_DIR, "dist", "release")
    dist_app_dir = os.path.join(release_dist, "ZyVPN")
    
    icon_path = os.path.join(BASE_DIR, "zyvpn.ico")

    cmd = [
        PYTHON_EXE, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir", # Directory build is much faster to launch and avoids temp file decompression on every start
        "--windowed", # No console window
        "--uac-admin", # Force UAC administrator elevation on Windows launch
        f"--icon={icon_path}",
        "--name", "ZyVPN",
        f"--distpath={release_dist}",
        f"--paths={BASE_DIR}",
        f"--add-data={add_data_arg}",
        "--collect-all=zyvpn",
        "--collect-all=pystray",
        "--hidden-import=bottle",
        "--hidden-import=webview",
        "--hidden-import=yaml",
        "--hidden-import=requests",
        "--hidden-import=clr_loader",
        "--hidden-import=pythonnet",
        "--hidden-import=pystray",
        "--hidden-import=pystray._win32",
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--hidden-import=PIL.ImageDraw",
        "--collect-all=pystray",
        os.path.join(BASE_DIR, "run.py")
    ]
    
    print("Running PyInstaller command...")
    build_env = os.environ.copy()
    build_env["PYTHONPATH"] = BASE_DIR + (os.pathsep + build_env["PYTHONPATH"] if "PYTHONPATH" in build_env else "")
    res = subprocess.run(cmd, cwd=BASE_DIR, env=build_env)
    if res.returncode != 0:
        print(f"Build failed with exit code {res.returncode}")
        sys.exit(res.returncode)
        
    print("PyInstaller build complete.")
    
    # Copy bin directory into dist/release/ZyVPN so it is 100% standalone
    dist_bin_dir = os.path.join(dist_app_dir, "bin")
    src_bin_dir = os.path.join(BASE_DIR, "bin")
    
    if os.path.exists(src_bin_dir):
        print(f"Copying bin directory to {dist_bin_dir}...")
        if os.path.exists(dist_bin_dir):
            shutil.rmtree(dist_bin_dir)
        shutil.copytree(src_bin_dir, dist_bin_dir)
        print("Bin directory copied.")
        
    src_data_cfg = os.path.join(BASE_DIR, "data", "config.json")
    dist_data_dir = os.path.join(dist_app_dir, "data")
    if os.path.exists(src_data_cfg):
        os.makedirs(dist_data_dir, exist_ok=True)
        shutil.copy2(src_data_cfg, os.path.join(dist_data_dir, "config.json"))
        print("data/config.json copied.")

    if os.path.exists(icon_path):
        shutil.copy2(icon_path, os.path.join(dist_app_dir, "zyvpn.ico"))
        print("zyvpn.ico copied.")

    # Try copying to primary dist/ZyVPN as well so ZyVPN.bat can find it
    primary_dist_dir = os.path.join(BASE_DIR, "dist", "ZyVPN")
    try:
        shutil.copytree(dist_app_dir, primary_dist_dir, dirs_exist_ok=True)
        print("Successfully updated dist/ZyVPN.")
    except Exception as e:
        print(f"Notice: could not update dist/ZyVPN: {e}. Standalone build is at dist/release/ZyVPN.")

    final_exe = os.path.join(dist_app_dir, "ZyVPN.exe")
    if os.path.exists(os.path.join(primary_dist_dir, "ZyVPN.exe")):
        final_exe = os.path.join(primary_dist_dir, "ZyVPN.exe")

    print("\n==========================================")
    print(" SUCCESS! ZyVPN is ready:")
    print(f" Executable: {final_exe}")
    print(f" Standalone folder: {dist_app_dir}")
    print("==========================================")

if __name__ == "__main__":
    build()
