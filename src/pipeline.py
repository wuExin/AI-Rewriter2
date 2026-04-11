"""
改写流程编排
抓取 → new → ask(分析) → ask(改写) → ask(标题) → 校验 → 保存
"""
import asyncio
import random
import re
from pathlib import Path
import yaml
from loguru import logger

from .yuanbao import YuanbaoClient
from .prompts import Prompts
from .validator import ArticleValidator, TitleValidator
from .formatter import OutputFormatter
from .fetcher import SmartFetcher


CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def load_config() -> dict:
    """加载配置文件"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


class RewritePipeline:
    """文章改写流水线"""

    def __init__(self, yuanbao: YuanbaoClient, output_dir="./output", progress_callback=None):
        self.yuanbao = yuanbao
        self.output_dir = output_dir
        self.fetcher = SmartFetcher(timeout=60000, headless=True)
        self.validator = ArticleValidator()
        self.formatter = OutputFormatter()
        self.progress_callback = progress_callback
        self.config = load_config()

    def _log(self, message: str, level: str = "info"):
        if self.progress_callback:
            self.progress_callback(message, level)
        logger.info(message)

    async def _random_delay(self, step_name: str = ""):
        """随机延迟，防止被封号"""
        yuanbao_cfg = self.config.get("yuanbao", {})
        delay_min = yuanbao_cfg.get("delay_min", 1)
        delay_max = yuanbao_cfg.get("delay_max", 15)

        if delay_max > 0:
            delay_seconds = random.uniform(delay_min * 60, delay_max * 60)
            delay_minutes = delay_seconds / 60
            self._log(f"[延迟] 等待 {delay_minutes:.1f} 分钟后继续（防止封号）...", "info")
            await asyncio.sleep(delay_seconds)

    async def run(self, url: str) -> dict:
        """
        执行完整改写流程

        Args:
            url: 文章 URL

        Returns:
            {
                "success": bool,
                "original_url": str,
                "original_title": str,
                "analysis": str,
                "article": str,
                "titles": list,
                "word_count": int,
                "output_file": str,
                "error": str
            }
        """
        result = {
            "success": False,
            "original_url": url,
            "original_title": "",
            "analysis": None,
            "article": None,
            "titles": None,
            "word_count": 0,
            "output_file": None,
            "error": None,
        }

        try:
            # ── 第 0 步：抓取原文 ──
            self._log(f"[1/4] 正在抓取文章: {url}", "info")
            fetch_result = await self.fetcher.fetch_from_url(url)
            title = fetch_result.get("title", "未知标题")
            article_content = fetch_result.get("content", "")
            result["original_title"] = title

            if not article_content or len(article_content) < 100:
                raise RuntimeError(f"抓取到的内容过短（{len(article_content)}字），请检查 URL")

            self._log(f"[OK] 抓取成功: {title[:30]}...（{len(article_content)}字）", "success")

            # ── 新建对话 ──
            self._log("[INFO] 新建元宝对话...", "info")
            self.yuanbao.reset()
            await self.yuanbao.new_conversation()

            # ── 第 1 步：分析文章 ──
            self._log("[2/4] 正在分析文章...", "info")
            prompt_analyze = Prompts.build_analyze(article_content)
            analysis = await self.yuanbao.ask(prompt_analyze, timeout=600, step="1_分析")
            result["analysis"] = analysis
            self._log("[OK] 分析完成", "success")

            # 随机延迟
            await self._random_delay("分析后")

            # ── 第 2 步：改写文章 ──
            self._log("[3/4] 正在改写文章（预计3-10分钟）...", "info")
            # 直接从 src/prompts.py 读取
            prompt_rewrite = Prompts.build_rewrite(title)
            article = await self.yuanbao.ask(prompt_rewrite, timeout=600, step="2_改写")

            # 清理 markdown 代码块标记
            article = self._clean_article(article)

            # 校验
            validation = self.validator.validate(article)
            result["word_count"] = validation["word_count"]

            if not validation["has_paywall"]:
                self._log("[WARN] 未检测到付费墙，自动插入", "warning")
                article = self.validator.insert_paywall(article)

            result["article"] = article

            if validation["issues"]:
                for issue in validation["issues"]:
                    self._log(f"[WARN] {issue}", "warning")

            self._log(f"[OK] 改写完成（{validation['word_count']}字）", "success")

            # 随机延迟
            await self._random_delay("改写后")

            # ── 第 3 步：生成标题 ──
            self._log("[4/4] 正在生成标题...", "info")
            prompt_titles = Prompts.build_titles(title)
            titles_response = await self.yuanbao.ask(prompt_titles, timeout=300, step="3_标题")
            titles = TitleValidator.parse_titles(titles_response)
            result["titles"] = titles
            self._log(f"[OK] 生成 {len(titles)} 个标题", "success")

            # ── 保存 ──
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
            output_file = f"{self.output_dir}/{safe_title}_改写.docx"

            self.formatter.save_to_file(
                original_url=url,
                titles=titles,
                article=article,
                filepath=output_file,
            )

            result["output_file"] = output_file
            result["success"] = True
            self._log(f"[DONE] 完成！已保存: {output_file}", "success")

        except Exception as e:
            error_msg = str(e)
            result["error"] = error_msg
            self._log(f"[ERR] 处理失败: {error_msg}", "error")
            logger.exception(f"Pipeline error for {url}")

        return result

    @staticmethod
    def _clean_article(article: str) -> str:
        """清理 markdown 代码块标记"""
        if article.startswith("```"):
            lines = article.split("\n")
            if lines[0].startswith("```"):
                for i, line in enumerate(lines[1:], 1):
                    if line.strip() == "```":
                        return "\n".join(lines[1:i])
                return "\n".join(lines[1:])
        return article.strip()
