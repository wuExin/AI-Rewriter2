"""批量测试百度链接抓取，每个链接单独保存到logs目录"""
import asyncio
import sys
import os
import re

sys.path.insert(0, os.path.dirname(__file__))
# Force UTF-8 output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from src.fetcher.playwright_fetcher import SmartFetcher

URLS = [
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_9395764670874400299%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_9946753428456023105%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_8779985069326203578%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_9414241869466317234%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_10007695960705032762%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_9874556445548685649%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_9212669854322787752%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_9463278520435821769%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_9385211176291734772%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_10379702444252018080%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_10457432822553344177%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_10337507362728435646%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_9253368174310399736%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_9473459482839194300%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_9005810330851867886%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_8713571517572721900%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_9762663450715249350%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_10122825617028713516%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_9543132008348844355%22%7D",
    "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_9462278849732265012%22%7D",
]

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def safe_filename(title: str, max_len: int = 50) -> str:
    """将标题转为安全的文件名"""
    # 去掉不安全字符
    name = re.sub(r'[\\/:*?"<>|\n\r]', '', title)
    # 截断
    if len(name) > max_len:
        name = name[:max_len]
    return name.strip()


async def main():
    fetcher = SmartFetcher(timeout=30000, headless=True)

    for i, url in enumerate(URLS, 1):
        print(f"[{i}/{len(URLS)}] Fetching: {url[:80]}...")

        try:
            result = await fetcher.fetch_from_url(url, truncate_at_paywall=True)
            title = result.get("title", "(无标题)")
            content = result.get("content", "")
            char_count = len(content)

            filename = f"{i:02d}_{safe_filename(title)}.md"
            filepath = os.path.join(LOG_DIR, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n\n")
                f.write(f"- **序号**: {i}/{len(URLS)}\n")
                f.write(f"- **链接**: {url}\n")
                f.write(f"- **正文字数**: {char_count}\n\n")
                f.write(f"---\n\n")
                f.write(content)

            print(f"  OK: {title} ({char_count} chars) -> {filename}")
        except Exception as e:
            print(f"  FAIL: {e}")


if __name__ == "__main__":
    asyncio.run(main())
