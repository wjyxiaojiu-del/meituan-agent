"""
LLM 调用模块
支持 Claude API 和 OpenAI 兼容接口
"""

from .client import LLMClient
from .prompts import IntentPrompts

__all__ = ["LLMClient", "IntentPrompts"]
