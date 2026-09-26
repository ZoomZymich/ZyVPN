@echo off
title ZyVPN Launcher
cd /d "%~dp0"

set PYTHON_EXE=C:\Users\Zyma\AppData\Local\Programs\Python\Python312\python.exe

if not exist "%PYTHON_EXE%" (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_EXE=python
    ) else (
        echo [ERROR] Python not found! Please ensure Python 3.12 is installed.
        pause
        exit /b 1
    )
)

echo Starting ZyVPN...
"%PYTHON_EXE%" run.py
