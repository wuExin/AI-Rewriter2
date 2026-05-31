"""
GUI 界面（customtkinter）
元宝专用文章改写工具
"""
import asyncio
import queue
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
import yaml
from loguru import logger

from .pipeline import RewritePipeline
from .yuanbao import YuanbaoClient
from .zhipu import ZhipuClient
from .deepseek import DeepSeekClient

def _get_base_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent

CONFIG_PATH = _get_base_dir() / "config.yaml"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=1000)


class App(ctk.CTk):

    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("AI文章改写工具 V2 - 元宝版")
        self.geometry("800x700")
        self.minsize(700, 600)

        self.log_queue = queue.Queue()
        self.progress_queue = queue.Queue()
        self.results = []

        # 流程选择：默认新流程
        self.process_mode = ctk.StringVar(value="emotion")  # emotion=新流程, rewrite=旧流程
        # 模型选择：默认元宝
        self.model_mode = ctk.StringVar(value="yuanbao")  # yuanbao=元宝, zhipu=智谱, deepseek=DeepSeek

        self._build_ui()
        self._process_queues()

    # ─── UI 构建 ───

    def _build_ui(self):
        # 标题
        ctk.CTkLabel(
            self, text="AI文章改写工具 V2 - 元宝版",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(pady=(15, 5))

        # 流程选择区
        mode_frame = ctk.CTkFrame(self)
        mode_frame.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(mode_frame, text="选择流程：", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=10, pady=5)

        ctk.CTkRadioButton(
            mode_frame, text="情感标题生文", variable=self.process_mode,
            value="emotion", command=self.on_mode_change
        ).pack(side="left", padx=5)

        ctk.CTkRadioButton(
            mode_frame, text="佛学文化", variable=self.process_mode,
            value="buddhism", command=self.on_mode_change
        ).pack(side="left", padx=5)

        ctk.CTkRadioButton(
            mode_frame, text="命理玄学", variable=self.process_mode,
            value="fortune", command=self.on_mode_change
        ).pack(side="left", padx=5)

        ctk.CTkRadioButton(
            mode_frame, text="情感文仿写", variable=self.process_mode,
            value="imitation", command=self.on_mode_change
        ).pack(side="left", padx=5)

        ctk.CTkRadioButton(
            mode_frame, text="文章改写", variable=self.process_mode,
            value="rewrite", command=self.on_mode_change
        ).pack(side="left", padx=5)

        # 模型选择区
        model_frame = ctk.CTkFrame(self)
        model_frame.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(model_frame, text="选择模型：", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=10, pady=5)

        ctk.CTkRadioButton(
            model_frame, text="腾讯元宝", variable=self.model_mode,
            value="yuanbao", command=self.on_model_change
        ).pack(side="left", padx=5)

        ctk.CTkRadioButton(
            model_frame, text="智谱GLM", variable=self.model_mode,
            value="zhipu", command=self.on_model_change
        ).pack(side="left", padx=5)

        ctk.CTkRadioButton(
            model_frame, text="DeepSeek", variable=self.model_mode,
            value="deepseek", command=self.on_model_change
        ).pack(side="left", padx=5)

        # 输入区
        self.input_frame = ctk.CTkFrame(self)
        self.input_frame.pack(fill="x", padx=20, pady=5)

        self.input_label = ctk.CTkLabel(self.input_frame, text="输入文章 URL（每行一个）：")
        self.input_label.pack(anchor="w", padx=10, pady=(5, 0))

        self.url_input = ctk.CTkTextbox(self.input_frame, height=180)
        self.url_input.pack(fill="x", padx=10, pady=5)
        self.url_input.insert("1.0", "https://mbd.baidu.com/newspage/data/landingsuper?pageType=1&context=%7B%22nid%22%3A%22news_9513274482372641098%22%7D")
        self.url_input.bind("<FocusIn>", self._clear_placeholder)
        self._placeholder_active = True

        # 情感流程：标题选择区（默认隐藏）
        self.emotion_frame = ctk.CTkFrame(self)
        ctk.CTkLabel(self.emotion_frame, text="情感标题生文流程：").pack(anchor="w", padx=10, pady=(5, 0))
        ctk.CTkLabel(self.emotion_frame, text="点击按钮后将生成30个标题并依次处理（付费前+结局），每次之间有随机延时", font=ctk.CTkFont(size=10), text_color="gray").pack(anchor="w", padx=10, pady=(0, 5))

        # 佛学流程
        self.buddhism_frame = ctk.CTkFrame(self)
        ctk.CTkLabel(self.buddhism_frame, text="佛学传统文化流程：").pack(anchor="w", padx=10, pady=(5, 0))
        ctk.CTkLabel(self.buddhism_frame, text="点击按钮后将生成15个佛学/传统文化标题并依次生成5000-10000字文章，每次之间有随机延时", font=ctk.CTkFont(size=10), text_color="gray").pack(anchor="w", padx=10, pady=(0, 5))

        # 命理流程
        self.fortune_frame = ctk.CTkFrame(self)
        ctk.CTkLabel(self.fortune_frame, text="命理玄学流程：").pack(anchor="w", padx=10, pady=(5, 0))
        ctk.CTkLabel(self.fortune_frame, text="点击按钮后将生成15个命理/玄学标题并依次生成5000-7000字文章，每次之间有随机延时", font=ctk.CTkFont(size=10), text_color="gray").pack(anchor="w", padx=10, pady=(0, 5))

        # 仿写流程（无提示frame，直接复用input_frame）

        # 按钮区
        self.btn_frame = ctk.CTkFrame(self)
        self.btn_frame.pack(fill="x", padx=20, pady=5)

        # 情感流程按钮
        self.emotion_batch_btn = ctk.CTkButton(
            self.btn_frame, text="开始批量生成（30篇）", fg_color="#E74C3C", hover_color="#C0392B",
            command=self.emotion_batch_start,
        )

        # 佛学流程按钮
        self.buddhism_batch_btn = ctk.CTkButton(
            self.btn_frame, text="开始批量生成（15篇佛学）", fg_color="#8E44AD", hover_color="#7D3C98",
            command=self.buddhism_batch_start,
        )

        # 命理流程按钮
        self.fortune_batch_btn = ctk.CTkButton(
            self.btn_frame, text="开始批量生成（15篇命理）", fg_color="#D4AC0D", hover_color="#B7950B",
            command=self.fortune_batch_start,
        )

        # 仿写流程按钮
        self.imitation_start_btn = ctk.CTkButton(
            self.btn_frame, text="开始仿写", fg_color="#1ABC9C", hover_color="#16A085",
            command=self.imitation_start,
        )

        # 改写流程按钮
        self.start_btn = ctk.CTkButton(
            self.btn_frame, text="开始改写", fg_color="#2CC985", hover_color="#25A873",
            command=self.start_rewrite,
        )

        # 通用按钮
        ctk.CTkButton(
            self.btn_frame, text="清空", fg_color="#FF6B6B", hover_color="#E55555",
            command=self.clear_all, width=80,
        ).pack(side="left", padx=5, pady=5)

        ctk.CTkButton(
            self.btn_frame, text="打开输出目录",
            command=self.open_output_dir, width=120,
        ).pack(side="left", padx=5, pady=5)

        ctk.CTkButton(
            self.btn_frame, text="提示词设置",
            command=self.open_prompt_settings, width=100,
        ).pack(side="right", padx=5, pady=5)

        ctk.CTkButton(
            self.btn_frame, text="设置",
            command=self.open_settings, width=80,
        ).pack(side="right", padx=5, pady=5)

        # 默认显示新流程UI（需要在按钮创建后调用）
        self.on_mode_change()

        # 进度区
        progress_frame = ctk.CTkFrame(self)
        progress_frame.pack(fill="x", padx=20, pady=5)

        self.progress_label = ctk.CTkLabel(progress_frame, text="就绪")
        self.progress_label.pack(anchor="w", padx=10, pady=(5, 0))

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_bar.set(0)

        # 日志区
        log_frame = ctk.CTkFrame(self)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(5, 15))

        ctk.CTkLabel(log_frame, text="运行日志：").pack(anchor="w", padx=10, pady=(5, 0))

        self.log_text = ctk.CTkTextbox(log_frame, state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

    # ─── 事件处理 ───

    def _clear_placeholder(self, event=None):
        if self._placeholder_active:
            self.url_input.delete("1.0", "end")
            self._placeholder_active = False

    def clear_all(self):
        self.url_input.delete("1.0", "end")
        self._placeholder_active = False
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self.progress_bar.set(0)
        self.progress_label.configure(text="就绪")
        self.results = []

    def open_output_dir(self):
        cfg = load_config()
        output_dir = cfg.get("output", {}).get("output_dir", "./output")
        path = Path(output_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def get_urls(self) -> list:
        text = self.url_input.get("1.0", "end").strip()
        urls = []
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("http://") or line.startswith("https://"):
                urls.append(line)
        return urls

    def _create_model_client(self, cfg: dict):
        """根据选择的模型创建客户端"""
        model = self.model_mode.get()

        if model == "zhipu":
            # 智谱客户端
            zhipu_cfg = cfg.get("zhipu", {})
            return ZhipuClient(
                api_key=zhipu_cfg.get("api_key", ""),
                model=zhipu_cfg.get("model", "glm-4-plus"),
                timeout=zhipu_cfg.get("timeout", 600),
                delay_min=zhipu_cfg.get("delay_min", 0),
                delay_max=zhipu_cfg.get("delay_max", 0),
            )
        elif model == "deepseek":
            # DeepSeek客户端
            deepseek_cfg = cfg.get("deepseek", {})
            return DeepSeekClient(
                api_key=deepseek_cfg.get("api_key", ""),
                model=deepseek_cfg.get("model", "deepseek-reasoner"),
                timeout=deepseek_cfg.get("timeout", 600),
                delay_min=deepseek_cfg.get("delay_min", 0),
                delay_max=deepseek_cfg.get("delay_max", 0),
            )
        else:
            # 元宝客户端（默认）
            yuanbao_cfg = cfg.get("yuanbao", {})
            return YuanbaoClient(
                opencli_path=yuanbao_cfg.get("opencli_path", "opencli"),
                think=yuanbao_cfg.get("think", False),
                search=yuanbao_cfg.get("search", False),
                timeout=yuanbao_cfg.get("timeout", 600),
            )

    # ─── 流程模式切换 ───

    def on_mode_change(self):
        """处理流程模式切换"""
        mode = self.process_mode.get()

        # 先隐藏所有内容区
        self.input_frame.pack_forget()
        self.emotion_frame.pack_forget()
        self.buddhism_frame.pack_forget()
        self.fortune_frame.pack_forget()
        if mode == "emotion":
            self.emotion_frame.pack(fill="x", padx=20, pady=5)
        elif mode == "buddhism":
            self.buddhism_frame.pack(fill="x", padx=20, pady=5)
        elif mode == "fortune":
            self.fortune_frame.pack(fill="x", padx=20, pady=5)
        elif mode == "imitation":
            self.input_frame.pack(fill="x", padx=20, pady=5)
        else:
            self.input_frame.pack(fill="x", padx=20, pady=5)

        self._update_buttons()

    def on_model_change(self):
        """处理模型切换"""
        model = self.model_mode.get()
        if model == "zhipu":
            self._append_log("已切换到智谱GLM模型", "info")
        elif model == "deepseek":
            self._append_log("已切换到DeepSeek模型", "info")
        else:
            self._append_log("已切换到腾讯元宝模型", "info")

    def _update_buttons(self):
        """根据流程模式更新按钮显示"""
        mode = self.process_mode.get()

        # 先隐藏所有流程按钮
        self.emotion_batch_btn.pack_forget()
        self.buddhism_batch_btn.pack_forget()
        self.fortune_batch_btn.pack_forget()
        self.imitation_start_btn.pack_forget()
        self.start_btn.pack_forget()

        if mode == "emotion":
            self.emotion_batch_btn.pack(side="left", padx=5, pady=5)
        elif mode == "buddhism":
            self.buddhism_batch_btn.pack(side="left", padx=5, pady=5)
        elif mode == "fortune":
            self.fortune_batch_btn.pack(side="left", padx=5, pady=5)
        elif mode == "imitation":
            self.imitation_start_btn.pack(side="left", padx=5, pady=5)
        else:
            self.start_btn.pack(side="left", padx=5, pady=5)

    # ─── 情感标题生文流程（新流程）───

    def emotion_batch_start(self):
        """批量生成30篇文章"""
        self.emotion_batch_btn.configure(state="disabled", text="批量生成中...")
        self._append_log("开始批量生成情感文章（30篇）...", "info")

        thread = threading.Thread(target=self._run_emotion_batch, daemon=True)
        thread.start()

    def _run_emotion_batch(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            cfg = load_config()
            output_dir = cfg.get("output", {}).get("output_dir", "./output")

            # 根据选择的模型创建客户端
            model_client = self._create_model_client(cfg)

            from .pipeline import EmotionPipeline

            def safe_callback(msg, level):
                self.log_queue.put((msg, level))
                self.progress_queue.put((0, 30, msg))

            pipeline = EmotionPipeline(
                model_client=model_client,
                output_dir=output_dir,
                progress_callback=safe_callback,
            )

            result = loop.run_until_complete(
                asyncio.wait_for(pipeline.run_all(progress_callback=safe_callback), timeout=3600*24)  # 24小时超时
            )

            if result.get("success"):
                completed = result.get("completed", 0)
                total = result.get("total", 30)
                safe_callback(f"批量生成完成！成功 {completed}/{total} 篇", "success")
                self.progress_queue.put((total, total, "批量生成完成"))
            else:
                safe_callback(f"批量生成失败: {result.get('error')}", "error")

        except Exception as e:
            self.log_queue.put((f"批量生成异常: {e}", "error"))
        finally:
            loop.close()
            self.after(0, lambda: self.emotion_batch_btn.configure(state="normal", text="开始批量生成（30篇）"))

    # ─── 情感文仿写三步法流程 ───

    def imitation_start(self):
        """开始仿写流程"""
        urls = self.get_urls()
        if not urls:
            self._append_log("请输入有效的 URL", "error")
            return

        self.imitation_start_btn.configure(state="disabled", text="仿写中...")
        self.results = []

        thread = threading.Thread(target=self._run_imitation, args=(urls,), daemon=True)
        thread.start()

    def _run_imitation(self, urls: list):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            cfg = load_config()
            output_dir = cfg.get("output", {}).get("output_dir", "./output")

            model_client = self._create_model_client(cfg)

            def safe_callback(msg, level):
                self.log_queue.put((msg, level))

            from .pipeline import ImitationPipeline

            pipeline = ImitationPipeline(
                yuanbao=model_client,
                output_dir=output_dir,
                progress_callback=safe_callback,
            )

            total = len(urls)
            for i, url in enumerate(urls):
                self.progress_queue.put((i, total, f"仿写第 {i+1}/{total} 篇"))
                safe_callback(f"{'='*40}", "info")
                safe_callback(f"开始仿写第 {i+1}/{total} 篇: {url}", "info")

                try:
                    result = loop.run_until_complete(
                        asyncio.wait_for(pipeline.run(url), timeout=3600)
                    )
                    self.results.append(result)
                except asyncio.TimeoutError:
                    safe_callback(f"仿写超时（60分钟）: {url}", "error")
                    self.results.append({"success": False, "original_url": url, "error": "超时"})
                except Exception as e:
                    safe_callback(f"仿写异常: {e}", "error")
                    self.results.append({"success": False, "original_url": url, "error": str(e)})

                # 随机延时（最后一篇不需要）
                if i < total - 1:
                    if self.model_mode.get() == "yuanbao":
                        yuanbao_cfg = cfg.get("yuanbao", {})
                        delay_min = yuanbao_cfg.get("delay_min", 1)
                        delay_max = yuanbao_cfg.get("delay_max", 15)
                        if delay_max > 0:
                            import random
                            delay_seconds = random.uniform(delay_min * 60, delay_max * 60)
                            delay_minutes = delay_seconds / 60
                            safe_callback(f"[延迟] 等待 {delay_minutes:.1f} 分钟后继续（防止封号）...", "info")
                            loop.run_until_complete(asyncio.sleep(delay_seconds))

            # 汇总
            self.progress_queue.put((total, total, "全部完成"))
            success_count = sum(1 for r in self.results if r.get("success"))
            safe_callback(f"{'='*40}", "info")
            safe_callback(f"仿写完成：共 {total} 篇，成功 {success_count} 篇，失败 {total - success_count} 篇", "success")

        except Exception as e:
            self.log_queue.put((f"仿写异常: {e}", "error"))
        finally:
            loop.close()
            self.after(0, lambda: self.imitation_start_btn.configure(state="normal", text="开始仿写"))

    # ─── 佛学流程 ───

    def buddhism_batch_start(self):
        """批量生成15篇佛学文章"""
        self.buddhism_batch_btn.configure(state="disabled", text="批量生成中...")
        self._append_log("开始批量生成佛学文章（15篇）...", "info")
        thread = threading.Thread(target=self._run_culture_batch, args=("buddhism",), daemon=True)
        thread.start()

    # ─── 命理流程 ───

    def fortune_batch_start(self):
        """批量生成15篇命理文章"""
        self.fortune_batch_btn.configure(state="disabled", text="批量生成中...")
        self._append_log("开始批量生成命理文章（15篇）...", "info")
        thread = threading.Thread(target=self._run_culture_batch, args=("fortune",), daemon=True)
        thread.start()

    def _run_culture_batch(self, culture_type: str):
        """佛学/命理批量生成通用方法"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        btn = self.buddhism_batch_btn if culture_type == "buddhism" else self.fortune_batch_btn
        btn_text = "开始批量生成（15篇佛学）" if culture_type == "buddhism" else "开始批量生成（15篇命理）"
        label = "佛学" if culture_type == "buddhism" else "命理"

        try:
            cfg = load_config()
            output_dir = cfg.get("output", {}).get("output_dir", "./output")
            model_client = self._create_model_client(cfg)

            from .pipeline import BuddhismPipeline, FortunePipeline

            PipelineClass = BuddhismPipeline if culture_type == "buddhism" else FortunePipeline

            def safe_callback(msg, level):
                self.log_queue.put((msg, level))
                self.progress_queue.put((0, 15, msg))

            pipeline = PipelineClass(
                model_client=model_client,
                output_dir=output_dir,
                progress_callback=safe_callback,
            )

            result = loop.run_until_complete(
                asyncio.wait_for(pipeline.run_all(progress_callback=safe_callback), timeout=3600*24)
            )

            if result.get("success"):
                completed = result.get("completed", 0)
                total = result.get("total", 15)
                safe_callback(f"{label}批量生成完成！成功 {completed}/{total} 篇", "success")
                self.progress_queue.put((total, total, f"{label}批量生成完成"))
            else:
                safe_callback(f"{label}批量生成失败: {result.get('error')}", "error")

        except Exception as e:
            self.log_queue.put((f"{label}批量生成异常: {e}", "error"))
        finally:
            loop.close()
            self.after(0, lambda: btn.configure(state="normal", text=btn_text))

    # ─── 改写流程 ───

    def start_rewrite(self):
        urls = self.get_urls()
        if not urls:
            self._append_log("请输入有效的 URL", "error")
            return

        self.start_btn.configure(state="disabled", text="处理中...")
        self.results = []

        thread = threading.Thread(target=self._run_rewrite, args=(urls,), daemon=True)
        thread.start()

    def _run_rewrite(self, urls: list):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            cfg = load_config()
            output_dir = cfg.get("output", {}).get("output_dir", "./output")

            # 根据选择的模型创建客户端
            model_client = self._create_model_client(cfg)

            def safe_callback(msg, level):
                self.log_queue.put((msg, level))

            pipeline = RewritePipeline(
                yuanbao=model_client,
                output_dir=output_dir,
                progress_callback=safe_callback,
            )

            total = len(urls)
            for i, url in enumerate(urls):
                self.progress_queue.put((i, total, f"处理第 {i+1}/{total} 篇"))
                safe_callback(f"{'='*40}", "info")
                safe_callback(f"开始处理第 {i+1}/{total} 篇: {url}", "info")

                try:
                    result = loop.run_until_complete(
                        asyncio.wait_for(pipeline.run(url), timeout=1800)
                    )
                    self.results.append(result)
                except asyncio.TimeoutError:
                    safe_callback(f"处理超时（30分钟）: {url}", "error")
                    self.results.append({"success": False, "original_url": url, "error": "超时"})
                except Exception as e:
                    safe_callback(f"处理异常: {e}", "error")
                    self.results.append({"success": False, "original_url": url, "error": str(e)})

                # 随机延时（最后一篇不需要延时）
                if i < total - 1:
                    # 元宝需要延时，智谱由客户端自己处理
                    if self.model_mode.get() == "yuanbao":
                        yuanbao_cfg = cfg.get("yuanbao", {})
                        delay_min = yuanbao_cfg.get("delay_min", 1)
                        delay_max = yuanbao_cfg.get("delay_max", 15)
                        if delay_max > 0:
                            import random
                            delay_seconds = random.uniform(delay_min * 60, delay_max * 60)
                            delay_minutes = delay_seconds / 60
                            safe_callback(f"[延迟] 等待 {delay_minutes:.1f} 分钟后继续（防止封号）...", "info")
                            loop.run_until_complete(asyncio.sleep(delay_seconds))

            # 汇总
            self.progress_queue.put((total, total, "全部完成"))
            success_count = sum(1 for r in self.results if r.get("success"))
            safe_callback(f"{'='*40}", "info")
            safe_callback(f"全部完成：共 {total} 篇，成功 {success_count} 篇，失败 {total - success_count} 篇", "success")

        except Exception as e:
            self.log_queue.put((f"运行异常: {e}", "error"))
        finally:
            loop.close()
            self.start_btn.configure(state="normal", text="开始改写")

    # ─── 日志与进度 ───

    def _process_queues(self):
        try:
            while True:
                msg, level = self.log_queue.get_nowait()
                self._append_log(msg, level)
        except queue.Empty:
            pass

        try:
            while True:
                current, total, message = self.progress_queue.get_nowait()
                if total > 0:
                    self.progress_bar.set(current / total)
                self.progress_label.configure(text=message)
        except queue.Empty:
            pass

        self.after(100, self._process_queues)

    def _append_log(self, message: str, level: str = "info"):
        icon = {"success": "[OK]", "error": "[ERR]", "warning": "[WARN]"}.get(level, "[INFO]")
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {icon} {message}\n"

        self.log_text.configure(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # ─── 设置窗口 ───

    def open_settings(self):
        cfg = load_config()
        yuanbao_cfg = cfg.get("yuanbao", {})
        zhipu_cfg = cfg.get("zhipu", {})
        deepseek_cfg = cfg.get("deepseek", {})

        win = ctk.CTkToplevel(self)
        win.title("设置")
        win.geometry("550x550")
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="设置", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        # 使用标签页
        tabview = ctk.CTkTabview(win, width=500, height=400)
        tabview.pack(padx=20, pady=10)

        # 元宝标签页
        yuanbao_tab = tabview.add("元宝")
        yuanbao_form = ctk.CTkFrame(yuanbao_tab)
        yuanbao_form.pack(fill="both", expand=True, padx=10, pady=10)

        # opencli 路径
        ctk.CTkLabel(yuanbao_form, text="opencli 路径：").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        opencli_var = ctk.StringVar(value=yuanbao_cfg.get("opencli_path", "opencli"))
        ctk.CTkEntry(yuanbao_form, textvariable=opencli_var, width=300).grid(row=0, column=1, padx=10, pady=5)

        # 超时
        ctk.CTkLabel(yuanbao_form, text="单步超时（秒）：").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        yuanbao_timeout_var = ctk.StringVar(value=str(yuanbao_cfg.get("timeout", 600)))
        ctk.CTkEntry(yuanbao_form, textvariable=yuanbao_timeout_var, width=300).grid(row=1, column=1, padx=10, pady=5)

        # 深度思考
        ctk.CTkLabel(yuanbao_form, text="深度思考：").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        think_var = ctk.BooleanVar(value=yuanbao_cfg.get("think", False))
        ctk.CTkSwitch(yuanbao_form, text="", variable=think_var).grid(row=2, column=1, sticky="w", padx=10, pady=5)

        # 联网搜索
        ctk.CTkLabel(yuanbao_form, text="联网搜索：").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        search_var = ctk.BooleanVar(value=yuanbao_cfg.get("search", False))
        ctk.CTkSwitch(yuanbao_form, text="", variable=search_var).grid(row=3, column=1, sticky="w", padx=10, pady=5)

        # 延迟范围（防止封号）
        delay_frame = ctk.CTkFrame(yuanbao_form)
        delay_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=10)

        ctk.CTkLabel(delay_frame, text="请求延迟（防止封号）", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 5))

        ctk.CTkLabel(delay_frame, text="最小（分钟）：").grid(row=1, column=0, sticky="w", padx=5)
        yuanbao_delay_min_var = ctk.StringVar(value=str(yuanbao_cfg.get("delay_min", 1)))
        ctk.CTkEntry(delay_frame, textvariable=yuanbao_delay_min_var, width=80).grid(row=1, column=1, padx=5)

        ctk.CTkLabel(delay_frame, text="最大（分钟）：").grid(row=1, column=2, sticky="w", padx=5)
        yuanbao_delay_max_var = ctk.StringVar(value=str(yuanbao_cfg.get("delay_max", 15)))
        ctk.CTkEntry(delay_frame, textvariable=yuanbao_delay_max_var, width=80).grid(row=1, column=3, padx=5)

        # 智谱标签页
        zhipu_tab = tabview.add("智谱")
        zhipu_form = ctk.CTkFrame(zhipu_tab)
        zhipu_form.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(zhipu_form, text="API Key：").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        zhipu_api_key_var = ctk.StringVar(value=zhipu_cfg.get("api_key", ""))
        api_key_entry = ctk.CTkEntry(zhipu_form, textvariable=zhipu_api_key_var, width=300, show="*")
        api_key_entry.grid(row=0, column=1, padx=10, pady=5)

        # 显示/隐藏密码按钮
        def toggle_api_key():
            if api_key_entry.cget("show") == "*":
                api_key_entry.configure(show="")
            else:
                api_key_entry.configure(show="*")
        ctk.CTkButton(zhipu_form, text="显示", command=toggle_api_key, width=60).grid(row=0, column=2, padx=5)

        ctk.CTkLabel(zhipu_form, text="模型名称：").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        zhipu_model_var = ctk.StringVar(value=zhipu_cfg.get("model", "glm-4-plus"))
        model_combo = ctk.CTkOptionMenu(
            zhipu_form, variable=zhipu_model_var,
            values=["glm-4-plus", "glm-4-flash", "glm-4-air", "glm-4"]
        )
        model_combo.grid(row=1, column=1, sticky="w", padx=10, pady=5)

        ctk.CTkLabel(zhipu_form, text="单步超时（秒）：").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        zhipu_timeout_var = ctk.StringVar(value=str(zhipu_cfg.get("timeout", 600)))
        ctk.CTkEntry(zhipu_form, textvariable=zhipu_timeout_var, width=300).grid(row=2, column=1, padx=10, pady=5)

        # 智谱延迟设置（防止API限流）
        zhipu_delay_frame = ctk.CTkFrame(zhipu_form)
        zhipu_delay_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=10, pady=10)

        ctk.CTkLabel(zhipu_delay_frame, text="请求延迟（防止API限流）", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 5))

        ctk.CTkLabel(zhipu_delay_frame, text="最小（分钟）：").grid(row=1, column=0, sticky="w", padx=5)
        zhipu_delay_min_var = ctk.StringVar(value=str(zhipu_cfg.get("delay_min", 0)))
        ctk.CTkEntry(zhipu_delay_frame, textvariable=zhipu_delay_min_var, width=80).grid(row=1, column=1, padx=5)

        ctk.CTkLabel(zhipu_delay_frame, text="最大（分钟）：").grid(row=1, column=2, sticky="w", padx=5)
        zhipu_delay_max_var = ctk.StringVar(value=str(zhipu_cfg.get("delay_max", 0)))
        ctk.CTkEntry(zhipu_delay_frame, textvariable=zhipu_delay_max_var, width=80).grid(row=1, column=3, padx=5)

        ctk.CTkLabel(
            zhipu_form,
            text="提示：智谱API Key可在 https://open.bigmodel.cn/ 获取",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        ).grid(row=4, column=0, columnspan=3, pady=5)

        # DeepSeek标签页
        deepseek_tab = tabview.add("DeepSeek")
        deepseek_form = ctk.CTkFrame(deepseek_tab)
        deepseek_form.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(deepseek_form, text="API Key：").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        deepseek_api_key_var = ctk.StringVar(value=deepseek_cfg.get("api_key", ""))
        deepseek_api_key_entry = ctk.CTkEntry(deepseek_form, textvariable=deepseek_api_key_var, width=300, show="*")
        deepseek_api_key_entry.grid(row=0, column=1, padx=10, pady=5)

        # 显示/隐藏密码按钮
        def toggle_deepseek_api_key():
            if deepseek_api_key_entry.cget("show") == "*":
                deepseek_api_key_entry.configure(show="")
            else:
                deepseek_api_key_entry.configure(show="*")
        ctk.CTkButton(deepseek_form, text="显示", command=toggle_deepseek_api_key, width=60).grid(row=0, column=2, padx=5)

        ctk.CTkLabel(deepseek_form, text="模型名称：").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        deepseek_model_var = ctk.StringVar(value=deepseek_cfg.get("model", "deepseek-reasoner"))
        deepseek_model_combo = ctk.CTkOptionMenu(
            deepseek_form, variable=deepseek_model_var,
            values=["deepseek-chat", "deepseek-coder", "deepseek-reasoner"]
        )
        deepseek_model_combo.grid(row=1, column=1, sticky="w", padx=10, pady=5)

        ctk.CTkLabel(deepseek_form, text="单步超时（秒）：").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        deepseek_timeout_var = ctk.StringVar(value=str(deepseek_cfg.get("timeout", 600)))
        ctk.CTkEntry(deepseek_form, textvariable=deepseek_timeout_var, width=300).grid(row=2, column=1, padx=10, pady=5)

        # DeepSeek延迟设置（防止API限流）
        deepseek_delay_frame = ctk.CTkFrame(deepseek_form)
        deepseek_delay_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=10, pady=10)

        ctk.CTkLabel(deepseek_delay_frame, text="请求延迟（防止API限流）", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 5))

        ctk.CTkLabel(deepseek_delay_frame, text="最小（分钟）：").grid(row=1, column=0, sticky="w", padx=5)
        deepseek_delay_min_var = ctk.StringVar(value=str(deepseek_cfg.get("delay_min", 0)))
        ctk.CTkEntry(deepseek_delay_frame, textvariable=deepseek_delay_min_var, width=80).grid(row=1, column=1, padx=5)

        ctk.CTkLabel(deepseek_delay_frame, text="最大（分钟）：").grid(row=1, column=2, sticky="w", padx=5)
        deepseek_delay_max_var = ctk.StringVar(value=str(deepseek_cfg.get("delay_max", 0)))
        ctk.CTkEntry(deepseek_delay_frame, textvariable=deepseek_delay_max_var, width=80).grid(row=1, column=3, padx=5)

        ctk.CTkLabel(
            deepseek_form,
            text="提示：DeepSeek API Key可在 https://platform.deepseek.com/ 获取",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        ).grid(row=4, column=0, columnspan=3, pady=5)

        # 通用标签页
        general_tab = tabview.add("通用")
        general_form = ctk.CTkFrame(general_tab)
        general_form.pack(fill="both", expand=True, padx=10, pady=10)

        # 输出目录
        ctk.CTkLabel(general_form, text="输出目录：").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        output_var = ctk.StringVar(value=cfg.get("output", {}).get("output_dir", "./output"))
        ctk.CTkEntry(general_form, textvariable=output_var, width=300).grid(row=0, column=1, padx=10, pady=5)

        def do_save():
            try:
                # 验证元宝延迟
                yuanbao_delay_min = int(yuanbao_delay_min_var.get())
                yuanbao_delay_max = int(yuanbao_delay_max_var.get())
                if yuanbao_delay_min < 0 or yuanbao_delay_max < 0:
                    self._append_log("元宝延迟值不能为负数", "error")
                    return
                if yuanbao_delay_min > yuanbao_delay_max:
                    self._append_log("元宝最小延迟不能大于最大延迟", "error")
                    return

                # 验证智谱延迟
                zhipu_delay_min = int(zhipu_delay_min_var.get())
                zhipu_delay_max = int(zhipu_delay_max_var.get())
                if zhipu_delay_min < 0 or zhipu_delay_max < 0:
                    self._append_log("智谱延迟值不能为负数", "error")
                    return
                if zhipu_delay_min > zhipu_delay_max:
                    self._append_log("智谱最小延迟不能大于最大延迟", "error")
                    return

                # 验证DeepSeek延迟
                deepseek_delay_min = int(deepseek_delay_min_var.get())
                deepseek_delay_max = int(deepseek_delay_max_var.get())
                if deepseek_delay_min < 0 or deepseek_delay_max < 0:
                    self._append_log("DeepSeek延迟值不能为负数", "error")
                    return
                if deepseek_delay_min > deepseek_delay_max:
                    self._append_log("DeepSeek最小延迟不能大于最大延迟", "error")
                    return

            except ValueError:
                self._append_log("延迟值必须是整数", "error")
                return

            # 保存元宝配置
            cfg["yuanbao"] = {
                "opencli_path": opencli_var.get(),
                "timeout": int(yuanbao_timeout_var.get()),
                "think": think_var.get(),
                "search": search_var.get(),
                "delay_min": yuanbao_delay_min,
                "delay_max": yuanbao_delay_max,
            }

            # 保存智谱配置
            cfg["zhipu"] = {
                "api_key": zhipu_api_key_var.get(),
                "model": zhipu_model_var.get(),
                "timeout": int(zhipu_timeout_var.get()),
                "delay_min": zhipu_delay_min,
                "delay_max": zhipu_delay_max,
            }

            # 保存DeepSeek配置
            cfg["deepseek"] = {
                "api_key": deepseek_api_key_var.get(),
                "model": deepseek_model_var.get(),
                "timeout": int(deepseek_timeout_var.get()),
                "delay_min": deepseek_delay_min,
                "delay_max": deepseek_delay_max,
            }

            # 保存通用配置
            cfg["output"] = {"output_dir": output_var.get()}

            save_config(cfg)
            self._append_log("设置已保存", "success")
            win.destroy()

        btn_frame = ctk.CTkFrame(win)
        btn_frame.pack(pady=15)

        ctk.CTkButton(btn_frame, text="保存", fg_color="#2CC985", command=do_save).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="取消", command=win.destroy).pack(side="left", padx=10)

    # ─── 提示词设置窗口 ───

    def open_prompt_settings(self):
        """打开提示词配置窗口（直接从 src/prompts.py 读取）"""
        win = ctk.CTkToplevel(self)
        win.title("提示词设置")
        win.geometry("700x650")
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="改写文章提示词（编辑 src/prompts.py）", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        # 提示词文本框
        frame = ctk.CTkFrame(win)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.prompt_text = ctk.CTkTextbox(frame, font=ctk.CTkFont("Microsoft YaHei", 12))
        self.prompt_text.pack(fill="both", expand=True, padx=10, pady=10)

        # 直接从 prompts.py 读取
        from .prompts import Prompts
        default_prompt = Prompts.REWRITE
        self.prompt_text.insert("1.0", default_prompt)

        # 提示信息
        info_label = ctk.CTkLabel(
            win,
            text="提示：{title} 会被替换为文章标题 | 修改后直接保存到 src/prompts.py",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        info_label.pack(pady=5)

        # 按钮区
        btn_frame = ctk.CTkFrame(win)
        btn_frame.pack(pady=15)

        def do_save():
            prompt_content = self.prompt_text.get("1.0", "end-1c")
            if not prompt_content.strip():
                self._append_log("提示词不能为空", "error")
                return

            # 直接更新 src/prompts.py 文件
            prompts_path = Path(__file__).parent / "prompts.py"
            try:
                with open(prompts_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # 找到 REWRITE = """\ 的位置，替换到下一个 """ 之前的内容
                import re
                pattern = r'(REWRITE = """\\\n)(.*?)(""")'
                replacement = r'REWRITE = """\\\n' + prompt_content + '\n"""'

                # 使用 MULTILINE 和 DOTALL 来匹配多行
                new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)

                with open(prompts_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                # 重新加载模块以更新内存中的提示词
                import importlib
                from . import prompts
                importlib.reload(prompts)

                self._append_log("提示词已保存到 src/prompts.py", "success")
                win.destroy()
            except Exception as e:
                self._append_log(f"保存失败: {e}", "error")

        ctk.CTkButton(btn_frame, text="保存", fg_color="#2CC985", command=do_save, width=100).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="取消", command=win.destroy, width=100).pack(side="left", padx=10)
