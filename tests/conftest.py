"""
测试配置：统一 mock 入口
所有单元测试默认走 mock，不调用真实 LLM
"""
import os
import pytest
import tempfile

# 强制测试环境使用 mock LLM
os.environ["LLM_MODE"] = "mock"
os.environ["LLM_PROVIDER"] = "mock"

# 隔离 session DB，避免污染开发数据
_test_db = tempfile.mktemp(suffix=".db")
os.environ["SESSION_DB_PATH"] = _test_db


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    """每个测试自动设置 mock 环境"""
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")


@pytest.fixture
def agent():
    """创建 mock 模式的 Agent 实例"""
    from agent.main import create_agent
    return create_agent()


@pytest.fixture
def session_manager():
    """创建隔离的会话管理器"""
    from agent.core.session import SessionManager
    return SessionManager()
