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


class EmotionPipeline:
    """情感标题生文流水线（新流程）"""

    def __init__(self, yuanbao: YuanbaoClient, output_dir="./output", progress_callback=None):
        self.yuanbao = yuanbao
        self.output_dir = output_dir
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

    async def run_step1(self) -> dict:
        """
        执行第一步：生成30个爆款标题

        Returns:
            {
                "success": bool,
                "titles": list,
                "error": str
            }
        """
        result = {
            "success": False,
            "titles": None,
            "error": None,
        }

        try:
            self._log("[情感流程] 第一步：生成30个爆款标题...", "info")

            # 新建对话
            self._log("[INFO] 新建元宝对话...", "info")
            self.yuanbao.reset()
            await self.yuanbao.new_conversation()

            # 生成标题
            from .prompts import Prompts
            prompt = Prompts.build_emotion_step1()
            response = await self.yuanbao.ask(prompt, timeout=600, step="emotion_1_标题")

            # 解析标题（每行一个）
            titles = [line.strip() for line in response.split("\n") if line.strip()]

            result["titles"] = titles
            result["success"] = True
            self._log(f"[OK] 生成 {len(titles)} 个标题", "success")

        except Exception as e:
            error_msg = str(e)
            result["error"] = error_msg
            self._log(f"[ERR] 生成标题失败: {error_msg}", "error")
            logger.exception("EmotionPipeline step1 error")

        return result

    async def run_step2(self, title: str) -> dict:
        """
        执行第二步：创作付费前内容

        Args:
            title: 选定的标题

        Returns:
            {
                "success": bool,
                "title": str,
                "article": str,
                "word_count": int,
                "error": str
            }
        """
        result = {
            "success": False,
            "title": title,
            "article": None,
            "word_count": 0,
            "error": None,
        }

        try:
            self._log(f"[情感流程] 第二步：创作付费前内容（标题：{title[:30]}...）...", "info")

            # 随机延迟
            await self._random_delay("生成标题后")

            # 创作付费前内容
            from .prompts import Prompts
            prompt = Prompts.build_emotion_step2(title)
            article = await self.yuanbao.ask(prompt, timeout=1200, step="emotion_2_付费前")

            # 清理 markdown 代码块标记
            article = self._clean_article(article)

            # 计算字数
            word_count = self._count_chinese_chars(article)

            result["article"] = article
            result["word_count"] = word_count
            result["success"] = True
            self._log(f"[OK] 付费前内容完成（{word_count}字）", "success")

        except Exception as e:
            error_msg = str(e)
            result["error"] = error_msg
            self._log(f"[ERR] 创作付费前内容失败: {error_msg}", "error")
            logger.exception("EmotionPipeline step2 error")

        return result

    async def run_step3(self, previous_content: str) -> dict:
        """
        执行第三步：续写结局

        Args:
            previous_content: 前面的文章内容

        Returns:
            {
                "success": bool,
                "article": str,
                "word_count": int,
                "error": str
            }
        """
        result = {
            "success": False,
            "article": None,
            "word_count": 0,
            "error": None,
        }

        try:
            self._log("[情感流程] 第三步：续写结局...", "info")

            # 随机延迟
            await self._random_delay("付费前内容后")

            # 续写结局
            from .prompts import Prompts
            prompt = Prompts.build_emotion_step3()
            article = await self.yuanbao.ask(prompt, timeout=1200, step="emotion_3_结局")

            # 清理 markdown 代码块标记
            article = self._clean_article(article)

            # 计算字数
            word_count = self._count_chinese_chars(article)

            result["article"] = article
            result["word_count"] = word_count
            result["success"] = True
            self._log(f"[OK] 结局完成（{word_count}字）", "success")

        except Exception as e:
            error_msg = str(e)
            result["error"] = error_msg
            self._log(f"[ERR] 续写结局失败: {error_msg}", "error")
            logger.exception("EmotionPipeline step3 error")

        return result

    async def run_all(self, progress_callback=None) -> dict:
        """
        执行完整流程：生成30个标题并循环处理

        Returns:
            {
                "success": bool,
                "total": int,
                "completed": int,
                "results": list,
                "error": str
            }
        """
        result = {
            "success": False,
            "total": 30,
            "completed": 0,
            "results": [],
            "error": None,
        }

        try:
            # 第一步：生成30个标题
            if progress_callback:
                progress_callback("正在生成30个爆款标题...", "info")

            self.yuanbao.reset()
            await self.yuanbao.new_conversation()

            from .prompts import Prompts
            prompt = Prompts.build_emotion_step1()
            response = await self.yuanbao.ask(prompt, timeout=600, step="emotion_1_标题")

            # 解析标题（更智能的解析）
            titles = self._parse_titles(response)

            # 保存标题到文件
            self._save_titles(titles)

            if progress_callback:
                progress_callback(f"已生成 {len(titles)} 个标题，开始批量处理...", "success")

            # 循环处理每个标题
            for i, title in enumerate(titles, 1):
                if progress_callback:
                    progress_callback(f"[{i}/{len(titles)}] 正在处理: {title[:30]}...", "info")

                # 每篇新建会话
                self.yuanbao.reset()
                await self.yuanbao.new_conversation()

                article_result = await self._process_one_article(title)
                result["results"].append(article_result)

                if article_result.get("success"):
                    result["completed"] += 1
                    if progress_callback:
                        progress_callback(f"[{i}/{len(titles)}] 完成: {title[:30]}", "success")
                else:
                    if progress_callback:
                        progress_callback(f"[{i}/{len(titles)}] 失败: {article_result.get('error')}", "error")

                # 随机延时（最后一条不需要延时）
                if i < len(titles):
                    await self._random_delay(f"第{i}个完成后")

            result["success"] = True

        except Exception as e:
            error_msg = str(e)
            result["error"] = error_msg
            if progress_callback:
                progress_callback(f"[ERR] 批量处理失败: {error_msg}", "error")
            logger.exception("EmotionPipeline run_all error")

        return result

    async def _process_one_article(self, title: str) -> dict:
        """
        处理单个文章：付费前+结局

        Returns:
            {
                "success": bool,
                "title": str,
                "paid_content": str,
                "ending_content": str,
                "paid_word_count": int,
                "ending_word_count": int,
                "output_file": str,
                "error": str
            }
        """
        result = {
            "success": False,
            "title": title,
            "paid_content": None,
            "ending_content": None,
            "paid_word_count": 0,
            "ending_word_count": 0,
            "output_file": None,
            "error": None,
        }

        try:
            # 第二步：创作付费前内容
            from .prompts import Prompts
            prompt = Prompts.build_emotion_step2(title)
            paid_content_raw = await self.yuanbao.ask(prompt, timeout=1200, step="emotion_2_付费前")
            paid_content = self._clean_article(paid_content_raw)
            paid_word_count = self._count_chinese_chars(paid_content)

            # 保存第二步原始输出
            self._save_step_output(title, "2_付费前", prompt, paid_content_raw)

            # 第三步：续写结局
            prompt = Prompts.build_emotion_step3()
            ending_content_raw = await self.yuanbao.ask(prompt, timeout=1200, step="emotion_3_结局")
            ending_content = self._clean_article(ending_content_raw)
            ending_word_count = self._count_chinese_chars(ending_content)

            # 保存第三步原始输出
            self._save_step_output(title, "3_结局", prompt, ending_content_raw)

            # 保存文件（付费前和结局用付费处分隔）
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title[:50])
            output_file = f"{self.output_dir}/{safe_title}_情感文.docx"

            # 确保付费前内容以付费标记结尾
            paywall_marker = "**【此处为付费节点，后续内容更加精彩，请看下集】**"
            if not paid_content.strip().endswith("下集】**"):
                paid_content = paid_content + "\n\n" + paywall_marker

            self.formatter.save_emotion_article(
                title=title,
                article=paid_content + "\n\n" + ending_content,
                filepath=output_file,
            )

            result["paid_content"] = paid_content
            result["ending_content"] = ending_content
            result["paid_word_count"] = paid_word_count
            result["ending_word_count"] = ending_word_count
            result["output_file"] = output_file
            result["success"] = True

        except Exception as e:
            result["error"] = str(e)
            logger.exception(f"EmotionPipeline _process_one_article error for {title}")

        return result

    def _parse_titles(self, response: str) -> list:
        """智能解析AI返回的标题列表"""
        import re

        titles = []
        lines = response.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 过滤掉明显不是标题的行
            if line.startswith("##") or line.startswith("#") or line.startswith("参考："):
                continue
            if "模版" in line or "类型" in line or "参考" in line:
                continue

            # 去掉序号（支持 "1. "、"1、" "①、" 等格式）
            line = re.sub(r'^[\d①②③④⑤⑥⑦⑧⑨⑩]+[\.\、:：]\s*', '', line)
            line = re.sub(r'^[\-\*]+\s*', '', line)

            # 如果行太短（小于10字），可能不是标题，跳过
            if len(line) < 10:
                continue

            # 如果行太长（超过100字），可能包含多个标题，尝试分割
            if len(line) > 100:
                # 尝试按句号或分号分割
                parts = re.split(r'[。；;]', line)
                for part in parts:
                    part = part.strip()
                    if len(part) >= 10:
                        titles.append(part)
                        if len(titles) >= 30:
                            break
            else:
                titles.append(line)

            if len(titles) >= 30:
                break

        return titles[:30]  # 最多30个

    def _save_titles(self, titles: list):
        """保存标题到文件"""
        from pathlib import Path
        from datetime import datetime

        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.output_dir}/情感标题列表_{timestamp}.txt"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"标题数量: {len(titles)}\n")
            f.write("=" * 50 + "\n\n")
            for i, title in enumerate(titles, 1):
                f.write(f"{i}. {title}\n")

        self._log(f"[OK] 标题已保存: {filename}", "success")

    def _save_step_output(self, title: str, step_name: str, prompt: str, output: str):
        """保存每步的输入输出到文件"""
        from pathlib import Path
        from datetime import datetime

        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 生成安全文件名
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title[:30])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.output_dir}/{safe_title}_{step_name}_{timestamp}.txt"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"标题: {title}\n")
            f.write(f"步骤: {step_name}\n")
            f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
            f.write("【输入提示词】\n")
            f.write(prompt + "\n\n")
            f.write("=" * 50 + "\n\n")
            f.write("【AI输出】\n")
            f.write(output + "\n")

        self._log(f"[OK] {step_name}原始输出已保存: {filename}", "info")

    async def save_full_article(self, title: str, paid_content: str, ending_content: str) -> str:
        """
        保存完整文章

        Returns:
            output_file: 保存的文件路径
        """
        import re
        from pathlib import Path

        # 合并内容
        full_content = paid_content + "\n\n" + ending_content

        # 生成安全文件名
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title[:50])
        output_file = f"{self.output_dir}/{safe_title}_情感文.docx"

        # 保存文件
        self.formatter.save_emotion_article(
            title=title,
            article=full_content,
            filepath=output_file,
        )

        self._log(f"[DONE] 完成！已保存: {output_file}", "success")
        return output_file

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

    @staticmethod
    def _count_chinese_chars(text: str) -> int:
        """计算中文字数（不含标点符号）"""
        import re
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        return len(chinese_chars)


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
