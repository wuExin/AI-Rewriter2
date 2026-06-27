@echo off
chcp 65001 >nul 2>&1
title AI文章改写工具 V2 - 一键安装
cd /d "%~dp0"

cls
echo.
echo ========================================
echo    AI文章改写工具 V2 - 一键安装
echo ========================================
echo.
echo 本脚本将自动安装以下组件：
echo   - Python (如需)
echo   - Node.js (如需)
echo.
echo Playwright 浏览器和 opencli 已内置，无需下载。
echo.
pause
echo.

REM ========== 检查 Python ==========
echo [1/2] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [提示] 未检测到 Python
    echo.
    echo 是否自动下载安装 Python？
    echo   [1] 是 (推荐)
    echo   [2] 否 (我将手动安装)
    echo.
    choice /C 12 /N /M "请选择: "
    if errorlevel 2 (
        echo.
        echo 请手动安装 Python 3.10+: https://www.python.org/downloads/
        echo 安装时务必勾选 "Add Python to PATH"
        echo 安装完成后重新运行本脚本
        pause
        exit /b 1
    )

    echo.
    echo 正在下载 Python 安装器...
    powershell -Command "& {Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe' -OutFile 'python-installer.exe'}"
    if exist "python-installer.exe" (
        echo 正在安装 Python (务必勾选 "Add Python to PATH")...
        python-installer.exe /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
        del python-installer.exe
        echo.
        echo 请关闭当前窗口，重新运行本脚本以验证安装
        pause
        exit /b 0
    ) else (
        echo [错误] 下载失败
        pause
        exit /b 1
    )
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo [OK] %%i
echo.

REM ========== 检查 Node.js ==========
echo [2/2] 检查 Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo [提示] 未检测到 Node.js
    echo.
    echo 是否自动下载安装 Node.js？
    echo   [1] 是 (推荐)
    echo   [2] 否 (我将手动安装)
    echo.
    choice /C 12 /N /M "请选择: "
    if errorlevel 2 (
        echo.
        echo 请手动安装 Node.js 20+: https://npmmirror.com/mirrors/node/
        echo 安装完成后重新运行本脚本
        pause
        exit /b 1
    )

    echo.
    echo 正在下载 Node.js 安装器...
    powershell -Command "& {Invoke-WebRequest -Uri 'https://npmmirror.com/mirrors/node/v20.11.0/node-v20.11.0-x64.msi' -OutFile 'nodejs-installer.msi'}"
    if exist "nodejs-installer.msi" (
        echo 正在安装 Node.js (可能需要管理员权限)...
        msiexec /i nodejs-installer.msi /qb
        del nodejs-installer.msi
        echo 请关闭当前窗口，重新运行本脚本以验证安装
        pause
        exit /b 0
    ) else (
        echo [错误] 下载失败
        pause
        exit /b 1
    )
)
for /f "tokens=*" %%i in ('node --version') do echo [OK] %%i
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
echo 下一步操作：
echo   1. 双击运行 "启动工具.bat" 启动程序
echo   2. 首次启动会自动生成 config.yaml
echo   3. 编辑 config.yaml 填入 API 密钥
echo.
echo 文件说明：
echo   - 启动工具.bat      : 启动主程序
echo   - output\           : 输出目录
echo   - logs\             : 日志目录
echo.
pause
