"""
内容抓取模块
"""
from .base import ContentFetcher, create_fetcher
from .playwright_fetcher import (
    PlaywrightFetcher,
    SmartFetcher,
    create_playwright_fetcher,
    create_smart_fetcher,
)

__all__ = [
    "ContentFetcher",
    "create_fetcher",
    "PlaywrightFetcher",
    "SmartFetcher",
    "create_playwright_fetcher",
    "create_smart_fetcher",
]
