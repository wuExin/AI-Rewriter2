@echo off
chcp 65001 >nul 2>&1
title 环境检查
cd /d "%~dp0"

cls
echo.
echo ========================================
echo    环境检查报告
echo ========================================
echo.

set ALL_OK=1

echo [1/6] Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [NG] 未安装
    set ALL_OK=0
) else (
    python --version
)

echo [2/6] Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo [NG] 未安装
    set ALL_OK=0
) else (
    node --version
)

echo [3/6] npm...
npm --version >nul 2>&1
if errorlevel 1 (
    echo [NG] 未安装
    set ALL_OK=0
) else (
    npm --version
)

echo [4/6] Python 依赖包...
python -c "import customtkinter, playwright, httpx, loguru, yaml, docx" >nul 2>&1
if errorlevel 1 (
    echo [NG] 依赖包缺失，请运行 "安装依赖.bat" 后重试
    set ALL_OK=0
) else (
    echo [OK] 所有依赖已安装
)

echo [5/6] Playwright 浏览器...
if exist "%~dp0ms-playwright\chromium" (
    echo [OK] Chromium 已安装（本地）
) else if exist "%USERPROFILE%\AppData\Local\ms-playwright\chromium" (
    echo [OK] Chromium 已安装（系统）
) else (
    echo [NG] 未安装，请运行 "安装依赖.bat"
    set ALL_OK=0
)

echo [6/6] opencli 依赖...
if exist "%~dp0opencli\node_modules" (
    echo [OK] 已安装
) else (
    echo [NG] 未安装，请运行 "安装依赖.bat"
    set ALL_OK=0
)

echo.
if "%ALL_OK%"=="1" (
    echo [OK] 所有组件已就绪！运行 "启动工具.bat" 即可开始使用
) else (
    echo 请按上述提示完成缺失组件的安装
)

echo.
pause
