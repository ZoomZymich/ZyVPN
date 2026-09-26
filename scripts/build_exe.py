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
    
    cmd = [
        PYTHON_EXE, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir", # Directory build is much faster to launch and avoids temp file decompression on every start
        "--windowed", # No console window
        "--name", "ZyVPN",
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
    
    # Copy bin directory into dist/ZyVPN so dist/ZyVPN is a 100% complete, standalone distribution!
    dist_app_dir = os.path.join(BASE_DIR, "dist", "ZyVPN")
    dist_bin_dir = os.path.join(dist_app_dir, "bin")
    src_bin_dir = os.path.join(BASE_DIR, "bin")
    
    if os.path.exists(src_bin_dir):
        print(f"Copying bin directory to {dist_bin_dir}...")
        if os.path.exists(dist_bin_dir):
            shutil.rmtree(dist_bin_dir)
        shutil.copytree(src_bin_dir, dist_bin_dir)
        print("Bin directory copied.")
        
    print("\n==========================================")
    print(" SUCCESS! ZyVPN is ready:")
    print(f" Executable: {os.path.join(dist_app_dir, 'ZyVPN.exe')}")
    print("==========================================")

if __name__ == "__main__":
    build()
