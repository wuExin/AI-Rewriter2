"""
智谱AI客户端
使用 zhipuai SDK 调用 GLM 模型
"""
import asyncio
import json
import os
import random
from datetime import datetime
from pathlib import Path
from loguru import logger


class ZhipuClient:
    """智谱AI客户端（兼容 YuanbaoClient 接口）"""

    def __init__(self, api_key="", model="glm-4-plus", timeout=600, log_dir="./logs", delay_min=1, delay_max=15):
        """
        初始化智谱客户端

        Args:
            api_key: 智谱API密钥
            model: 模型名称（glm-4-plus, glm-4-flash, glm-4-air等）
            timeout: 单次请求超时时间（秒）
            log_dir: 日志目录
            delay_min: 最小延迟（分钟），防止API限流
            delay_max: 最大延迟（分钟），防止API限流
        """
        self.api_key = api_key or os.getenv("ZHIPU_API_KEY", "")
        self.model = model
        self.timeout = timeout
        self.delay_min = delay_min
        self.delay_max = delay_max
        self._conversation_active = False
        self._step_counter = 0
        self._messages = []  # 对话历史

        # 对话日志目录
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 检查API密钥
        if not self.api_key:
            logger.warning("智谱：未设置API密钥，请设置 ZHIPU_API_KEY 环境变量或在配置中设置")

        try:
            from zhipuai import ZhipuAI
            self._client = ZhipuAI(api_key=self.api_key)
            logger.info(f"智谱：客户端初始化成功，模型={model}")
        except ImportError:
            logger.error("智谱：未安装 zhipuai SDK，请运行: pip install zhipuai")
            raise ImportError("请先安装 zhipuai: pip install zhipuai")
        except Exception as e:
            logger.error(f"智谱：初始化失败: {e}")
            raise

    async def new_conversation(self):
        """新建对话（清空历史）"""
        logger.info("智谱：新建对话...")
        self._messages = []
        self._conversation_active = True
        # 智API不需要显式新建对话，只是清空历史
        await asyncio.sleep(0.5)
        logger.info("智谱：新对话已建立")

    def _save_log(self, step: str, prompt: str, response: str):
        """保存发送和接收的消息到日志文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._step_counter += 1
        log_file = self.log_dir / f"zhipu_{timestamp}_{self._step_counter}_{step}.md"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"# 智谱对话日志 - {step}\n\n")
            f.write(f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**模型**: {self.model}\n\n")
            f.write(f"---\n\n")
            f.write(f"## 发送的消息（{len(prompt)}字）\n\n")
            f.write(f"{prompt}\n\n")
            f.write(f"---\n\n")
            f.write(f"## 智谱的回复（{len(response)}字）\n\n")
            f.write(f"{response}\n")
        logger.info(f"智谱：对话日志已保存: {log_file}")

    async def _random_delay(self, step_name: str = ""):
        """随机延迟，防止API限流"""
        if self.delay_max > 0:
            delay_seconds = random.uniform(self.delay_min * 60, self.delay_max * 60)
            delay_minutes = delay_seconds / 60
            if delay_minutes > 0.5:  # 只在延迟超过30秒时提示
                logger.info(f"[智谱延迟] 等待 {delay_minutes:.1f} 分钟后继续...")
            await asyncio.sleep(delay_seconds)

    async def ask(self, prompt: str, timeout: int = None, step: str = "", max_retries: int = 2) -> str:
        """
        在当前对话中发送消息并等待回复

        Args:
            prompt: 要发送的提示词
            timeout: 超时秒数（默认使用配置值）
            step: 步骤名称（用于日志）
            max_retries: 最大重试次数

        Returns:
            智谱的回复文本
        """
        effective_timeout = timeout or self.timeout

        if not self._conversation_active:
            await self.new_conversation()

        last_error = None
        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.warning(f"智谱：第 {attempt} 次重试（{step}）...")
                await asyncio.sleep(3)

            try:
                logger.info(f"智谱：发送消息，长度={len(prompt)}字，timeout={effective_timeout}s")

                # 添加用户消息到历史
                self._messages.append({"role": "user", "content": prompt})

                # 在线程池中执行同步API调用
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self._client.chat.completions.create(
                        model=self.model,
                        messages=self._messages,
                        temperature=0.7,
                        # 不设置max_tokens限制，让模型自动输出完整内容
                        # GLM-4-plus默认最大输出可达128k tokens
                        timeout=effective_timeout,
                    )
                )

                # 提取回复内容
                content = response.choices[0].message.content

                if not content:
                    raise RuntimeError("智谱返回了空响应")

                # 添加助手回复到历史
                self._messages.append({"role": "assistant", "content": content})

                logger.info(f"智谱：收到响应，长度={len(content)}字")
                self._save_log(step or "ask", prompt, content)

                return content

            except Exception as e:
                last_error = e
                error_str = str(e)

                # 检查是否是限流错误
                if "429" in error_str or "rate limit" in error_str.lower():
                    logger.warning(f"智谱：触发限流，等待后重试...")
                    await asyncio.sleep(60)
                    continue

                logger.warning(f"智谱：调用失败: {error_str}")

        # 所有重试用完
        raise last_error

    def reset(self):
        """重置对话状态，下次 ask 前会自动 new"""
        self._conversation_active = False
        self._messages = []
