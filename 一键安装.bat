@echo off
chcp 65001 >/dev/null
title AI文章改写工具 V2 - 安装程序

echo ========================================
echo    AI文章改写工具 V2 - 环境安装
echo ========================================
echo.

echo [检查] 正在检查Python...
python --version >/dev/null 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python！
    echo.
    echo 请先安装Python 3.10+: https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo [OK] Python已安装
python --version

echo.
echo [1/4] 升级pip...
python -m pip install --upgrade pip -q

echo [2/4] 安装依赖包...
echo 正在安装: customtkinter, playwright, httpx, loguru等...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo [3/4] 安装Playwright浏览器...
echo 这可能需要几分钟...
set PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/
playwright install chromium

echo [4/4] 创建输出目录...
if not exist "output" mkdir output
if not exist "logs" mkdir logs

echo.
echo ========================================
echo    安装完成！
echo ========================================
echo.
echo 双击 "启动GUI.bat" 即可开始使用
echo.
pause
