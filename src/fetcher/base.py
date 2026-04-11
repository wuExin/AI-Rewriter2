"""
内容抓取模块
支持从URL获取文章内容
"""
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from bs4 import BeautifulSoup
import httpx
from loguru import logger


class ContentFetcher:
    """内容抓取器基类"""

    def __init__(self, timeout: int = 30, user_agent: str = None, log_dir: str = "./logs"):
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        # 日志目录
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _log_fetched_content(self, url: str, title: str, content: str):
        """记录抓取的内容到日志"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.log_dir / f"fetch_{timestamp}.md"

        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"# 内容抓取日志\n\n")
            f.write(f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**URL**: {url}\n")
            f.write(f"**标题**: {title}\n")
            f.write(f"**字数**: {len(content)}\n")
            f.write(f"\n---\n\n")
            f.write(f"## 抓取内容:\n\n")
            f.write(f"```\n{content}\n```\n")

        logger.info(f"抓取内容已保存到: {log_file}")

    def _extract_title(self, html: str, url: str) -> str:
        """从HTML中提取标题"""
        soup = BeautifulSoup(html, "lxml")

        # 尝试多种方式获取标题
        title = ""

        # 1. h1标签
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text().strip()

        # 2. og:title
        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title:
                title = og_title.get("content", "")

        # 3. title标签
        if not title:
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text().strip()

        # 清理标题
        title = re.sub(r"_.*?今日头条.*", "", title)
        title = re.sub(r"-.*?今日头条.*", "", title)
        title = re.sub(r"\s*-\s*今日头条.*", "", title)
        title = title.strip()

        return title or "未知标题"

    async def fetch_from_url(self, url: str) -> dict:
        """
        从URL获取文章内容

        Args:
            url: 文章URL

        Returns:
            {"title": str, "content": str}
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()

                html = response.text
                title = self._extract_title(html, url)
                content = self.parse_html(html, url)

                logger.info(f"成功获取内容: {url}, 标题: {title}, 字数: {len(content)}")

                # 保存抓取内容到日志
                self._log_fetched_content(url, title, content)

                return {"title": title, "content": content}

        except httpx.TimeoutException:
            logger.error(f"请求超时: {url}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP错误: {e.response.status_code} - {url}")
            raise
        except Exception as e:
            logger.error(f"获取内容失败: {e}")
            raise

    def parse_html(self, html: str, url: str = "") -> str:
        """
        解析HTML，提取正文内容

        Args:
            html: HTML内容
            url: 来源URL（用于判断平台）

        Returns:
            提取的纯文本内容
        """
        soup = BeautifulSoup(html, "lxml")

        # 移除不需要的标签
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
            tag.decompose()

        # 根据平台选择不同的解析策略
        if "mp.weixin.qq.com" in url:
            content = self._parse_wechat(soup)
        elif "toutiao.com" in url:
            content = self._parse_toutiao(soup)
        elif "zhihu.com" in url:
            content = self._parse_zhihu(soup)
        else:
            content = self._parse_generic(soup)

        return self.clean_content(content)

    def _parse_wechat(self, soup: BeautifulSoup) -> str:
        """解析微信公众号文章"""
        # 微信公众号文章正文在 id="js_content" 中
        content_div = soup.find("div", id="js_content")
        if content_div:
            return content_div.get_text(separator="\n", strip=True)
        return self._parse_generic(soup)

    def _parse_toutiao(self, soup: BeautifulSoup) -> str:
        """解析今日头条文章"""
        # 今日头条文章通常在 class="article-content" 中
        content_div = soup.find("div", class_=re.compile(r"article-content|article__content"))
        if content_div:
            return content_div.get_text(separator="\n", strip=True)
        return self._parse_generic(soup)

    def _parse_zhihu(self, soup: BeautifulSoup) -> str:
        """解析知乎文章"""
        # 知乎文章在 class="Post-RichText" 或 class="RichContent-inner" 中
        content_div = soup.find("div", class_=re.compile(r"Post-RichText|RichContent-inner"))
        if content_div:
            return content_div.get_text(separator="\n", strip=True)
        return self._parse_generic(soup)

    def _parse_generic(self, soup: BeautifulSoup) -> str:
        """通用HTML解析"""
        # 尝试找到主要内容区域
        candidates = []

        # 常见的内容容器选择器
        selectors = [
            "article",
            "[class*='content']",
            "[class*='article']",
            "[class*='post']",
            "[id*='content']",
            "[id*='article']",
            "main",
        ]

        for selector in selectors:
            for elem in soup.select(selector):
                text = elem.get_text(separator="\n", strip=True)
                if len(text) > 200:  # 至少200字才考虑
                    candidates.append((elem, len(text)))

        # 选择最长的内容
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0].get_text(separator="\n", strip=True)

        # 兜底：返回body的所有文本
        body = soup.find("body")
        if body:
            return body.get_text(separator="\n", strip=True)

        return soup.get_text(separator="\n", strip=True)

    def clean_content(self, content: str) -> str:
        """
        清洗提取的内容

        Args:
            content: 原始内容

        Returns:
            清洗后的内容
        """
        # 移除多余的空白行
        content = re.sub(r"\n{3,}", "\n\n", content)

        # 移除行首行尾空白
        lines = [line.strip() for line in content.split("\n")]
        content = "\n".join(lines)

        # 移除常见的广告/无关文本
        noise_patterns = [
            r"点击.*?关注",
            r"扫码.*?关注",
            r"长按.*?识别",
            r"更多.*?请关注",
            r"转载请注明",
            r"来源.*?授权",
            r"广告",
        ]

        for pattern in noise_patterns:
            content = re.sub(pattern, "", content, flags=re.IGNORECASE)

        return content.strip()

    def fetch_from_text(self, text: str) -> str:
        """
        直接处理文本内容

        Args:
            text: 输入文本

        Returns:
            清洗后的文本
        """
        return self.clean_content(text)


def create_fetcher(timeout: int = 30, user_agent: str = None) -> ContentFetcher:
    """创建内容抓取器实例"""
    return ContentFetcher(timeout=timeout, user_agent=user_agent)
