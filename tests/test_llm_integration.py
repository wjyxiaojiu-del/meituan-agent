"""
LLM 集成测试
测试 LLM 客户端的功能
"""

import pytest
import asyncio
import sys
import os
import json

sys.path.insert(0, ".")

from agent.llm.client import LLMClient, LLMConfig


class TestLLMClientInit:
    """测试 LLM 客户端初始化"""

    def test_mock_mode(self):
        """测试 Mock 模式"""
        client = LLMClient()
        assert client.config.provider in ["claude", "openai", "deepseek", "mock"]

    def test_deepseek_config(self):
        """测试 DeepSeek 配置"""
        config = LLMConfig(
            provider="deepseek",
            api_key="test-key",
            model="deepseek-chat",
            base_url="https://api.deepseek.com"
        )
        client = LLMClient(config)
        assert client.config.provider == "deepseek"
        assert client.config.base_url == "https://api.deepseek.com"

    def test_openai_config(self):
        """测试 OpenAI 配置"""
        config = LLMConfig(
            provider="openai",
            api_key="test-key",
            model="gpt-4o"
        )
        client = LLMClient(config)
        assert client.config.provider == "openai"


class TestLLMIntentPrompts:
    """测试意图解析提示词"""

    def test_intent_prompt_structure(self):
        """测试意图提示词结构"""
        from agent.llm.prompts import IntentPrompts

        user_input = "带老婆孩子出去玩"
        messages = IntentPrompts.get_intent_prompt(user_input)

        assert isinstance(messages, list)
        assert len(messages) > 0
        assert messages[0]["role"] == "user"
        assert user_input in messages[0]["content"]

    def test_system_prompt(self):
        """测试系统提示词"""
        from agent.llm.prompts import IntentPrompts

        assert IntentPrompts.SYSTEM_PROMPT is not None
        assert len(IntentPrompts.SYSTEM_PROMPT) > 0
        assert "JSON" in IntentPrompts.SYSTEM_PROMPT or "json" in IntentPrompts.SYSTEM_PROMPT


class TestLLMRealAPI:
    """测试真实 LLM API（需要配置 API Key）"""

    @pytest.fixture
    def client(self):
        """创建真实 LLM 客户端"""
        config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
        if not os.path.exists(config_path):
            pytest.skip("未找到 config.json")

        with open(config_path) as f:
            config = json.load(f)

        api_key = config.get("llm_api_key", "")
        if not api_key:
            pytest.skip("未配置 LLM API Key")

        return LLMClient(LLMConfig(
            provider=config.get("llm_provider", "deepseek"),
            api_key=api_key,
            model=config.get("llm_model", "deepseek-chat"),
            base_url=config.get("llm_base_url", "https://api.deepseek.com")
        ))

    @pytest.mark.asyncio
    async def test_real_api_intent_parsing(self, client):
        """测试真实 API 意图解析"""
        from agent.llm.prompts import IntentPrompts

        messages = IntentPrompts.get_intent_prompt(
            "这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜"
        )

        try:
            response = await client.chat(
                messages=messages,
                system_prompt=IntentPrompts.SYSTEM_PROMPT,
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "401" in error_msg or "authentication" in error_msg or "incorrect api key" in error_msg:
                pytest.skip(f"API Key 无效或已过期: {e}")
            raise

        assert response is not None
        assert len(response) > 0

        # 尝试解析 JSON
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)
            assert "people" in data
            assert "needs" in data
        except json.JSONDecodeError:
            pytest.fail(f"无法解析 LLM 响应为 JSON: {response[:200]}")

    @pytest.mark.asyncio
    async def test_real_api_json_mode(self, client):
        """测试真实 API JSON 模式"""
        messages = [{"role": "user", "content": "和朋友聚餐，4个人"}]
        system_prompt = "返回 JSON 格式的意图解析结果"

        try:
            data = await client.chat_json(
                messages=messages,
                system_prompt=system_prompt
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "401" in error_msg or "authentication" in error_msg or "incorrect api key" in error_msg:
                pytest.skip(f"API Key 无效或已过期: {e}")
            raise

        assert isinstance(data, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
