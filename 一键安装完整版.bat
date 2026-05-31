@echo off
chcp 65001 >nul 2>&1
title AI文章改写工具 V2 - 一键安装

cls
echo.
echo ========================================
echo    AI文章改写工具 V2 - 一键安装
echo ========================================
echo.
echo 本脚本将自动安装以下组件：
echo   - Python 依赖包
echo   - Playwright 浏览器 (国内镜像)
echo   - Node.js (如需)
echo   - opencli 依赖
echo.
pause
echo.

REM ========== 检查 Python ==========
echo [1/6] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python！
    echo.
    echo 请先安装 Python 3.10+: https://www.python.org/downloads/
    echo 安装时务必勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo [OK] %PYVER%
echo.

REM ========== 检查 pip ==========
echo [2/6] 检查 pip...
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [错误] pip 未安装，尝试修复...
    python -m ensurepip --default-pip
)
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple -q
echo [OK] pip 已就绪
echo.

REM ========== 安装 Python 依赖 ==========
echo [3/6] 安装 Python 依赖包...
echo (使用清华大学镜像，约需 1-2 分钟)
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple -q
if errorlevel 1 (
    echo [错误] 依赖安装失败，尝试备用镜像...
    python -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ -q
)
echo [OK] Python 依赖已安装
echo.

REM ========== 安装 Playwright 浏览器 ==========
echo [4/6] 安装 Playwright 浏览器...
echo (使用国内镜像，约需 300-400MB，下载时间取决于网速)
echo.
REM 设置国内镜像环境变量
set PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/
set PLAYWRIGHT_BROWSERS_PATH=0

REM 尝试安装
python -m playwright install chromium --with-deps
if errorlevel 1 (
    echo.
    echo [警告] 自动安装失败，尝试手动安装...
    echo 如果下载失败，请访问以下链接手动下载：
    echo https://npmmirror.com/mirrors/playwright/
    echo.
    pause
    python -m playwright install chromium
)

REM 复制到本地（用于便携）
if exist "%USERPROFILE%\AppData\Local\ms-playwright" (
    if not exist "ms-playwright" mkdir ms-playwright
    xcopy "%USERPROFILE%\AppData\Local\ms-playwright\*" "ms-playwright\" /E /I /Y >nul 2>&1
)
echo [OK] Playwright 浏览器已安装
echo.

REM ========== 检查 Node.js ==========
echo [5/6] 检查 Node.js...
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
        echo 请手动安装 Node.js: https://npm.taobao.org/mirrors/node/
        echo 安装完成后重新运行本脚本
        pause
        exit /b 1
    )

    echo.
    echo 正在下载 Node.js 安装器...
    powershell -Command "& {Invoke-WebRequest -Uri 'https://npm.taobao.org/mirrors/node/v20.11.0/node-v20.11.0-x64.msi' -OutFile 'nodejs-installer.msi'}"
    if exist "nodejs-installer.msi" (
        echo 正在安装 Node.js (可能需要管理员权限)...
        msiexec /i nodejs-installer.msi /qb
        del nodejs-installer.msi
        echo 请重启命令行后重新运行本脚本
        pause
        exit /b 0
    ) else (
        echo [错误] 下载失败
        pause
        exit /b 1
    )
)
for /f "tokens=*" %%i in ('node --version') do set NODEVER=%%i
echo [OK] %NODEVER%
echo.

REM ========== 安装 opencli 依赖 ==========
echo [6/6] 安装 opencli 依赖...
echo (约需 200MB，下载时间取决于网速)
cd opencli
call npm install --registry=https://registry.npmmirror.com
if errorlevel 1 (
    echo [错误] opencli 依赖安装失败
    echo 尝试使用备用源...
    call npm install --registry=https://registry.npm.taobao.org
)
cd ..
echo [OK] opencli 依赖已安装
echo.

REM ========== 创建目录 ==========
echo [完成] 创建工作目录...
if not exist "output" mkdir output
if not exist "logs" mkdir logs
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
echo   1. 双击运行 "启动GUI.bat" 启动程序
echo   2. 首次使用需要在浏览器中登录腾讯元宝
echo.
echo 文件说明：
echo   - 启动GUI.bat      : 启动主程序
echo   - output\          : 输出目录
echo   - logs\            : 日志目录
echo.
pause
