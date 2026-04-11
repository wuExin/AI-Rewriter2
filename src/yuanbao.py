"""
元宝客户端
通过 opencli CLI 调用腾讯元宝（浏览器自动化）
"""
import asyncio
import json
import shlex
import sys
import tempfile
import os
from datetime import datetime
from pathlib import Path
from loguru import logger


class YuanbaoClient:
    """通过 opencli yuanbao 命令调用元宝的客户端（连续对话模式）"""

    def __init__(self, opencli_path="opencli", think=False, search=False, timeout=600, log_dir="./logs"):
        self.opencli_path = opencli_path
        self.think = think
        self.search = search
        self.timeout = timeout
        self._conversation_active = False
        self._step_counter = 0
        # 对话日志目录
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        # Windows 下解析 .cmd 文件，找到实际的 node 脚本路径
        self._node_script = self._resolve_node_script()

    def _resolve_node_script(self) -> str | None:
        """解析 opencli 入口脚本路径（支持本地项目目录或 .cmd 文件）"""
        import os
        logger.info(f"[DEBUG] 当前工作目录: {os.getcwd()}")
        logger.info(f"[DEBUG] opencli_path配置: {self.opencli_path}")

        opencli_path = Path(self.opencli_path)
        logger.info(f"[DEBUG] 解析后路径: {opencli_path}")
        logger.info(f"[DEBUG] 是否为目录: {opencli_path.is_dir()}")
        logger.info(f"[DEBUG] 绝对路径: {opencli_path.resolve()}")

        # 如果直接指向 main.js，直接用
        if opencli_path.suffix.lower() == ".js" and opencli_path.exists():
            logger.info(f"元宝：找到 node 脚本: {opencli_path}")
            return str(opencli_path)

        # 如果指向项目目录，查找 dist/main.js
        if opencli_path.is_dir():
            for sub in ["dist/src/main.js", "dist/main.js"]:
                js_path = opencli_path / sub
                logger.info(f"[DEBUG] 检查: {js_path}, 存在: {js_path.exists()}")
                if js_path.exists():
                    logger.info(f"元宝：找到 node 脚本: {js_path}")
                    return str(js_path)

        # Windows: 从 .cmd 文件解析 node_modules 中的入口
        if sys.platform == "win32" and opencli_path.suffix.lower() == ".cmd":
            candidates = [
                opencli_path.parent / "node_modules" / "@jackwener" / "opencli" / "dist" / "src" / "main.js",
                opencli_path.parent / "node_modules" / "@jackwener" / "opencli" / "dist" / "main.js",
            ]
            for js_path in candidates:
                if js_path.exists():
                    logger.info(f"元宝：找到 node 脚本: {js_path}")
                    return str(js_path)

        logger.warning(f"[DEBUG] 未找到 node 脚本，返回 None")
        return None

    def _get_node_executable(self) -> str:
        """获取node可执行文件路径，优先使用本地bundled版本"""
        # 优先级: 打包目录的 node/node.exe > 当前目录 node.exe > 系统 node
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后，_MEIPASS 是解压目录
            import os
            base_dir = Path(sys.executable).parent
        else:
            # 开发环境
            base_dir = Path(__file__).parent.parent

        # 检查 node/node.exe (打包版本)
        bundled_node = base_dir / "node" / "node.exe"
        if bundled_node.exists():
            logger.info(f"使用打包node: {bundled_node}")
            return str(bundled_node)

        # 检查当前目录的 node.exe
        local_node = base_dir / "node.exe"
        if local_node.exists():
            logger.info(f"使用本地node: {local_node}")
            return str(local_node)

        return "node"

    def _build_exec_args(self, *args) -> list[str]:
        """构建 create_subprocess_exec 的参数列表（用于无 prompt 的简单命令）"""
        if self._node_script:
            node_exe = self._get_node_executable()
            return [node_exe, self._node_script] + list(args)
        return [self.opencli_path] + list(args)

    async def new_conversation(self):
        """新建元宝对话"""
        logger.info("元宝：新建对话...")
        logger.info(f"[DEBUG] _node_script: {self._node_script}")
        cmd_args = self._build_exec_args("yuanbao", "new")
        logger.info(f"[DEBUG] 执行命令: {cmd_args}")
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)
            if stderr:
                logger.info(f"[DEBUG] stderr: {stderr.decode('utf-8', errors='replace')}")
        except Exception as e:
            logger.error(f"[DEBUG] new_conversation 错误: {e}")
            raise
        await asyncio.sleep(3)
        self._conversation_active = True
        logger.info("元宝：新对话已建立")

    @staticmethod
    def _parse_response(stdout: str) -> str:
        """从 opencli stdout 解析 Assistant 回复，过滤思考过程"""
        lines = stdout.strip().split("\n")
        # 找到最后一个 "Role: Assistant" 后面的 "Text: " 内容
        assistant_text = ""
        in_assistant = False
        for line in lines:
            if line.strip() == "Role: Assistant":
                in_assistant = True
                assistant_text = ""
                continue
            if in_assistant:
                if line.startswith("Text: "):
                    assistant_text = line[6:]
                elif line.startswith("Role: "):
                    in_assistant = False
                else:
                    assistant_text += "\n" + line
        return assistant_text.strip()

    def _save_log(self, step: str, prompt: str, response: str):
        """保存发送和接收的消息到日志文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._step_counter += 1
        log_file = self.log_dir / f"yuanbao_{timestamp}_{self._step_counter}_{step}.md"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"# 元宝对话日志 - {step}\n\n")
            f.write(f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"---\n\n")
            f.write(f"## 发送的消息（{len(prompt)}字）\n\n")
            f.write(f"{prompt}\n\n")
            f.write(f"---\n\n")
            f.write(f"## 元宝的回复（{len(response)}字）\n\n")
            f.write(f"{response}\n")
        logger.info(f"元宝：对话日志已保存: {log_file}")

    async def ask(self, prompt: str, timeout: int = None, step: str = "", max_retries: int = 2) -> str:
        """
        在当前对话中发送消息并等待回复，失败自动重试

        Args:
            prompt: 要发送的提示词
            timeout: 超时秒数（默认使用配置值）
            step: 步骤名称（用于日志）
            max_retries: 最大重试次数

        Returns:
            元宝的回复文本
        """
        effective_timeout = timeout or self.timeout

        if not self._conversation_active:
            await self.new_conversation()

        last_error = None
        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.warning(f"元宝：第 {attempt} 次重试（{step}）...")
                await asyncio.sleep(3)

            prompt_file = None
            wrapper_file = None

            try:
                # 使用 innerHTML 设置 Quill 内容，换行会被转为 <p> 标签，无需去掉
                prompt_flat = prompt

                # prompt 写入临时文件
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False, encoding="utf-8"
                ) as f:
                    f.write(prompt_flat)
                    prompt_file = f.name

                logger.info(f"元宝：发送消息，长度={len(prompt)}字，timeout={effective_timeout}s")

                if self._node_script:
                    # Windows: 通过 Node.js ESM wrapper 从文件读取 prompt
                    wrapper_code = (
                        "import { readFileSync } from 'node:fs';\n"
                        "import { pathToFileURL } from 'node:url';\n"
                        f"const prompt = readFileSync({json.dumps(prompt_file)}, 'utf8');\n"
                        f"process.argv = ['node', {json.dumps(self._node_script)}, "
                        f"'yuanbao', 'ask', prompt, "
                        f"'--timeout', '{effective_timeout}', "
                        f"'--search', '{str(self.search).lower()}', "
                        f"'--think', '{str(self.think).lower()}', "
                        f"'-f', 'plain'];\n"
                        f"await import(pathToFileURL({json.dumps(self._node_script)}).href);\n"
                    )
                    with tempfile.NamedTemporaryFile(
                        mode="w", suffix=".mjs", delete=False, encoding="utf-8"
                    ) as f:
                        f.write(wrapper_code)
                        wrapper_file = f.name

                    process = await asyncio.create_subprocess_exec(
                        self._get_node_executable(), wrapper_file,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                else:
                    # Unix: 直接传参数
                    cmd_args = [
                        self.opencli_path, "yuanbao", "ask",
                        prompt,
                        "--timeout", str(effective_timeout),
                        "--search", str(self.search).lower(),
                        "--think", str(self.think).lower(),
                        "-f", "plain",
                    ]
                    process = await asyncio.create_subprocess_exec(
                        *cmd_args,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )

                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=effective_timeout + 60,
                )

                if process.returncode != 0:
                    error_msg = stderr.decode("utf-8", errors="replace")
                    if "auth" in error_msg.lower() or "login" in error_msg.lower():
                        self._conversation_active = False
                        raise RuntimeError(f"元宝登录已过期，请在浏览器中重新登录: {error_msg}")
                    raise RuntimeError(f"opencli yuanbao ask 失败 (code={process.returncode}): {error_msg}")

                # 从 stdout 解析 Assistant 回复
                response = self._parse_response(stdout.decode("utf-8", errors="replace"))

                if not response:
                    raise RuntimeError("元宝返回了空响应")

                logger.info(f"元宝：收到响应，长度={len(response)}字")
                self._save_log(step or "ask", prompt, response)
                return response

            except asyncio.TimeoutError:
                logger.error(f"元宝：调用超时 ({effective_timeout + 60}s)")
                last_error = TimeoutError(f"元宝响应超时，已等待 {effective_timeout + 60} 秒")

            except RuntimeError as e:
                last_error = e
                error_str = str(e)
                # 登录过期不重试
                if "登录已过期" in error_str:
                    raise
                logger.warning(f"元宝：调用失败: {error_str}")

            finally:
                for f in [prompt_file, wrapper_file]:
                    if f and os.path.exists(f):
                        try:
                            os.unlink(f)
                        except OSError:
                            pass

        # 所有重试用完
        raise last_error

    def reset(self):
        """重置对话状态，下次 ask 前会自动 new"""
        self._conversation_active = False
