"""
集成测试
测试完整的业务流程（规划→确认→执行）
"""

import pytest
import asyncio
import sys
import os

sys.path.insert(0, ".")

from agent.main import create_agent
from agent.tools.book_restaurant import BookRestaurantTool


DEFAULT_BOOKING_STATUS = {
    "rest_001": {"available": True, "capacity": 60, "booked": 35, "name": "新元素餐厅"},
    "rest_002": {"available": True, "capacity": 100, "booked": 80, "name": "海底捞火锅"},
    "rest_003": {"available": True, "capacity": 40, "booked": 20, "name": "wagas"},
    "rest_004": {"available": True, "capacity": 80, "booked": 50, "name": "西贝莜面村"},
    "rest_005": {"available": True, "capacity": 30, "booked": 15, "name": "一兰拉面"},
    "rest_006": {"available": True, "capacity": 80, "booked": 40, "name": "木屋烧烤"},
    "rest_007": {"available": True, "capacity": 30, "booked": 10, "name": "素宿素食"},
    "rest_008": {"available": True, "capacity": 120, "booked": 90, "name": "外婆家"},
}


@pytest.fixture(autouse=True)
def _reset_booking_status():
    """每个测试前重置预订状态，防止跨测试状态泄漏"""
    BookRestaurantTool.BOOKING_STATUS = {k: dict(v) for k, v in DEFAULT_BOOKING_STATUS.items()}
    yield


class TestCompleteFlow:
    """测试完整业务流程"""

    @pytest.fixture
    def agent(self):
        """创建测试用 Agent"""
        return create_agent(llm_provider="mock")

    async def _run_and_confirm(self, agent, user_input):
        """辅助方法：规划→确认→返回执行结果"""
        plan = await agent.run(user_input)
        assert plan["status"] == "waiting_confirmation"
        session_id = plan["session_id"]
        result = await agent.confirm_and_execute(session_id, confirmed=True)
        return result

    @pytest.mark.asyncio
    async def test_family_outing(self, agent):
        """测试家庭出游场景"""
        user_input = "这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜"
        result = await self._run_and_confirm(agent, user_input)

        # 验证执行成功或部分成功
        assert result["status"] in ["success", "partial"]

        # 验证有任务执行结果
        results = result.get("results", {})
        assert len(results) >= 3

        # 验证有分享文案
        assert "share_text" in result

    @pytest.mark.asyncio
    async def test_couple_date(self, agent):
        """测试情侣约会场景"""
        user_input = "想和老婆约会，要有惊喜，吃点好的"
        result = await self._run_and_confirm(agent, user_input)

        assert result["status"] in ["success", "partial"]
        results = result.get("results", {})
        assert len(results) >= 2

    @pytest.mark.asyncio
    async def test_friends_gathering(self, agent):
        """测试朋友聚会场景"""
        user_input = "周末和4个朋友一起出去玩，2男2女，想找好玩的地方"
        result = await self._run_and_confirm(agent, user_input)

        assert result["status"] in ["success", "partial"]
        results = result.get("results", {})
        assert len(results) >= 2

    @pytest.mark.asyncio
    async def test_birthday_surprise(self, agent):
        """测试生日惊喜场景"""
        user_input = "老婆生日，想给她一个惊喜，要有鲜花和蛋糕"
        result = await self._run_and_confirm(agent, user_input)

        assert result["status"] in ["success", "partial"]
        results = result.get("results", {})

        # 验证有惊喜配送
        delivery_found = False
        for task_id, task_result in results.items():
            if isinstance(task_result, dict) and "order_id" in task_result:
                delivery_found = True
                break

        assert delivery_found, "应该有惊喜配送任务"


