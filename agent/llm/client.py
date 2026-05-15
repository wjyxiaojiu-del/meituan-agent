"""
LLM 客户端模块
支持 Claude API 和 OpenAI 兼容接口
"""

import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str = "claude"  # claude / openai / deepseek
    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    base_url: str = ""  # 自定义 API 端点
    temperature: float = 0.0
    max_tokens: int = 2000


class LLMClient:
    """
    LLM 客户端
    支持 Claude API 和 OpenAI 兼容接口
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._client = None
        self._init_client()

    def _init_client(self):
        """初始化 LLM 客户端（使用异步版本）"""
        # 没有 API Key 直接进入 Mock 模式
        if not self.config.api_key:
            logger.info("未配置 API Key，使用 Mock 模式")
            self._client = None
            return

        try:
            if self.config.provider == "claude":
                import anthropic
                kwargs = {"api_key": self.config.api_key}
                if self.config.base_url:
                    kwargs["base_url"] = self.config.base_url
                self._client = anthropic.AsyncAnthropic(**kwargs)
                logger.info("Claude API 异步客户端初始化成功")
            elif self.config.provider in ("openai", "deepseek"):
                import openai
                kwargs = {"api_key": self.config.api_key}
                if self.config.base_url:
                    kwargs["base_url"] = self.config.base_url
                # DeepSeek 兼容 OpenAI 接口，使用异步客户端
                self._client = openai.AsyncOpenAI(**kwargs)
                logger.info(f"{self.config.provider.upper()} API 异步客户端初始化成功")
            else:
                raise ValueError(f"不支持的 LLM 提供商: {self.config.provider}")
        except ImportError as e:
            logger.warning(f"LLM SDK 未安装: {e}，将使用 Mock 模式")
            self._client = None
        except Exception as e:
            logger.warning(f"LLM 客户端初始化失败: {e}，将使用 Mock 模式")
            self._client = None

    def is_available(self) -> bool:
        """LLM 客户端是否可用（非 Mock 模式）"""
        return self._client is not None

    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        response_format: Optional[str] = None,
    ) -> str:
        """
        发送聊天请求

        Args:
            messages: 消息列表，格式: [{"role": "user", "content": "..."}]
            system_prompt: 系统提示词
            response_format: 响应格式，如 "json"

        Returns:
            LLM 响应文本
        """
        if not self._client:
            logger.warning("LLM 客户端未初始化，返回 Mock 响应")
            return self._mock_response(messages)

        try:
            if self.config.provider == "claude":
                return await self._call_claude(messages, system_prompt)
            elif self.config.provider in ("openai", "deepseek"):
                return await self._call_openai(messages, system_prompt, response_format)
        except (ConnectionError, TimeoutError, OSError) as e:
            # 网络错误：降级到 Mock
            logger.error(f"LLM 网络错误，降级到 Mock: {e}")
            return self._mock_response(messages)
        except TypeError as e:
            # SDK 认证/配置错误：降级到 Mock
            logger.error(f"LLM 配置错误，降级到 Mock: {e}")
            return self._mock_response(messages)
        except Exception as e:
            # API 错误（认证失败、限流等）：向上抛出
            logger.error(f"LLM API 错误: {e}")
            raise

    async def _call_claude(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
    ) -> str:
        """调用 Claude API（异步）"""
        response = await self._client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text

    async def _call_openai(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        response_format: Optional[str],
    ) -> str:
        """调用 OpenAI 兼容 API（异步）"""
        kwargs = {
            "model": self.config.model,
            "messages": [{"role": "system", "content": system_prompt}] + messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        if response_format == "json" and self.config.provider == "openai":
            kwargs["response_format"] = {"type": "json_object"}

        response = await self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def _mock_response(self, messages: List[Dict[str, str]]) -> str:
        """Mock 响应（当 LLM 不可用时）"""
        user_msg = messages[-1]["content"] if messages else ""

        # 根据用户输入返回 Mock 意图解析结果
        if "孩子" in user_msg and "老婆" in user_msg:
            return json.dumps({
                "people": [
                    {"role": "child", "age": 5},
                    {"role": "wife"},
                    {"role": "self"}
                ],
                "needs": ["entertainment", "dining"],
                "constraints": [
                    {"type": "diet", "requirement": "low_calorie"},
                    {"type": "age_appropriate", "age": 5}
                ],
                "surprise": "惊喜" in user_msg or "花" in user_msg,
                "time_preference": "周末",
                "mood": "轻松愉快"
            }, ensure_ascii=False)
        elif "孩子" in user_msg:
            return json.dumps({
                "people": [
                    {"role": "child", "age": 5},
                    {"role": "self"}
                ],
                "needs": ["entertainment", "dining"],
                "constraints": [
                    {"type": "age_appropriate", "age": 5}
                ],
                "surprise": False,
                "time_preference": "周末",
                "mood": "亲子时光"
            }, ensure_ascii=False)
        elif "朋友" in user_msg and ("密室" in user_msg or "逃脱" in user_msg):
            return json.dumps({
                "people": [
                    {"role": "friend"},
                    {"role": "friend"},
                    {"role": "self"}
                ],
                "needs": ["entertainment"],
                "constraints": [],
                "surprise": False,
                "time_preference": None,
                "mood": "刺激"
            }, ensure_ascii=False)
        elif "朋友" in user_msg:
            return json.dumps({
                "people": [
                    {"role": "friend"},
                    {"role": "self"}
                ],
                "needs": ["entertainment", "dining"],
                "constraints": [],
                "surprise": "惊喜" in user_msg or "花" in user_msg,
                "time_preference": None,
                "mood": "热闹"
            }, ensure_ascii=False)
        elif "老婆" in user_msg:
            return json.dumps({
                "people": [
                    {"role": "wife"},
                    {"role": "self"}
                ],
                "needs": ["dining"],
                "constraints": [
                    {"type": "diet", "requirement": "low_calorie"}
                ],
                "surprise": "惊喜" in user_msg or "花" in user_msg,
                "time_preference": None,
                "mood": "浪漫"
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "people": [{"role": "self"}],
                "needs": ["dining", "entertainment"],
                "constraints": [],
                "surprise": False,
                "time_preference": None,
                "mood": "休闲"
            }, ensure_ascii=False)

    async def chat_json(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        """
        发送聊天请求并返回 JSON 格式响应

        Returns:
            解析后的 JSON 对象
        """
        # DeepSeek 不支持 response_format，通过 system prompt 引导输出 JSON
        if self.config.provider == "deepseek":
            system_prompt = system_prompt + "\n请只输出纯 JSON，不要 markdown 代码块，不要其他文字。"
            response = await self.chat(messages, system_prompt)
        else:
            response = await self.chat(messages, system_prompt, response_format="json")

        try:
            # 尝试提取 JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}\n原始响应: {response}")
            # 返回默认结构
            return {"error": "解析失败", "raw_response": response}
