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
set PYTHON_EXE=C:\Users\Zyma\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PYTHON_EXE%" (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_EXE=python
    ) else (
        echo [ERROR] Python not found.
        pause
        exit /b 1
    )
)
start "" "%PYTHON_EXE%" run.py
