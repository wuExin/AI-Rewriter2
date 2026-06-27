@echo off
chcp 65001 >nul 2>&1
title AI文章改写工具 V2 - 打包发布

cls
echo.
echo ========================================
echo    AI文章改写工具 V2 - 打包发布
echo ========================================
echo.

set VERSION=2.1
set DIST_DIR=AI文章改写工具V2_元宝版_v%VERSION%

REM ========== 清理旧文件 ==========
echo [清理] 删除旧的构建文件...
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%" 2>nul
if exist "build" rmdir /s /q "build" 2>nul
if exist "dist" rmdir /s /q "dist" 2>nul
echo [OK] 清理完成
echo.

REM ========== 安装 PyInstaller ==========
echo [1/5] 安装 PyInstaller...
pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple -q
echo [OK] PyInstaller 已就绪
echo.

REM ========== 编译 EXE ==========
echo [2/5] 编译 EXE（需要几分钟）...
pyinstaller --clean build_exe.spec
if errorlevel 1 (
    echo.
    echo [错误] 编译失败！请检查代码是否有语法错误。
    pause
    exit /b 1
)
echo [OK] 编译完成
echo.

REM ========== 创建分发目录 ==========
echo [3/5] 创建分发目录...
mkdir "%DIST_DIR%" 2>nul
mkdir "%DIST_DIR%\output" 2>nul
mkdir "%DIST_DIR%\logs" 2>nul
echo [OK] 目录已创建
echo.

REM ========== 复制文件 ==========
echo [4/5] 复制文件到分发目录...

REM EXE
copy /Y "dist\AI文章改写工具.exe" "%DIST_DIR%\" >nul
if errorlevel 1 (
    echo [错误] 未找到编译后的 EXE 文件
    pause
    exit /b 1
)

REM 配置模板
copy /Y "config.example.yaml" "%DIST_DIR%\" >nul

REM opencli（仅必要的文件）
mkdir "%DIST_DIR%\opencli" 2>nul
xcopy "opencli\dist" "%DIST_DIR%\opencli\dist\" /E /I /Y /Q >nul 2>&1
xcopy "opencli\skills" "%DIST_DIR%\opencli\skills\" /E /I /Y /Q >nul 2>&1
copy /Y "opencli\package.json" "%DIST_DIR%\opencli\" >nul 2>&1
copy /Y "opencli\package-lock.json" "%DIST_DIR%\opencli\" >nul 2>&1
if exist "opencli\scripts" (
    xcopy "opencli\scripts" "%DIST_DIR%\opencli\scripts\" /E /I /Y /Q >nul 2>&1
)
if exist "opencli\tsconfig.json" (
    copy /Y "opencli\tsconfig.json" "%DIST_DIR%\opencli\" >nul
)

REM opencli/node_modules（已装好的依赖，用户无需再 npm install）
if exist "opencli\node_modules" (
    echo   复制 opencli/node_modules（约 200MB）...
    xcopy "opencli\node_modules" "%DIST_DIR%\opencli\node_modules\" /E /I /Y /Q >nul
) else (
    echo   [警告] opencli\node_modules 不存在，跳过
)

REM Playwright 浏览器（优先本地，其次系统目录）
set PW_FOUND=0
if exist "ms-playwright" (
    echo   复制本地 ms-playwright（约 400MB）...
    xcopy "ms-playwright" "%DIST_DIR%\ms-playwright\" /E /I /Y /Q >nul
    set PW_FOUND=1
)
if "%PW_FOUND%"=="0" if exist "%LOCALAPPDATA%\ms-playwright" (
    echo   复制系统 ms-playwright（约 400MB）...
    xcopy "%LOCALAPPDATA%\ms-playwright\chromium-*" "%DIST_DIR%\ms-playwright\" /E /I /Y /Q >nul
    set PW_FOUND=1
)
if "%PW_FOUND%"=="0" (
    echo   [警告] 未找到 Playwright 浏览器，用户需自行下载
)

echo [OK] 文件复制完成
echo.

REM ========== 复制用户脚本 ==========
echo [5/5] 复制用户脚本...
copy /Y "scripts\启动工具.bat" "%DIST_DIR%\" >nul
copy /Y "scripts\安装依赖.bat" "%DIST_DIR%\" >nul
copy /Y "scripts\检查环境.bat" "%DIST_DIR%\" >nul
copy /Y "scripts\使用说明.txt" "%DIST_DIR%\" >nul
echo [OK] 用户脚本已复制
echo.

REM ========== 完成 ==========
cls
echo.
echo ========================================
echo    打包完成！
echo ========================================
echo.
echo 发布目录: %DIST_DIR%\
echo.
echo 包含文件:
dir /b "%DIST_DIR%"
echo.
echo 下一步：
echo   1. 将 %DIST_DIR%\ 文件夹压缩后发送给用户
echo   2. 用户按 "使用说明.txt" 操作即可
echo.

REM ========== 可选压缩 ==========
echo 是否创建压缩包？
echo   [1] 创建 ZIP
echo   [2] 跳过
echo.
choice /C 12 /N /M "请选择: "
if errorlevel 2 goto :end
if errorlevel 1 (
    echo.
    echo 正在压缩（可能需要几分钟）...
    powershell -Command "Compress-Archive -Path '%DIST_DIR%' -DestinationPath '%DIST_DIR%.zip' -Force"
    if errorlevel 1 (
        echo [警告] 压缩失败，请手动压缩 %DIST_DIR% 文件夹
    ) else (
        echo [OK] 已生成 %DIST_DIR%.zip
    )
)

:end
echo.
pause
