"""
规划引擎测试
"""

import pytest
import asyncio
from agent.main import create_agent


@pytest.fixture
def agent():
    """创建测试用 Agent（Mock 模式）"""
    return create_agent(llm_provider="mock")


@pytest.mark.asyncio
async def test_intent_parsing(agent):
    """测试意图解析"""
    intent = await agent.parse_intent("这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜")

    assert len(intent["people"]) >= 2  # 至少有老婆和孩子
    assert any(p["role"] == "child" for p in intent["people"])
    assert any(p["role"] == "wife" for p in intent["people"])
    assert intent["surprise"] is True
    assert any(c["type"] == "diet" for c in intent["constraints"])


@pytest.mark.asyncio
async def test_plan_and_confirm_flow(agent):
    """测试规划→确认→执行完整流程"""
    # 第一步：规划
    plan = await agent.run("这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜")
    assert plan["status"] == "waiting_confirmation"
    assert "session_id" in plan
    assert "plan_summary" in plan

    # 第二步：确认执行
    session_id = plan["session_id"]
    result = await agent.confirm_and_execute(session_id, confirmed=True)
    assert result["status"] in ["success", "partial"]
    assert len(result.get("results", {})) >= 3


@pytest.mark.asyncio
async def test_plan_cancel_flow(agent):
    """测试规划→取消流程"""
    plan = await agent.run("和女朋友约会")
    assert plan["status"] == "waiting_confirmation"

    result = await agent.confirm_and_execute(plan["session_id"], confirmed=False)
    assert result["status"] == "cancelled"


@pytest.mark.asyncio
async def test_search_poi(agent):
    """测试 POI 搜索"""
    tool = agent.tool_registry.get("search_poi")
    result = await tool({"category": "儿童乐园", "keywords": ["适合5岁"]})

    assert result.success is True
    assert result.data["total"] > 0


@pytest.mark.asyncio
async def test_restaurant_booking(agent):
    """测试餐厅预订"""
    from agent.tools.book_restaurant import BookRestaurantTool
    # 重置预订状态，避免被其他测试污染
    BookRestaurantTool.BOOKING_STATUS["rest_001"] = {
        "available": True, "capacity": 60, "booked": 35, "name": "新元素餐厅"
    }
    tool = agent.tool_registry.get("book_restaurant")
    result = await tool({
        "restaurant_id": "rest_001",
        "time": "17:00",
        "party_size": 3,
    })

    assert result.success is True
    assert "booking_id" in result.data


@pytest.mark.asyncio
async def test_restaurant_booking_unknown_id(agent):
    """测试未知餐厅 ID 预订（应自动成功）"""
    tool = agent.tool_registry.get("book_restaurant")
    result = await tool({
        "restaurant_id": "unknown_001",
        "time": "17:00",
        "party_size": 3,
    })

    assert result.success is True
    assert "booking_id" in result.data


@pytest.mark.asyncio
async def test_queue_system(agent):
    """测试排队系统"""
    tool = agent.tool_registry.get("check_queue")

    # 查询排队状态
    check_result = await tool({"restaurant_id": "rest_001", "action": "check"})
    assert check_result.success is True
    assert "waiting_count" in check_result.data

    # 取号
    take_result = await tool({
        "restaurant_id": "rest_001",
        "action": "take_number",
        "party_size": 3,
    })
    assert take_result.success is True
    assert "my_number" in take_result.data


@pytest.mark.asyncio
async def test_delivery_order(agent):
    """测试即时配送"""
    tool = agent.tool_registry.get("order_delivery")
    result = await tool({
        "item_type": "鲜花",
        "item_name": "玫瑰花束",
        "deliver_to": "新元素餐厅",
        "deliver_time": "17:30",
        "message": "老婆辛苦了",
    })

    assert result.success is True
    assert "order_id" in result.data
    assert result.data["scheduled"] is True


@pytest.mark.asyncio
async def test_weather_api(agent):
    """测试天气 API"""
    tool = agent.tool_registry.get("weather_api")
    result = await tool({
        "date": "2026-05-17",
        "time": "14:00",
    })

    assert result.success is True
    assert "condition" in result.data


@pytest.mark.asyncio
async def test_state_machine(agent):
    """测试状态机"""
    from agent.core.state_machine import AgentState

    assert agent.state_machine.state == AgentState.PLANNING

    # 测试状态转换
    success = agent.state_machine.transition_to(AgentState.EXECUTING)
    assert success is True
    assert agent.state_machine.state == AgentState.EXECUTING

    # 测试非法状态转换
    success = agent.state_machine.transition_to(AgentState.PLANNING)
    assert success is False  # EXECUTING 不能直接回到 PLANNING


@pytest.mark.asyncio
async def test_state_machine_reset(agent):
    """测试状态机重置"""
    from agent.core.state_machine import AgentState

    agent.state_machine.transition_to(AgentState.EXECUTING)
    agent.state_machine.transition_to(AgentState.COMPLETED)
    assert agent.state_machine.state == AgentState.COMPLETED

    agent.state_machine.reset()
    assert agent.state_machine.state == AgentState.PLANNING


@pytest.mark.asyncio
async def test_exception_handler(agent):
    """测试异常处理器"""
    from agent.core.exception_handler import ErrorLevel, ErrorClassifier

    # 测试错误分类
    assert ErrorClassifier.classify("timeout") == ErrorLevel.RETRY
    assert ErrorClassifier.classify("seat_unavailable") == ErrorLevel.FALLBACK
    assert ErrorClassifier.classify("weather_change") == ErrorLevel.REPLAN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
