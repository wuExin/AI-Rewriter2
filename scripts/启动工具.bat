@echo off
chcp 65001 >nul 2>&1
title AI文章改写工具 V2
cd /d "%~dp0"

REM 首次运行：从模板生成配置文件
if not exist "%~dp0config.yaml" (
    if exist "%~dp0config.example.yaml" (
        copy /Y "%~dp0config.example.yaml" "%~dp0config.yaml" >nul
        echo.
        echo ========================================
        echo   首次运行 - 已生成配置文件
        echo ========================================
        echo.
        echo 请编辑 config.yaml 填入你的 API 密钥后重新启动
        echo.
        notepad "%~dp0config.yaml"
        exit /b 0
    ) else (
        echo [错误] 找不到配置文件模板
        pause
        exit /b 1
    )
)

REM 设置 Playwright 使用本地浏览器
if exist "%~dp0ms-playwright" (
    set PLAYWRIGHT_BROWSERS_PATH=%~dp0ms-playwright
)

start "" "AI文章改写工具.exe"
