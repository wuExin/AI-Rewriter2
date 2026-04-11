@echo off
chcp 65001 >/dev/null 2>&1
title AI Article Rewriter V2 - YuanBao Edition

echo.
echo ========================================
echo    AI Article Rewriter V2 - Starting...
echo ========================================
echo.

cd /d "%~dp0"

python main.py

if errorlevel 1 (
    echo.
    echo [Error] Failed to start!
    echo Please check:
    echo 1. Python is installed
    echo 2. Dependencies installed: pip install -r requirements.txt
    echo.
    pause
)
