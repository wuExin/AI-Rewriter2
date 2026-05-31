@echo off
chcp 65001 >nul 2>&1
title AI文章改写工具 V2

REM 设置 Playwright 使用本地浏览器
set PLAYWRIGHT_BROWSERS_PATH=%~dp0ms-playwright

REM 启动程序
cd /d "%~dp0"
python main.py

REM 如果出错，显示提示
if errorlevel 1 (
    echo.
    echo ========================================
    echo [启动失败]
    echo ========================================
    echo.
    echo 可能原因：
    echo   1. Python 未安装或未添加到 PATH
    echo   2. 依赖未安装，请运行 "一键安装完整版.bat"
    echo   3. Playwright 浏览器未安装
    echo.
    echo 请检查 logs 目录中的日志文件
    echo.
    pause
)
