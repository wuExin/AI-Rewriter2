"""
基于Playwright的动态网页抓取器
支持JavaScript渲染的网页内容抓取
"""
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None
    Browser = None
    Page = None


class PlaywrightFetcher:
    """基于Playwright的动态网页抓取器"""

    def __init__(
        self,
        timeout: int = 30000,
        headless: bool = True,
        user_agent: Optional[str] = None,
        log_dir: str = "./logs",
    ):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright未安装，请运行: pip install playwright && playwright install"
            )

        self.timeout = timeout
        self.headless = headless
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

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

    async def _extract_title(self, page: Page, url: str) -> str:
        """提取页面标题"""
        extract_title_js = r"""
        () => {
            // 尝试多种方式获取标题
            let title = '';

            // 1. 从h1标签获取
            const h1 = document.querySelector('h1');
            if (h1) {
                title = h1.innerText.trim();
            }

            // 2. 从og:title获取
            if (!title) {
                const ogTitle = document.querySelector('meta[property="og:title"]');
                if (ogTitle) {
                    title = ogTitle.getAttribute('content');
                }
            }

            // 3. 从title标签获取
            if (!title) {
                title = document.title;
            }

            // 4. 清理标题（去掉平台名称等）
            title = title
                .replace(/_.*?今日头条.*/, '')
                .replace(/-.*?今日头条.*/, '')
                .replace(/_.*?头条号.*/, '')
                .replace(/-.*?原创.*/, '')
                .replace(/\s*-\s*今日头条.*/, '')
                .trim();

            return title || '未知标题';
        }
        """
        return await page.evaluate(extract_title_js)

    async def fetch_from_url(self, url: str, truncate_at_paywall: bool = False) -> dict:
        """
        从URL获取文章内容

        Args:
            url: 文章URL
            truncate_at_paywall: 是否在付费墙标记处截断（仅仿写流程需要）

        Returns:
            {"title": str, "content": str}
        """
        self._truncate_at_paywall = truncate_at_paywall
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent=self.user_agent,
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()

            try:
                # 设置超时
                page.set_default_timeout(self.timeout)

                # 访问页面
                logger.info(f"正在加载页面: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)

                # 等待主要内容加载
                await self._wait_for_content(page, url)

                # 滚动页面触发懒加载
                await self._scroll_to_load(page, url)

                # 提取标题和内容
                title = await self._extract_title(page, url)
                content = await self._extract_content(page, url)

                logger.info(f"成功获取内容: {url}, 标题: {title}, 字数: {len(content)}")

                # 保存抓取内容到日志
                self._log_fetched_content(url, title, content)

                return {"title": title, "content": content}

            except Exception as e:
                logger.error(f"获取内容失败: {e}")
                # 保存截图用于调试
                try:
                    screenshot_path = f"debug_screenshot_{hash(url)}.png"
                    await page.screenshot(path=screenshot_path)
                    logger.info(f"已保存调试截图: {screenshot_path}")
                except:
                    pass
                raise

            finally:
                await browser.close()

    async def _scroll_to_load(self, page: Page, url: str):
        """滚动页面触发懒加载"""
        # 对于今日头条等需要滚动的页面
        if "toutiao.com" in url or "zhihu.com" in url or "baidu.com" in url:
            try:
                # 获取页面高度
                page_height = await page.evaluate("document.body.scrollHeight")
                scroll_steps = 5
                step_height = page_height / scroll_steps

                for i in range(scroll_steps):
                    await page.evaluate(f"window.scrollTo(0, {step_height * (i + 1)})")
                    await asyncio.sleep(0.5)  # 等待内容加载

                # 滚回顶部
                await page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(1)
                logger.info("页面滚动完成")
            except Exception as e:
                logger.warning(f"滚动失败: {e}")

    async def _wait_for_content(self, page: Page, url: str):
        """等待主要内容加载"""

        # 根据不同平台等待特定元素
        if "toutiao.com" in url:
            # 今日头条：等待文章内容容器，尝试多个可能的选择器
            selectors = [
                "article",
                ".article-content",
                ".textContent",
                "[class*='article']",
                "[class*='content']",
                ".tt-article",
                ".baidu-my",
            ]
            for selector in selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    logger.info(f"找到内容容器: {selector}")
                    break
                except:
                    continue
            # 额外等待确保内容完全加载
            await asyncio.sleep(3)

        elif "mp.weixin.qq.com" in url:
            # 微信公众号：等待内容区域
            try:
                await page.wait_for_selector("#js_content", timeout=10000)
            except:
                await asyncio.sleep(2)

        elif "zhihu.com" in url:
            # 知乎：等待文章内容
            try:
                await page.wait_for_selector(".Post-RichText, .RichContent-inner", timeout=10000)
            except:
                await asyncio.sleep(2)

        elif "baidu.com" in url:
            # 百度新闻/百家号：先检测是否触发安全验证
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(2)

            # 检测安全验证页面
            page_title = await page.title()
            page_text = await page.evaluate("document.body.innerText || ''")
            if "安全验证" in page_title or "网络不给力" in page_text:
                logger.warning("百度安全验证被触发，尝试等待后刷新...")
                await asyncio.sleep(3)
                await page.reload(wait_until="networkidle", timeout=15000)
                await asyncio.sleep(3)

                # 再次检测
                page_text = await page.evaluate("document.body.innerText || ''")
                if "网络不给力" in page_text or "安全验证" in (await page.title()):
                    raise RuntimeError("百度安全验证无法绕过，请尝试更换网络环境或稍后重试")

            # 等待正文内容容器
            selectors = [
                "div.article-content",
                "div[class*='article']",
                "article",
                ".index-module_articleWrap",
                ".index-module_textContent",
                "[class*='content']",
            ]
            for selector in selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    logger.info(f"百度页面找到内容容器: {selector}")
                    break
                except:
                    continue
            await asyncio.sleep(2)

        else:
            # 通用：等待body有内容
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(2)

    async def _extract_content(self, page: Page, url: str) -> str:
        """提取页面内容"""

        # 使用JavaScript在浏览器中提取内容（使用原始字符串避免转义问题）
        extract_js = r"""
        () => {
            // 移除不需要的元素
            const selectors = [
                'script', 'style', 'nav', 'header', 'footer', 'aside',
                'iframe', '.advertisement', '.ad', '.sidebar',
                '.comments', '.related', '.share', '.nav',
                '.recommend', '.hot-list', '.user-card'
            ];

            selectors.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => el.remove());
            });

            // 根据平台选择内容容器
            let contentElement = null;

            if (window.location.href.includes('toutiao.com')) {
                // 今日头条 - 使用更精确的选择器
                // 优先查找article标签，但要排除评论区域
                const article = document.querySelector('article');
                if (article) {
                    // 克隆节点以避免修改原始DOM
                    contentElement = article.cloneNode(true);

                    // 移除评论区和推荐内容
                    const removeSelectors = [
                        '[class*="comment"]',
                        '[class*="Comment"]',
                        '[id*="comment"]',
                        '[class*="recommend"]',
                        '[class*="related"]',
                        '[class*="share"]',
                        '[class*="follow"]',
                        '[class*="hot-list"]',
                        '[class*="user-card"]',
                        '.article-end',
                        '.read-more',
                        'footer'
                    ];

                    removeSelectors.forEach(sel => {
                        contentElement.querySelectorAll(sel).forEach(el => el.remove());
                    });

                    // 只取前几个段落（正文通常在前面）
                    const paragraphs = contentElement.querySelectorAll('p, div');
                    let text = '';
                    let emptyCount = 0;

                    for (let i = 0; i < paragraphs.length; i++) {
                        const p = paragraphs[i];
                        const txt = p.innerText || p.textContent || '';

                        // 跳过空段落
                        if (!txt.trim()) {
                            emptyCount++;
                            if (emptyCount > 2) break; // 连续2个空段落后停止
                            continue;
                        }
                        emptyCount = 0;

                        // 跳过明显的评论区标识
                        if (txt.includes('评论') || txt.includes('登录') ||
                            txt.includes('举报') || txt.includes('分享') ||
                            txt.includes('收藏') || txt.includes('查看全部')) {
                            break;
                        }

                        text += txt + '\n\n';

                        // 如果已经有足够内容且遇到短段落，可能到正文末尾
                        if (text.length > 500 && txt.length < 50) {
                            break;
                        }
                    }

                    if (text.length > 100) {
                        return text.trim();
                    }
                }

                // 备用选择器
                const toutiaoSelectors = [
                    '.article-content',
                    '.textContent',
                    '[class*="article"]',
                    '.tt-article',
                    '.baidu-my',
                    '.article-box',
                    '[class*="Article"]',
                ];

                for (const sel of toutiaoSelectors) {
                    const el = document.querySelector(sel);
                    if (el && el.innerText.length > 500) {
                        contentElement = el;
                        console.log('Found with selector:', sel);
                        break;
                    }
                }
            }
            else if (window.location.href.includes('baidu.com')) {
                // 百度新闻/百家号 — 精确提取正文，过滤头尾噪音
                const baiduSelectors = [
                    '.index-module_articleWrap',
                    '.index-module_textContent',
                    'div[class*="article-content"]',
                    'div[class*="article_content"]',
                    'article',
                    '.mainContent',
                ];
                let baiduContainer = null;
                for (const sel of baiduSelectors) {
                    const el = document.querySelector(sel);
                    if (el && el.innerText && el.innerText.length > 200) {
                        baiduContainer = el;
                        break;
                    }
                }

                if (baiduContainer) {
                    // 从容器中移除非正文元素
                    const clone = baiduContainer.cloneNode(true);
                    const removeSelectors = [
                        '[class*="comment"]', '[class*="Comment"]',
                        '[id*="comment"]', '[id*="Comment"]',
                        '[class*="super-comment"]',
                        '[class*="commentBox"]', '[class*="comment-box"]',
                        '[class*="comment-wrapper"]', '[class*="comment-list"]',
                        '[class*="reply-wrapper"]', '[class*="Reply"]',
                        '[class*="recommend"]', '[class*="related"]',
                        '[class*="share"]', '[class*="follow"]',
                        '[class*="hot-list"]', '[class*="user-card"]',
                        '[class*="header"]', '[class*="nav"]',
                        '[class*="footer"]', '[class*="copyright"]',
                        '[class*="author-info"]', '[class*="tag"]',
                        '[class*="pay"]', '[class*="purchase"]',
                        '[class*="column"]', '[class*="专栏"]',
                        'footer', 'nav', 'header',
                    ];
                    removeSelectors.forEach(sel => {
                        clone.querySelectorAll(sel).forEach(el => el.remove());
                    });

                    // 逐段提取，跳过头部元信息和尾部噪音
                    const paragraphs = clone.querySelectorAll('p, div > span, section');
                    let text = '';
                    let started = false;

                    for (let i = 0; i < paragraphs.length; i++) {
                        const txt = (paragraphs[i].innerText || '').trim();
                        if (!txt || txt.length < 2) continue;

                        // 跳过头部：导航、标题行、作者信息等
                        if (!started) {
                            if (txt === '百度首页' || txt === '登录' || txt === '关注' ||
                                txt.match(/^\d{4}-\d{2}-\d{2}/) || txt.length < 10) {
                                continue;
                            }
                            // 正文通常以引号、中文叙述开头，且长度较长
                            if (txt.length >= 15) {
                                started = true;
                            } else {
                                continue;
                            }
                        }

                        // 遇到尾部噪音则停止
                        if (txt.includes('剩余') && txt.includes('未读')) break;
                        if (txt.includes('立即解锁') || txt.includes('立即购买')) break;
                        if (txt.includes('举报/反馈') || txt.includes('举报') && txt.length < 10) break;
                        if (txt.match(/^\d{2}-\d{2}$/) && text.length > 500) break;
                        if (txt.includes('作者声明') || txt.includes('设为首页')) break;
                        if (txt.includes('京ICP') || txt.includes('京公网')) break;
                        if (txt.match(/^评论\s*\d*$/)) break;
                        if (txt === '发表' || txt.includes('发表神评妙论') || txt.includes('发表评论')) break;
                        if (txt.includes('精彩评论') || txt.includes('热门评论') || txt.includes('查看全部评论')) break;

                        text += txt + '\n\n';
                    }

                    if (text.length > 200) {
                        contentElement = null;  // 不走后续通用逻辑
                        return text.trim();
                    }
                }

                // 备用：尝试通用容器
                const fallbackSelectors = ['div[class*="content"]', 'main'];
                for (const sel of fallbackSelectors) {
                    const el = document.querySelector(sel);
                    if (el && el.innerText && el.innerText.length > 500) {
                        contentElement = el;
                        break;
                    }
                }
            }
            else if (window.location.href.includes('weixin.qq.com')) {
                // 微信公众号
                contentElement = document.querySelector('#js_content');
            }
            else if (window.location.href.includes('zhihu.com')) {
                // 知乎
                contentElement = document.querySelector('.Post-RichText') ||
                                 document.querySelector('.RichContent-inner');
            }

            // 如果没找到特定容器，尝试通用方法
            if (!contentElement || contentElement.innerText.length < 200) {
                // 找最长的文本块
                const candidates = [];
                const elements = document.querySelectorAll('div, article, main, section');

                elements.forEach(el => {
                    // 跳过明显不是内容的元素
                    const className = el.className || '';
                    if (className.includes('header') || className.includes('footer') ||
                        className.includes('nav') || className.includes('sidebar') ||
                        className.includes('ad') || className.includes('comment')) {
                        return;
                    }

                    const text = el.innerText || el.textContent;
                    if (text && text.length > 200) {
                        candidates.push({element: el, length: text.length});
                    }
                });

                if (candidates.length > 0) {
                    candidates.sort((a, b) => b.length - a.length);
                    // 优先选择更深层(更精确)的容器：如果子容器已包含父容器90%+文本，
                    // 选子容器——自然排除评论、推荐等兄弟节点噪音
                    var best = candidates[0];
                    for (var i = 1; i < Math.min(candidates.length, 10); i++) {
                        if (candidates[i].length > best.length * 0.9 &&
                            best.element.contains(candidates[i].element)) {
                            best = candidates[i];
                        }
                    }
                    contentElement = best.element;
                }
            }

            // 如果还是没找到，返回body
            if (!contentElement) {
                contentElement = document.body;
            }

            // 获取文本内容，保留段落结构
            let text = contentElement.innerText || contentElement.textContent || '';

            // 清理文本但保留段落结构
            text = text
                .replace(/\r\n/g, '\n')
                .replace(/\r/g, '\n')
                .replace(/\n{3,}/g, '\n\n')  // 多个换行变成两个
                .replace(/[ \t]+/g, ' ')  // 多个空格变成一个
                .trim();

            return text;
        }
        """

        content = await page.evaluate(extract_js)

        # 进一步清理
        content = self._clean_content(content, getattr(self, '_truncate_at_paywall', False))

        return content

    def _clean_content(self, content: str, truncate_at_paywall: bool = False) -> str:
        """清理提取的内容"""
        import re

        # 移除常见的噪音文本
        noise_patterns = [
            r"点击.*?关注",
            r"扫码.*?关注",
            r"长按.*?识别",
            r"更多.*?请关注",
            r"转载请注明",
            r"打开.*?APP",
            r"下载.*?客户端",
            r"广告",
            r"推荐阅读",
            r"百度首页",
            r"立即解锁专栏.*",
            r"立即购买本专栏.*",
            r"作者声明：.*",
            r"举报/反馈",
            r"设为首页",
            r"©\s*Baidu.*",
            r"使用百度前必读",
            r"京ICP证.*",
            r"京公网安备.*",
            r"敬请期待更多专栏内容",
            r"剩余\d+%未读",
        ]

        # 百度页面头尾裁剪（必须在 noise_patterns 之前，
        # 否则"剩余XX%未读"等截断标记会被 re.sub 删掉导致无法定位截断点）
        content = self._trim_baidu_noise(content, truncate_at_paywall)

        for pattern in noise_patterns:
            content = re.sub(pattern, "", content, flags=re.IGNORECASE)

        # 清理多余空白
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = re.sub(r" +", " ", content)

        return content.strip()

    def _trim_baidu_noise(self, content: str, truncate_at_paywall: bool = False) -> str:
        """裁剪百度页面特有的头部元信息和尾部评论/推荐噪音"""
        import re

        lines = content.split("\n")

        # ── 头部裁剪 ──
        # 策略：在前30行内找独立的"关注"行（百度文章元信息的最后一项），
        # 从它之后开始就是正文。如果没找到，尝试找日期行后的下一段内容。
        start_idx = 0
        for i, line in enumerate(lines[:30]):
            if line.strip() == "关注":
                start_idx = i + 1
                break
        else:
            # 没找到"关注"，尝试找日期行
            for i, line in enumerate(lines[:30]):
                if re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", line.strip()):
                    # 跳过日期行及其后面可能的省份行
                    start_idx = i + 1
                    for j in range(i + 1, min(i + 3, len(lines))):
                        stripped = lines[j].strip()
                        if stripped and re.match(r"^[\u4e00-\u9fff]{2,4}$", stripped):
                            start_idx = j + 1
                        elif stripped == "关注":
                            start_idx = j + 1
                    break

        # 跳过 start_idx 之后的空行
        while start_idx < len(lines) and not lines[start_idx].strip():
            start_idx += 1

        # ── 尾部裁剪 ──
        # 策略：从 start_idx 之后正向搜索，找"评论"区的开始标记，
        # 或者"剩余xx%未读"/"举报/反馈"等付费墙/页脚标记，从那里截断。
        end_idx = len(lines)
        tail_markers = [
            r"^评论\s*\d*\s*$",       # "评论" 或 "评论 5"
            r"^举报/反馈$",
            r"^立即解锁",
            r"^立即购买",
            r"^作者声明[：:]",
            r"^敬请期待更多",
            r"^没有更多",
            r"^专栏简介[：:]?",
            r"^发表神评妙论",
            r"^发表评论",
            r"^精彩评论",
            r"^热门评论",
            r"^查看全部评论",
            r"^发表$",
            r"^©\s*Baidu",
        ]
        # 仅仿写流程：在付费墙处截断（读者看不到后面的内容）
        if truncate_at_paywall:
            tail_markers.insert(0, r"^剩余\d+%未读$")
        for i in range(start_idx, len(lines)):
            stripped = lines[i].strip()
            if not stripped:
                continue
            for pat in tail_markers:
                if re.match(pat, stripped):
                    end_idx = i
                    break
            if end_idx != len(lines):
                break

        # 回退尾部的空行
        while end_idx > start_idx and not lines[end_idx - 1].strip():
            end_idx -= 1

        return "\n".join(lines[start_idx:end_idx])


class SmartFetcher:
    """智能抓取器：自动选择静态或动态抓取"""

    def __init__(
        self,
        timeout: int = 30000,
        headless: bool = True,
        user_agent: Optional[str] = None,
        log_dir: str = "./logs",
    ):
        from .base import ContentFetcher

        self.static_fetcher = ContentFetcher(timeout=timeout // 1000, user_agent=user_agent, log_dir=log_dir)
        self.dynamic_fetcher = PlaywrightFetcher(timeout=timeout, headless=headless, user_agent=user_agent, log_dir=log_dir)

    def should_use_dynamic(self, url: str) -> bool:
        """判断是否需要使用动态抓取"""
        # 这些域名需要动态抓取
        dynamic_domains = [
            "toutiao.com",
            "mp.weixin.qq.com",
            "zhihu.com",
            "jianshu.com",
            "bilibili.com",
            "mbd.baidu.com",
            "baijiahao.baidu.com",
        ]

        return any(domain in url for domain in dynamic_domains)

    async def fetch(self, url: str, truncate_at_paywall: bool = False) -> dict:
        """智能抓取"""
        if self.should_use_dynamic(url):
            logger.info("使用动态抓取（Playwright）")
            return await self.dynamic_fetcher.fetch_from_url(url, truncate_at_paywall=truncate_at_paywall)
        else:
            logger.info("使用静态抓取")
            return await self.static_fetcher.fetch_from_url(url)

    async def fetch_from_url(self, url: str, truncate_at_paywall: bool = False) -> dict:
        """兼容接口"""
        return await self.fetch(url, truncate_at_paywall=truncate_at_paywall)

    def fetch_from_text(self, content: str) -> str:
        """从文本获取内容（直接返回）"""
        return content


def create_playwright_fetcher(
    timeout: int = 30000,
    headless: bool = True,
    user_agent: Optional[str] = None,
) -> PlaywrightFetcher:
    """创建Playwright抓取器实例"""
    return PlaywrightFetcher(timeout=timeout, headless=headless, user_agent=user_agent)


def create_smart_fetcher(
    timeout: int = 30000,
    headless: bool = True,
    user_agent: Optional[str] = None,
) -> SmartFetcher:
    """创建智能抓取器实例"""
    return SmartFetcher(timeout=timeout, headless=headless, user_agent=user_agent)
