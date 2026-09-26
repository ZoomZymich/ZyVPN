import os
import sys
import shutil
import subprocess

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PYTHON_EXE = sys.executable

def build():
    print(f"Building ZyVPN.exe using Python: {PYTHON_EXE}...")
    
    ui_dir = os.path.join(BASE_DIR, "zyvpn", "ui")
    add_data_arg = f"{ui_dir};zyvpn/ui"
    
    release_dist = os.path.join(BASE_DIR, "dist", "release")
    dist_app_dir = os.path.join(release_dist, "ZyVPN")
    
    cmd = [
        PYTHON_EXE, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir", # Directory build is much faster to launch and avoids temp file decompression on every start
        "--windowed", # No console window
        "--name", "ZyVPN",
        f"--distpath={release_dist}",
        f"--add-data={add_data_arg}",
        "--hidden-import=bottle",
        "--hidden-import=webview",
        "--hidden-import=yaml",
        "--hidden-import=requests",
        "--hidden-import=clr_loader",
        "--hidden-import=pythonnet",
        os.path.join(BASE_DIR, "run.py")
    ]
    
    print("Running PyInstaller command...")
    res = subprocess.run(cmd, cwd=BASE_DIR)
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

    # Try copying to primary dist/ZyVPN as well if accessible
    primary_dist_dir = os.path.join(BASE_DIR, "dist", "ZyVPN")
    try:
        if os.path.exists(primary_dist_dir):
            shutil.copytree(dist_app_dir, primary_dist_dir, dirs_exist_ok=True)
            print("Successfully updated dist/ZyVPN.")
    except Exception as e:
        print(f"Notice: dist/ZyVPN is currently in use by a running process. Standalone build is at dist/release/ZyVPN.")

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
