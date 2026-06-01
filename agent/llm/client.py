"""
LLM 客户端模块
支持 Claude API 和 OpenAI 兼容接口
"""

import json
import logging
import asyncio
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
    temperature: float = 0.3
    max_tokens: int = 800
    timeout: float = 15.0  # 请求超时（秒）- 故事/摘要生成不应卡主链路


class LLMClient:
    """
    LLM 客户端
    支持 Claude API 和 OpenAI 兼容接口
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._client = None
        self._last_status = "unknown"  # "live" | "mock" | "unknown"
        self._last_error = ""
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
                kwargs = {
                    "api_key": self.config.api_key,
                    "timeout": self.config.timeout,
                }
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
        max_tokens_override: Optional[int] = None,
        timeout_override: Optional[float] = None,
    ) -> str:
        """
        发送聊天请求

        Args:
            messages: 消息列表，格式: [{"role": "user", "content": "..."}]
            system_prompt: 系统提示词
            response_format: 响应格式，如 "json"
            max_tokens_override: 覆盖默认 max_tokens（用于短回复场景）
            timeout_override: 覆盖默认超时（秒）

        Returns:
            LLM 响应文本
        """
        if not self._client:
            logger.warning("LLM 客户端未初始化，返回 Mock 响应")
            self._last_status = "mock"
            self._last_error = "客户端未初始化"
            return self._mock_response(messages, system_prompt)

        timeout = timeout_override or self.config.timeout

        try:
            if self.config.provider == "claude":
                result = await asyncio.wait_for(
                    self._call_claude(messages, system_prompt, max_tokens_override),
                    timeout=timeout
                )
            elif self.config.provider in ("openai", "deepseek"):
                result = await asyncio.wait_for(
                    self._call_openai(messages, system_prompt, response_format, max_tokens_override),
                    timeout=timeout
                )
            else:
                raise ValueError(f"不支持的 provider: {self.config.provider}")
            self._last_status = "live"
            self._last_error = ""
            return result
        except (ConnectionError, TimeoutError, asyncio.TimeoutError, OSError) as e:
            logger.warning(f"LLM 网络/超时错误，降级到 Mock: {e}")
            self._last_status = "mock"
            self._last_error = str(e)
            return self._mock_response(messages, system_prompt)
        except TypeError as e:
            logger.warning(f"LLM 配置错误，降级到 Mock: {e}")
            self._last_status = "mock"
            self._last_error = str(e)
            return self._mock_response(messages, system_prompt)
        except Exception as e:
            logger.warning(f"LLM API 错误，降级到 Mock: {e}")
            self._last_status = "mock"
            self._last_error = str(e)
            return self._mock_response(messages, system_prompt)

    async def _call_claude(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        max_tokens_override: Optional[int] = None,
    ) -> str:
        """调用 Claude API（异步）"""
        response = await self._client.messages.create(
            model=self.config.model,
            max_tokens=max_tokens_override or self.config.max_tokens,
            temperature=self.config.temperature,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text

    @staticmethod
    def _sanitize(text: str) -> str:
        """移除 MiMo API 返回的无效 Unicode 代理对字符"""
        if not text:
            return text
        return text.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")

    async def _call_openai(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        response_format: Optional[str],
        max_tokens_override: Optional[int] = None,
    ) -> str:
        """调用 OpenAI 兼容 API（异步）"""
        # MiMo 推理模型：system prompt 导致 content 为空，合并到 user message
        all_messages = list(messages)
        if system_prompt and system_prompt.strip():
            if all_messages:
                last = dict(all_messages[-1])
                last["content"] = f"{system_prompt}\n\n{last['content']}"
                all_messages[-1] = last
            else:
                all_messages = [{"role": "user", "content": system_prompt}]

        kwargs = {
            "model": self.config.model,
            "messages": all_messages,
            "temperature": self.config.temperature,
            "max_tokens": max_tokens_override or self.config.max_tokens,
        }

        is_mimo = "mimo" in self.config.model.lower()

        # MiMo 推理模型不支持 response_format，改用 prompt 约束
        if response_format == "json" and self.config.provider == "openai":
            if not is_mimo:
                kwargs["response_format"] = {"type": "json_object"}
            else:
                last = dict(all_messages[-1])
                last["content"] += "\n\n请直接输出 JSON，不要包含其他文字或 markdown 标记。"
                all_messages[-1] = last
                kwargs["messages"] = all_messages

        # 重试逻辑：最多 3 次
        last_error = None
        for attempt in range(3):
            try:
                response = await self._client.chat.completions.create(**kwargs)
                msg = response.choices[0].message

                # 优先读 content
                content = self._sanitize(msg.content or "")

                # MiMo 推理模型：content 可能在 reasoning_content 字段
                if not content and hasattr(msg, 'reasoning_content'):
                    content = self._sanitize(msg.reasoning_content or "")

                # 检查 tool_calls（某些模型用这个返回结果）
                if not content and hasattr(msg, 'tool_calls') and msg.tool_calls:
                    try:
                        content = msg.tool_calls[0].function.arguments
                    except Exception:
                        pass

                if content:
                    return content

                # 空内容：打印完整响应帮助调试
                logger.warning(f"MiMo 返回空 (尝试 {attempt+1}/3)。msg attrs: {list(vars(msg).keys())}")
                last_error = ValueError("MiMo API 返回空内容")

            except (ConnectionError, TimeoutError, OSError) as e:
                logger.warning(f"网络错误 (尝试 {attempt+1}/3): {e}")
                last_error = e
            except Exception as e:
                logger.warning(f"API 调用失败 (尝试 {attempt+1}/3): {e}")
                last_error = e

            if attempt < 2:
                await asyncio.sleep(1)

        raise last_error or ValueError("MiMo API 返回空内容")

    def _mock_response(self, messages: List[Dict[str, str]], system_prompt: str = "") -> str:
        """Mock 响应（当 LLM 不可用时）"""
        user_msg = messages[-1]["content"] if messages else ""

        # 方案摘要请求：返回自然语言，不返回 JSON
        if "行程方案摘要" in user_msg or "行程规划师" in system_prompt:
            user_need = ""
            for line in user_msg.split("\n"):
                if line.startswith("用户需求："):
                    user_need = line[len("用户需求："):]
                    break
            check_text = user_need or user_msg
            if "团建" in check_text or "公司" in check_text:
                return "团建方案已出炉！先去餐厅聚餐，然后去轰趴馆尽情放松，KTV、桌游、台球一应俱全，保证同事们玩得开心！"
            elif "孩子" in check_text and "老婆" in check_text:
                return "已为你们一家三口规划好下午行程！先去亲子乐园让宝贝尽情撒欢，然后找一家有轻食的餐厅吃饭，老婆减肥也能吃得好。还安排了一个小惊喜～"
            elif "孩子" in check_text:
                return "亲子时光安排好了！先去儿童乐园或博物馆，寓教于乐，玩完找个适合小朋友的餐厅吃饭，全程不用操心。"
            elif "朋友" in check_text and ("聚会" in check_text or "多人" in check_text):
                return "聚会方案搞定！先去轰趴馆玩个痛快，KTV、桌游、台球随便选，晚饭安排在附近的人气餐厅，步行就到。"
            elif "朋友" in check_text:
                return "和朋友们的下午局安排好了！先去玩点有意思的，然后找个氛围好的餐厅吃饭，全程有剧情引导，保证你们玩得过瘾！"
            elif "约会" in check_text or "浪漫" in check_text:
                return "浪漫下午安排好了！先去一个有格调的地方度过二人时光，晚餐选了氛围超好的餐厅，还准备了一个小惊喜～"
            elif "一个人" in check_text or "安静" in check_text:
                return "独处时光安排好了！先找一家安静的咖啡馆坐坐，下午再去书店逛逛，晚餐选了一家评分很高的简餐，一个人也要好好吃饭。"
            else:
                return "已为你规划好下午行程！根据你的需求，安排了合理的路线和时间，每个地点都精心挑选，希望你玩得开心！"

        # 剧本杀故事生成请求
        if "故事" in user_msg and ("剧本" in user_msg or "剧情" in user_msg):
            return json.dumps({
                "title": "《城市探秘之旅》",
                "theme": "城市探索",
                "description": "在这座城市的角落里，隐藏着不为人知的故事……",
                "checkpoints": []
            }, ensure_ascii=False)

        # 分享文案请求
        if "行程" in user_msg and ("微信" in user_msg or "分享" in system_prompt):
            return "行程已安排好！下午先去吃饭，然后逛逛，晚上有惊喜安排～到时候发定位给你，不见不散！"

        # 根据用户输入返回 Mock 意图解析结果
        if "团建" in user_msg or "公司" in user_msg:
            return json.dumps({
                "people": [{"role": "colleague"} for _ in range(5)] + [{"role": "self"}],
                "needs": ["meeting", "dining", "entertainment"],
                "constraints": [
                    {"type": "budget", "max": 4000, "per_person": 200},
                    {"type": "group_size", "count": 20}
                ],
                "surprise": False,
                "time_preference": None,
                "mood": "团队凝聚"
            }, ensure_ascii=False)
        elif "孩子" in user_msg and "老婆" in user_msg:
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
        elif "朋友" in user_msg and ("聚会" in user_msg or "多人" in user_msg or "6" in user_msg or "8" in user_msg or "10" in user_msg):
            return json.dumps({
                "people": [{"role": "friend"} for _ in range(6)] + [{"role": "self"}],
                "needs": ["entertainment", "dining"],
                "constraints": [
                    {"type": "group_size", "count": 7}
                ],
                "surprise": False,
                "time_preference": "晚上",
                "mood": "热闹"
            }, ensure_ascii=False)
        elif "朋友" in user_msg:
            return json.dumps({
                "people": [
                    {"role": "friend", "gender": "male"},
                    {"role": "friend", "gender": "female"},
                    {"role": "friend", "gender": "male"},
                    {"role": "friend", "gender": "female"},
                    {"role": "self"}
                ],
                "needs": ["entertainment", "dining"],
                "constraints": [],
                "surprise": False,
                "time_preference": "下午",
                "mood": "轻松有趣"
            }, ensure_ascii=False)
        elif "约会" in user_msg or ("老婆" in user_msg and "浪漫" in user_msg):
            return json.dumps({
                "people": [
                    {"role": "wife"},
                    {"role": "self"}
                ],
                "needs": ["entertainment", "dining"],
                "constraints": [
                    {"type": "budget", "max": 500}
                ],
                "surprise": True,
                "time_preference": "下午",
                "mood": "浪漫"
            }, ensure_ascii=False)
        elif "老婆" in user_msg:
            return json.dumps({
                "people": [
                    {"role": "wife"},
                    {"role": "self"}
                ],
                "needs": ["dining", "entertainment"],
                "constraints": [
                    {"type": "diet", "requirement": "low_calorie"}
                ],
                "surprise": "惊喜" in user_msg or "花" in user_msg,
                "time_preference": "下午",
                "mood": "浪漫"
            }, ensure_ascii=False)
        elif "一个人" in user_msg or "独处" in user_msg or "安静" in user_msg:
            return json.dumps({
                "people": [{"role": "self"}],
                "needs": ["dining", "entertainment"],
                "constraints": [],
                "surprise": False,
                "time_preference": "下午",
                "mood": "安静放松"
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "people": [{"role": "self"}],
                "needs": ["dining", "entertainment"],
                "constraints": [],
                "surprise": False,
                "time_preference": "下午",
                "mood": "休闲"
            }, ensure_ascii=False)

    @staticmethod
    def extract_json(text: str, expect_array: bool = False) -> Any:
        """从 LLM 响应中提取 JSON（兼容推理模型的思考过程）
        5 级提取：markdown fence → 直接 parse → 括号匹配 → regex → first-to-last
        """
        import re
        text = text.strip()

        # Stage 1: Markdown code fence
        for fence in ["```json", "```"]:
            if fence in text:
                try:
                    return json.loads(text.split(fence)[1].split("```")[0].strip())
                except (json.JSONDecodeError, IndexError):
                    pass

        # Stage 2: 直接 parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Stage 3: 括号匹配（从最后一个闭括号向前找配对开括号）
        open_char, close_char = ('[', ']') if expect_array else ('{', '}')
        last_close = text.rfind(close_char)
        if last_close != -1:
            depth = 0
            for i in range(last_close, -1, -1):
                if text[i] == close_char:
                    depth += 1
                elif text[i] == open_char:
                    depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[i:last_close+1])
                    except json.JSONDecodeError:
                        pass
                    break

        # Stage 4: regex 简单对象/数组
        pattern = r'\[[^\[\]]*\]' if expect_array else r'\{[^{}]*\}'
        for m in re.finditer(pattern, text, re.DOTALL):
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                continue

        # Stage 5: first open to last close
        first = text.find(open_char)
        last = text.rfind(close_char)
        if first != -1 and last > first:
            try:
                return json.loads(text[first:last+1])
            except json.JSONDecodeError:
                pass

        return None

    async def chat_json(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        """发送聊天请求并返回 JSON 格式响应"""
        response = await self.chat(messages, system_prompt, response_format="json")
        result = self.extract_json(response)
        if result is not None:
            return result
        logger.error(f"JSON 解析失败，原始响应前200字: {response[:200]}")
        return {"error": "解析失败", "raw_response": response[:500]}

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        max_tokens_override: Optional[int] = None,
    ):
        """流式输出，yield 每个文本 chunk"""
        if not self._client:
            yield self._mock_response(messages, system_prompt)
            return

        # MiMo 推理模型：system prompt 合并到 user message
        all_messages = list(messages)
        if system_prompt and system_prompt.strip():
            if all_messages:
                last = dict(all_messages[-1])
                last["content"] = f"{system_prompt}\n\n{last['content']}"
                all_messages[-1] = last
            else:
                all_messages = [{"role": "user", "content": system_prompt}]

        kwargs = {
            "model": self.config.model,
            "messages": all_messages,
            "temperature": self.config.temperature,
            "max_tokens": max_tokens_override or self.config.max_tokens,
            "stream": True,
        }

        try:
            is_mimo = "mimo" in self.config.model.lower()
            response = await self._client.chat.completions.create(**kwargs)
            async for chunk in response:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield self._sanitize(delta.content)
                    elif is_mimo:
                        # MiMo 推理模型：reasoning_content 是思考过程，跳过不输出
                        rc = getattr(delta, 'reasoning_content', None)
                        if rc:
                            pass  # 跳过推理内容
            self._last_status = "live"
            self._last_error = ""
        except Exception as e:
            logger.warning(f"流式输出失败: {e}")
            self._last_status = "mock"
            self._last_error = str(e)
            yield self._mock_response(messages, system_prompt)