class TestEdgeCases:
    """测试边界情况"""

    @pytest.fixture
    def agent(self):
        return create_agent(llm_provider="mock")

    @pytest.mark.asyncio
    async def test_minimal_input(self, agent):
        """测试最小输入"""
        result = await agent.run("吃饭")
        assert result["status"] == "waiting_confirmation"

    @pytest.mark.asyncio
    async def test_complex_input(self, agent):
        """测试复杂输入"""
        user_input = """明天下午带老婆和3岁的女儿出去玩，
        老婆最近在减肥要吃低卡的，
        孩子喜欢恐龙，
        我自己想喝咖啡，
        最好有惊喜安排，
        预算500以内"""
        result = await agent.run(user_input)
        assert result["status"] == "waiting_confirmation"
        assert "plan_summary" in result

    @pytest.mark.asyncio
    async def test_empty_input(self, agent):
        """测试空输入"""
        result = await agent.run("")
        assert "status" in result

    @pytest.mark.asyncio
    async def test_special_characters(self, agent):
        """测试特殊字符"""
        result = await agent.run("带老婆出去玩！！！要有惊喜~~~")
        assert "status" in result


class TestStateTransitions:
    """测试状态转换"""

    @pytest.fixture
    def agent(self):
        return create_agent(llm_provider="mock")

    @pytest.mark.asyncio
    async def test_state_during_execution(self, agent):
        """测试执行过程中的状态"""
        from agent.core.state_machine import AgentState

        # 初始状态
        assert agent.state_machine.state == AgentState.PLANNING

        # 规划
        plan = await agent.run("带老婆孩子出去玩")
        assert plan["status"] == "waiting_confirmation"

        # 确认执行
        await agent.confirm_and_execute(plan["session_id"], confirmed=True)

        # 执行完成后应该是完成状态
        assert agent.state_machine.state in [
            AgentState.COMPLETED,
            AgentState.EXECUTING,
            AgentState.PLANNING
        ]

    @pytest.mark.asyncio
    async def test_state_after_cancel(self, agent):
        """测试取消后的状态"""
        from agent.core.state_machine import AgentState

        plan = await agent.run("和女朋友约会")
        await agent.confirm_and_execute(plan["session_id"], confirmed=False)

        # 取消后状态机应该被重置（下次规划时）
        assert agent.state_machine.state in [
            AgentState.PLANNING,
            AgentState.CANCELLED,
        ]


class TestConcurrency:
    """测试并发执行"""

    @pytest.fixture
    def agent(self):
        return create_agent(llm_provider="mock")

    @pytest.mark.asyncio
    async def test_multiple_plan_requests(self, agent):
        """测试多个规划请求"""
        inputs = [
            "带老婆吃饭",
            "和朋友出去玩",
            "自己看电影"
        ]

        # 并发执行多个规划请求
        tasks = [agent.run(inp) for inp in inputs]
        results = await asyncio.gather(*tasks)

        # 所有请求都应该返回等待确认
        for result in results:
            assert result["status"] == "waiting_confirmation"


class TestDataPersistence:
    """测试数据持久性"""

    @pytest.fixture
    def agent(self):
        return create_agent(llm_provider="mock")

    @pytest.mark.asyncio
    async def test_session_persistence(self, agent):
        """测试会话在规划和确认之间的持久性"""
        plan = await agent.run("带老婆孩子出去玩")
        session_id = plan["session_id"]

        # 确认执行时应该能找到会话
        result = await agent.confirm_and_execute(session_id, confirmed=True)
        assert result["status"] in ["success", "partial"]
        assert result["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_invalid_session(self, agent):
        """测试无效会话 ID"""
        result = await agent.confirm_and_execute("nonexistent_session", confirmed=True)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_booking_id_format(self, agent):
        """测试预订号格式"""
        plan = await agent.run("带老婆孩子出去玩")
        result = await agent.confirm_and_execute(plan["session_id"], confirmed=True)

        # 找到预订任务
        for task_id, task_result in result.get("results", {}).items():
            if isinstance(task_result, dict) and "booking_id" in task_result:
                booking_id = task_result["booking_id"]
                assert booking_id.startswith("BK")
                assert len(booking_id) > 10
                break

    @pytest.mark.asyncio
    async def test_order_id_format(self, agent):
        """测试订单号格式"""
        plan = await agent.run("带老婆孩子出去玩，要有惊喜")
        result = await agent.confirm_and_execute(plan["session_id"], confirmed=True)

        # 找到订单任务
        for task_id, task_result in result.get("results", {}).items():
            if isinstance(task_result, dict) and "order_id" in task_result:
                order_id = task_result["order_id"]
                assert order_id.startswith("DL")
                assert len(order_id) > 10
                break


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
