@echo off
chcp 65001 >nul 2>&1
title 环境检查

cls
echo.
echo ========================================
echo    环境检查报告
echo ========================================
echo.

REM 检查 Python
echo [1/7] Python ...
python --version >nul 2>&1
if errorlevel 1 (
    echo [NG] Python 未安装
    set PYTHON_OK=0
) else (
    python --version
    set PYTHON_OK=1
)

REM 检查 pip
echo [2/7] pip ...
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [NG] pip 未安装
    set PIP_OK=0
) else (
    python -m pip --version
    set PIP_OK=1
)

REM 检查 Node.js
echo [3/7] Node.js ...
node --version >nul 2>&1
if errorlevel 1 (
    echo [NG] Node.js 未安装
    set NODE_OK=0
) else (
    node --version
    set NODE_OK=1
)

REM 检查 npm
echo [4/7] npm ...
npm --version >nul 2>&1
if errorlevel 1 (
    echo [NG] npm 未安装
    set NPM_OK=0
) else (
    npm --version
    set NPM_OK=1
)

REM 检查 Python 依赖
echo [5/7] Python 依赖包 ...
python -c "import customtkinter, playwright, httpx, loguru, yaml, docx" >nul 2>&1
if errorlevel 1 (
    echo [NG] 依赖包缺失
    set DEPS_OK=0
) else (
    echo [OK] 所有依赖已安装
    set DEPS_OK=1
)

REM 检查 Playwright 浏览器
echo [6/7] Playwright 浏览器 ...
python -c "from playwright.sync_api import sync_playwright; print('OK')" >nul 2>&1
if errorlevel 1 (
    echo [NG] Playwright 未正确安装
    set PW_OK=0
) else (
    if exist "%USERPROFILE%\AppData\Local\ms-playwright\chromium" (
        echo [OK] Chromium 已安装
        set PW_OK=1
    ) else if exist "%~dp0ms-playwright\chromium" (
        echo [OK] Chromium 已安装 (本地)
        set PW_OK=1
    ) else (
        echo [NG] Chromium 浏览器未下载
        set PW_OK=0
    )
)

REM 检查 opencli
echo [7/7] opencli ...
if exist "%~dp0opencli\node_modules" (
    echo [OK] opencli 依赖已安装
    set OPENCLI_OK=1
) else (
    echo [NG] opencli 依赖未安装
    set OPENCLI_OK=0
)

echo.
echo ========================================
echo    检查结果
echo ========================================
echo.

set ALL_OK=1
if %PYTHON_OK%==0 (
    echo [!] Python 未安装 → 请访问 https://www.python.org/downloads/
    set ALL_OK=0
)
if %NODE_OK%==0 (
    echo [!] Node.js 未安装 → 请访问 https://npm.taobao.org/mirrors/node/
    set ALL_OK=0
)
if %DEPS_OK%==0 (
    echo [!] Python 依赖缺失 → 请运行 "一键安装完整版.bat"
    set ALL_OK=0
)
if %PW_OK%==0 (
    echo [!] Playwright 浏览器未下载 → 请运行 "下载Playwright浏览器.bat"
    set ALL_OK=0
)
if %OPENCLI_OK%==0 (
    echo [!] opencli 依赖未安装 → 请运行 "一键安装完整版.bat"
    set ALL_OK=0
)

if %ALL_OK%==1 (
    echo [OK] 所有组件已就绪！
    echo.
    echo 运行 "启动GUI.bat" 即可开始使用
) else (
    echo.
    echo 请按上述提示完成缺失组件的安装
)

echo.
pause
