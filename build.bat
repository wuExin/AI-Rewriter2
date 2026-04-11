@echo off
chcp 65001 >nul
title AI文章改写工具 V2 - 打包

echo ========================================
echo    AI文章改写工具 V2 - 打包
echo ========================================
echo.

set VERSION=2.1
set DIST_DIR=AI文章改写工具V2_元宝版_v%VERSION%

echo [清理] 删除旧文件...
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%" 2>nul
if exist "build" rmdir /s /q "build" 2>nul
if exist "dist\AI文章改写工具" rmdir /s /q "dist\AI文章改写工具" 2>nul
if exist "dist\AI文章改写工具.exe" del "dist\AI文章改写工具.exe" 2>nul
if exist "dist\*.rar" del "dist\*.rar" 2>nul

echo.
echo [1/4] 安装 PyInstaller...
pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple -q

echo.
echo [2/4] 打包 EXE（需要几分钟）...
pyinstaller --clean build_exe.spec

echo.
echo [3/4] 创建发布目录...
mkdir "%DIST_DIR%" 2>nul

echo.
echo [4/4] 复制文件到发布目录...
copy /Y "dist\AI文章改写工具.exe" "%DIST_DIR%\" >nul
copy /Y "config.yaml" "%DIST_DIR%\" >nul
mkdir "%DIST_DIR%\output" 2>nul
mkdir "%DIST_DIR%\logs" 2>nul

echo.
echo ========================================
echo    打包完成！
echo ========================================
echo.
echo 发布目录: %DIST_DIR%\
echo.

echo 正在创建启动脚本...
call :create_start_bat
call :create_setup_bat
call :create_readme

echo.
dir "%DIST_DIR%"
echo.
pause
exit /b

:create_start_bat
(
echo @echo off
echo chcp 65001 ^>nul 2^>^&1
echo title AI文章改写工具 V2
echo cd /d "%%~dp0"
echo set PLAYWRIGHT_BROWSERS_PATH=%%~dp0ms-playwright
echo start "" "AI文章改写工具.exe"
) > "%DIST_DIR%\启动工具.bat"
exit /b

:create_setup_bat
(
echo @echo off
echo chcp 65001 ^>nul
echo title AI文章改写工具 V2 - 首次设置
echo cd /d "%%~dp0"
echo echo ========================================
echo echo    AI文章改写工具 V2 - 首次设置
echo echo ========================================
echo echo.
echo echo [1/2] 安装 opencli 依赖...
echo cd opencli
echo call npm install
echo echo.
echo echo [2/2] 登录腾讯元宝...
echo echo   将打开浏览器，请扫码登录
echo pause
echo node dist/main.js yuanbao new
echo echo.
echo echo 设置完成！运行 "启动工具.bat" 开始使用
echo pause
) > "%DIST_DIR%\首次设置.bat"
exit /b

:create_readme
(
echo ========================================
echo    AI文章改写工具 V2 - 元宝版 v%VERSION%
echo ========================================
echo.
echo [首次使用]
echo.
echo 1. 运行 "首次设置.bat"
echo    - 安装 opencli 依赖
echo    - 登录腾讯元宝
echo.
echo [日常使用]
echo.
echo 1. 运行 "启动工具.bat"
echo.
echo 2. 确保浏览器已安装 opencli 扩展
echo    - 下载: github.com/jackwener/opencli/releases
echo.
echo 3. 粘贴文章URL，点击"开始处理"
echo.
echo [目录说明]
echo.
echo - output\  : 改写后的文章
echo - logs\    : 运行日志
echo - opencli\ : opencli 程序
echo.
echo ========================================
) > "%DIST_DIR%\使用说明.txt"
exit /b
