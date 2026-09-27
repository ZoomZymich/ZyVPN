@echo off
title ZyVPN
cd /d "%~dp0"

if exist "dist\ZyVPN\ZyVPN.exe" (
    start "" "dist\ZyVPN\ZyVPN.exe"
    exit /b 0
)

if exist "ZyVPN.exe" (
    start "" "ZyVPN.exe"
    exit /b 0
)

echo Compiled ZyVPN.exe not found, starting via Python...
set PYTHON_EXE=
where python >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_EXE=python
) else (
    where py >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_EXE=py
    ) else (
        if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
            set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
        ) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
            set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        ) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
            set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        ) else (
            echo [ERROR] Python not found. Please install Python 3.10+ from python.org
            pause
            exit /b 1
        )
    )
)
if not exist "bin\xray.exe" (
    echo [INFO] VPN core binaries not found in bin\. Downloading automatically...
    "%PYTHON_EXE%" scripts\download_binaries.py
)

start "" "%PYTHON_EXE%" run.py
