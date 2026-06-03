@echo off
chcp 65001 >nul 2>&1
title AI文章改写工具 V2 - 首次安装依赖
cd /d "%~dp0"

cls
echo.
echo ========================================
echo    AI文章改写工具 V2 - 首次安装
echo ========================================
echo.
echo 本脚本将安装运行所需的依赖：
echo   [1] 检查 Python 和 Node.js
echo   [2] 安装 opencli 依赖
echo   [3] 下载 Playwright 浏览器（可选）
echo.
echo.
pause

REM ========== 检查 Python ==========
echo [1/4] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python！
    echo.
    echo 请安装 Python 3.10+: https://www.python.org/downloads/
    echo 安装时务必勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
python --version
echo.

REM ========== 检查 Node.js ==========
echo [2/4] 检查 Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Node.js！
    echo.
    echo 请安装 Node.js 20+: https://npmmirror.com/mirrors/node/
    echo.
    pause
    exit /b 1
)
node --version
echo.

REM ========== 安装 opencli 依赖 ==========
echo [3/4] 安装 opencli 依赖...
cd opencli
call npm install --ignore-scripts --registry=https://registry.npmmirror.com
if errorlevel 1 (
    echo [错误] opencli 依赖安装失败
    pause
    exit /b 1
)
cd ..
echo [OK] opencli 依赖已安装
echo.

REM ========== 安装 Playwright 浏览器 ==========
echo [4/4] Playwright 浏览器（可选，约400MB）...
echo.
echo   [1] 下载到本目录（便携版）
echo   [2] 下载到系统目录
echo   [3] 跳过（我已有 Playwright 浏览器）
echo.
choice /C 123 /N /M "请选择: "

if errorlevel 3 goto :skip_pw
if errorlevel 2 (
    set PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/
    python -m playwright install chromium --with-deps
    goto :pw_done
)
if errorlevel 1 (
    set PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/
    set PLAYWRIGHT_BROWSERS_PATH=%~dp0ms-playwright
    python -m playwright install chromium --with-deps
)
:pw_done
echo [OK] Playwright 浏览器已安装
:skip_pw
echo.

REM ========== 完成 ==========
cls
echo.
echo ========================================
echo    安装完成！
echo ========================================
echo.
echo 环境信息：
python --version 2>&1
node --version 2>&1
echo.
echo 下一步：
echo   1. 双击 "启动工具.bat" 启动程序
echo   2. 首次启动会自动生成 config.yaml
echo   3. 编辑 config.yaml 填入 API 密钥
echo.
pause
