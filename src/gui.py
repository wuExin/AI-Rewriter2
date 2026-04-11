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

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


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
            mode_frame, text="情感标题生文（新流程）", variable=self.process_mode,
            value="emotion", command=self.on_mode_change
        ).pack(side="left", padx=5)

        ctk.CTkRadioButton(
            mode_frame, text="文章改写（旧流程）", variable=self.process_mode,
            value="rewrite", command=self.on_mode_change
        ).pack(side="left", padx=5)

        # 输入区
        self.input_frame = ctk.CTkFrame(self)
        self.input_frame.pack(fill="x", padx=20, pady=5)

        self.input_label = ctk.CTkLabel(self.input_frame, text="输入文章 URL（每行一个）：")
        self.input_label.pack(anchor="w", padx=10, pady=(5, 0))

        self.url_input = ctk.CTkTextbox(self.input_frame, height=120)
        self.url_input.pack(fill="x", padx=10, pady=5)
        self.url_input.insert("1.0", "https://www.toutiao.com/article/7624543829000995374")
        self.url_input.bind("<FocusIn>", self._clear_placeholder)
        self._placeholder_active = True

        # 情感流程：标题选择区（默认隐藏）
        self.emotion_frame = ctk.CTkFrame(self)

        ctk.CTkLabel(self.emotion_frame, text="情感标题生文流程：").pack(anchor="w", padx=10, pady=(5, 0))
        ctk.CTkLabel(self.emotion_frame, text="点击按钮后将生成30个标题并依次处理（付费前+结局），每次之间有随机延时", font=ctk.CTkFont(size=10), text_color="gray").pack(anchor="w", padx=10, pady=(0, 5))

        # 按钮区
        self.btn_frame = ctk.CTkFrame(self)
        self.btn_frame.pack(fill="x", padx=20, pady=5)

        # 新流程按钮
        self.emotion_batch_btn = ctk.CTkButton(
            self.btn_frame, text="开始批量生成（30篇）", fg_color="#E74C3C", hover_color="#C0392B",
            command=self.emotion_batch_start,
        )

        # 旧流程按钮
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

    # ─── 流程模式切换 ───

    def on_mode_change(self):
        """处理流程模式切换"""
        mode = self.process_mode.get()
        if mode == "emotion":
            # 新流程：显示情感流程说明，隐藏URL输入框
            self.input_frame.pack_forget()
            self.emotion_frame.pack(fill="x", padx=20, pady=5)
            self._update_buttons()
        else:
            # 旧流程：显示URL输入框，隐藏情感流程
            self.emotion_frame.pack_forget()
            self.input_frame.pack(fill="x", padx=20, pady=5)
            self._update_buttons()

    def _update_buttons(self):
        """根据流程模式更新按钮显示"""
        mode = self.process_mode.get()

        # 先隐藏所有流程按钮
        self.emotion_batch_btn.pack_forget()
        self.start_btn.pack_forget()

        if mode == "emotion":
            # 新流程：显示批量生成按钮
            self.emotion_batch_btn.pack(side="left", padx=5, pady=5)
        else:
            # 旧流程：显示开始改写按钮
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
            yuanbao_cfg = cfg.get("yuanbao", {})
            output_dir = cfg.get("output", {}).get("output_dir", "./output")

            yuanbao = YuanbaoClient(
                opencli_path=yuanbao_cfg.get("opencli_path", "opencli"),
                think=yuanbao_cfg.get("think", False),
                search=yuanbao_cfg.get("search", False),
                timeout=yuanbao_cfg.get("timeout", 600),
            )

            from .pipeline import EmotionPipeline

            def safe_callback(msg, level):
                self.log_queue.put((msg, level))
                self.progress_queue.put((0, 30, msg))

            pipeline = EmotionPipeline(
                yuanbao=yuanbao,
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
            yuanbao_cfg = cfg.get("yuanbao", {})
            output_dir = cfg.get("output", {}).get("output_dir", "./output")

            yuanbao = YuanbaoClient(
                opencli_path=yuanbao_cfg.get("opencli_path", "opencli"),
                think=yuanbao_cfg.get("think", False),
                search=yuanbao_cfg.get("search", False),
                timeout=yuanbao_cfg.get("timeout", 600),
            )

            def safe_callback(msg, level):
                self.log_queue.put((msg, level))

            pipeline = RewritePipeline(
                yuanbao=yuanbao,
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

        win = ctk.CTkToplevel(self)
        win.title("设置")
        win.geometry("480x480")
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="元宝设置", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        form = ctk.CTkFrame(win)
        form.pack(fill="x", padx=20, pady=5)

        # opencli 路径
        ctk.CTkLabel(form, text="opencli 路径：").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        opencli_var = ctk.StringVar(value=yuanbao_cfg.get("opencli_path", "opencli"))
        ctk.CTkEntry(form, textvariable=opencli_var, width=280).grid(row=0, column=1, padx=10, pady=5)

        # 超时
        ctk.CTkLabel(form, text="单步超时（秒）：").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        timeout_var = ctk.StringVar(value=str(yuanbao_cfg.get("timeout", 600)))
        ctk.CTkEntry(form, textvariable=timeout_var, width=280).grid(row=1, column=1, padx=10, pady=5)

        # 深度思考
        ctk.CTkLabel(form, text="深度思考：").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        think_var = ctk.BooleanVar(value=yuanbao_cfg.get("think", False))
        ctk.CTkSwitch(form, text="", variable=think_var).grid(row=2, column=1, sticky="w", padx=10, pady=5)

        # 联网搜索
        ctk.CTkLabel(form, text="联网搜索：").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        search_var = ctk.BooleanVar(value=yuanbao_cfg.get("search", False))
        ctk.CTkSwitch(form, text="", variable=search_var).grid(row=3, column=1, sticky="w", padx=10, pady=5)

        # 延迟范围（防止封号）
        delay_frame = ctk.CTkFrame(form)
        delay_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=10)

        ctk.CTkLabel(delay_frame, text="请求延迟（防止封号）", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 5))

        ctk.CTkLabel(delay_frame, text="最小（分钟）：").grid(row=1, column=0, sticky="w", padx=5)
        delay_min_var = ctk.StringVar(value=str(yuanbao_cfg.get("delay_min", 1)))
        ctk.CTkEntry(delay_frame, textvariable=delay_min_var, width=80).grid(row=1, column=1, padx=5)

        ctk.CTkLabel(delay_frame, text="最大（分钟）：").grid(row=1, column=2, sticky="w", padx=5)
        delay_max_var = ctk.StringVar(value=str(yuanbao_cfg.get("delay_max", 15)))
        ctk.CTkEntry(delay_frame, textvariable=delay_max_var, width=80).grid(row=1, column=3, padx=5)

        # 输出目录
        ctk.CTkLabel(form, text="输出目录：").grid(row=5, column=0, sticky="w", padx=10, pady=5)
        output_var = ctk.StringVar(value=cfg.get("output", {}).get("output_dir", "./output"))
        ctk.CTkEntry(form, textvariable=output_var, width=280).grid(row=5, column=1, padx=10, pady=5)

        def do_save():
            try:
                delay_min = int(delay_min_var.get())
                delay_max = int(delay_max_var.get())
                if delay_min < 0 or delay_max < 0:
                    self._append_log("延迟值不能为负数", "error")
                    return
                if delay_min > delay_max:
                    self._append_log("最小延迟不能大于最大延迟", "error")
                    return
            except ValueError:
                self._append_log("延迟值必须是整数", "error")
                return

            cfg["yuanbao"] = {
                "opencli_path": opencli_var.get(),
                "timeout": int(timeout_var.get()),
                "think": think_var.get(),
                "search": search_var.get(),
                "delay_min": delay_min,
                "delay_max": delay_max,
            }
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

                # 找到 REWRITE = """\n 的位置，替换到下一个 """ 之前的内容
                import re
                pattern = r'(REWRITE = """\n)(.*?)("""\s*$)'
                replacement = r'REWRITE = """\n' + prompt_content + '\n"""'

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
