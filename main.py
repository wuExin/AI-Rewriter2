"""AI文章改写工具 V2 - 元宝版"""
import asyncio
import os
import sys
from pathlib import Path

# Windows 下修复 asyncio subprocess 兼容性问题
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# 设置 Playwright 浏览器路径（优先使用打包版本）
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后
    base_dir = Path(sys.executable).parent
else:
    # 开发环境
    base_dir = Path(__file__).parent

# 设置 Playwright 浏览器路径
local_playwright = base_dir / "ms-playwright"
if local_playwright.exists():
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(local_playwright)
    print(f"[INFO] 使用本地 Playwright 浏览器: {local_playwright}")
elif 'PLAYWRIGHT_BROWSERS_PATH' not in os.environ:
    # 使用系统默认路径
    system_pw = Path(os.environ.get('LOCALAPPDATA', '')) / 'ms-playwright'
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(system_pw)

from src.gui import App

if __name__ == "__main__":
    app = App()
    app.mainloop()
