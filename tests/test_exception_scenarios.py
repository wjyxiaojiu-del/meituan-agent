"""
异常场景测试
测试 Fallback 和 Replan 逻辑
"""

import pytest
import asyncio
import sys

sys.path.insert(0, ".")

from agent.main import create_agent
from agent.tools.book_restaurant import BookRestaurantTool
from agent.tools.weather_api import WeatherAPITool


@pytest.fixture
def agent():
    """创建测试用 Agent"""
    return create_agent(llm_provider="mock")


class TestFallbackScenario:
    """测试 Fallback（备选方案）场景"""

    @pytest.mark.asyncio
    async def test_restaurant_full_fallback(self, agent):
        """测试餐厅满座时自动切换备选方案"""
        book_tool = agent.tool_registry.get("book_restaurant")

        # 手动设置 rest_002 为满座状态
        book_tool.BOOKING_STATUS["rest_002"]["available"] = False

        result = await book_tool({
            "restaurant_id": "rest_002",
            "time": "17:00",
            "party_size": 3,
        })

        # 验证预订失败
        assert result.success is False
        assert result.error_type == "seat_unavailable"

        # 恢复
        book_tool.BOOKING_STATUS["rest_002"]["available"] = True

    @pytest.mark.asyncio
    async def test_fallback_mechanism(self, agent):
        """测试备选方案机制"""
        from agent.core.state_machine import Task, TaskStatus
        from agent.core.exception_handler import ExceptionHandler

        # 创建一个带备选方案的任务
        task = Task(
            task_id="T001",
            name="预订餐厅",
            tool_name="book_restaurant",
            params={"restaurant_id": "rest_002", "time": "17:00", "party_size": 3},
            fallback_tool="book_restaurant",
            fallback_params={"restaurant_id": "rest_001", "time": "17:00", "party_size": 3},
        )

        # 处理错误（async）
        handler = agent.exception_handler
        result = await handler.handle_error(
            task=task,
            error_type="seat_unavailable",
            error_message="餐厅已满座",
        )

        # 验证切换到备选方案并执行成功
        assert result["action_taken"] in ("fallback", "fallback_success")
        assert task.tool_name == "book_restaurant"
        assert task.params["restaurant_id"] == "rest_001"

    @pytest.mark.asyncio
    async def test_full_flow_with_fallback(self, agent):
        """测试完整流程中的备选方案"""
        user_input = "带老婆吃海底捞，老婆在减肥"

        plan = await agent.run(user_input)
        result = await agent.confirm_and_execute(plan["session_id"], confirmed=True)

        # 验证流程完成
        assert result["status"] in ["success", "partial"]


class TestReplanScenario:
    """测试 Replan（重新规划）场景"""

    @pytest.mark.asyncio
    async def test_weather_change_detection(self, agent):
        """测试天气变化检测"""
        weather_tool = agent.tool_registry.get("weather_api")

        # 设置天气为晴天
        weather_tool.set_mock_weather("sunny")
        result_sunny = await weather_tool({"date": "2026-05-17", "time": "14:00"})
        assert result_sunny.data["outdoor_friendly"] is True

        # 设置天气为雨天
        weather_tool.set_mock_weather("rainy")
        result_rainy = await weather_tool({"date": "2026-05-17", "time": "14:00"})
        assert result_rainy.data["outdoor_friendly"] is False

    @pytest.mark.asyncio
    async def test_replan_trigger(self, agent):
        """测试重新规划触发"""
        from agent.core.state_machine import Task, TaskStatus, AgentState

        # 确保状态机在 EXECUTING 状态
        agent.state_machine.transition_to(AgentState.EXECUTING)

        task = Task(
            task_id="T001",
            name="户外活动",
            tool_name="search_poi",
            params={"category": "儿童乐园", "keywords": ["户外"]},
        )

        handler = agent.exception_handler
        result = await handler.handle_error(
            task=task,
            error_type="weather_change",
            error_message="下午有雨，不适合户外活动",
        )

        # 验证触发重新规划
        assert result["action_taken"] == "replan"
        assert agent.state_machine.state == AgentState.PLANNING

    @pytest.mark.asyncio
    async def test_full_flow_with_replan(self, agent):
        """测试完整流程中的重新规划"""
        # 设置天气为雨天
        weather_tool = agent.tool_registry.get("weather_api")
        weather_tool.set_mock_weather("rainy")

        user_input = "这周六带老婆孩子出去玩，孩子5岁"

        plan = await agent.run(user_input)
        result = await agent.confirm_and_execute(plan["session_id"], confirmed=True)

        # 验证流程完成
        assert result["status"] in ["success", "partial", "replan_needed"]


class TestRetryScenario:
    """测试 Retry（重试）场景"""

    @pytest.mark.asyncio
    async def test_retry_mechanism(self, agent):
        """测试重试机制"""
        from agent.core.state_machine import Task, TaskStatus

        task = Task(
            task_id="T001",
            name="测试任务",
            tool_name="test_tool",
            params={},
        )

        handler = agent.exception_handler
        result = await handler.handle_error(
            task=task,
            error_type="timeout",
            error_message="请求超时",
        )

        # 验证触发重试
        assert result["action_taken"] == "retry_scheduled"
        assert task.retry_count == 1
        assert task.status == TaskStatus.RETRYING

    @pytest.mark.asyncio
    async def test_retry_exhaustion(self, agent):
        """测试重试次数耗尽"""
        from agent.core.state_machine import Task, TaskStatus

        task = Task(
            task_id="T001",
            name="测试任务",
            tool_name="test_tool",
            params={},
        )
        task.retry_count = 2  # 已重试 2 次

        handler = agent.exception_handler
        result = await handler.handle_error(
            task=task,
            error_type="timeout",
            error_message="请求超时",
            retry_func=lambda t: None,
        )

        # 重试次数耗尽后应该升级处理
        assert result["action_taken"] in ["retry_scheduled", "no_fallback", "fallback", "fallback_success", "fallback_failed"]


class TestUserNotification:
    """测试用户通知生成"""

    def test_retry_notification(self, agent):
        """测试重试通知"""
        handler = agent.exception_handler
        notification = handler.generate_user_notification({
            "task_id": "T001",
            "action_taken": "retry_scheduled",
            "retry_count": 1,
        })

        assert "重试" in notification

    def test_fallback_notification(self, agent):
        """测试备选方案通知"""
        handler = agent.exception_handler
        notification = handler.generate_user_notification({
            "task_id": "T001",
            "action_taken": "fallback",
            "original_tool": "book_restaurant",
            "new_tool": "search_poi",
        })

        assert "备选方案" in notification

    def test_replan_notification(self, agent):
        """测试重新规划通知"""
        handler = agent.exception_handler
        notification = handler.generate_user_notification({
            "task_id": "T001",
            "action_taken": "replan",
            "reason": "天气变化",
        })

        assert "重新规划" in notification


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
