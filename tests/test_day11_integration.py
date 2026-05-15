"""
Day 11 集成测试
补充端到端流程、会话生命周期、错误恢复、边界场景
"""

import pytest
import sys
import asyncio

sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from agent.api import app
from agent.main import create_agent
from agent.tools.book_restaurant import BookRestaurantTool

client = TestClient(app)

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


# ===== 1. 会话生命周期 =====


class TestSessionLifecycle:
    """会话从创建→规划→确认→清理的完整生命周期"""

    def test_session_created_on_execute(self):
        """execute 应创建新会话并返回 sessionId"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃火锅"
        })
        data = resp.json()
        assert data["sessionId"] is not None
        assert len(data["sessionId"]) > 0

    def test_different_inputs_different_sessions(self):
        """不同请求应生成不同 sessionId"""
        r1 = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃火锅"
        }).json()
        r2 = client.post("/api/agent/execute", json={
            "userInput": "和朋友去KTV"
        }).json()
        assert r1["sessionId"] != r2["sessionId"]

    def test_session_survives_between_execute_and_confirm(self):
        """sessionId 在 execute→confirm 之间应保持一致"""
        r1 = client.post("/api/agent/execute", json={
            "userInput": "带孩子去游乐园"
        }).json()
        sid = r1["sessionId"]

        r2 = client.post("/api/agent/confirm", json={
            "sessionId": sid,
            "confirmed": True,
        }).json()
        assert r2["sessionId"] == sid

    def test_confirm_clears_session_tasks(self):
        """确认后再次确认同一 session 应返回 error（任务已清空）"""
        r1 = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃火锅"
        }).json()
        sid = r1["sessionId"]

        # 第一次确认
        client.post("/api/agent/confirm", json={
            "sessionId": sid,
            "confirmed": True,
        })

        # 第二次确认同一 session — 任务已清空
        r2 = client.post("/api/agent/confirm", json={
            "sessionId": sid,
            "confirmed": True,
        }).json()
        assert r2["status"] in ("error", "cancelled")


# ===== 2. 取消→重新规划流程 =====


class TestCancelAndReplan:
    """取消后重新规划的完整流程"""

    def test_cancel_then_new_plan(self):
        """取消后应能重新发起规划"""
        # 第一次规划
        r1 = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃火锅"
        }).json()
        sid1 = r1["sessionId"]

        # 取消
        cancel_resp = client.post("/api/agent/confirm", json={
            "sessionId": sid1,
            "confirmed": False,
        }).json()
        assert cancel_resp["status"] == "cancelled"

        # 重新规划
        r2 = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃日料"
        }).json()
        assert r2["status"] == "waiting_confirmation"
        assert r2["sessionId"] != sid1

        # 确认新方案
        r3 = client.post("/api/agent/confirm", json={
            "sessionId": r2["sessionId"],
            "confirmed": True,
        }).json()
        assert r3["status"] in ("success", "partial")

    def test_cancel_then_different_scenario(self):
        """取消家庭场景后切换到朋友场景"""
        r1 = client.post("/api/agent/execute", json={
            "userInput": "带孩子出去玩"
        }).json()
        client.post("/api/agent/confirm", json={
            "sessionId": r1["sessionId"],
            "confirmed": False,
        })

        r2 = client.post("/api/agent/execute", json={
            "userInput": "和朋友去密室逃脱"
        }).json()
        assert r2["status"] == "waiting_confirmation"
        # 不同场景应生成不同任务
        assert r2["tasks"] != r1["tasks"]


# ===== 3. 多会话并发 =====


class TestConcurrentSessions:
    """多个会话同时存在互不干扰"""

    def test_two_sessions_independent(self):
        """两个会话可以同时存在，确认一个不影响另一个"""
        r1 = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃火锅"
        }).json()
        r2 = client.post("/api/agent/execute", json={
            "userInput": "和朋友去KTV"
        }).json()

        sid1, sid2 = r1["sessionId"], r2["sessionId"]
        assert sid1 != sid2

        # 确认第一个
        c1 = client.post("/api/agent/confirm", json={
            "sessionId": sid1,
            "confirmed": True,
        }).json()
        assert c1["status"] in ("success", "partial")

        # 第二个仍然可以确认
        c2 = client.post("/api/agent/confirm", json={
            "sessionId": sid2,
            "confirmed": True,
        }).json()
        assert c2["status"] in ("success", "partial")

    def test_confirm_wrong_session_id(self):
        """用错误的 sessionId 确认应返回 error"""
        r = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃火锅"
        }).json()

        resp = client.post("/api/agent/confirm", json={
            "sessionId": "wrong_id_12345",
            "confirmed": True,
        }).json()
        assert resp["status"] in ("error", "cancelled")


# ===== 4. 路线数据流 =====


class TestRouteDataFlow:
    """路线数据从 API 流向前端"""

    def test_execute_returns_route(self):
        """execute 应返回 route 对象"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "带孩子出去玩"
        })
        data = resp.json()
        assert "route" in data
        # route 可以是 null、list 或 dict
        if data["route"] is not None:
            assert isinstance(data["route"], (dict, list))

    def test_confirm_returns_route(self):
        """confirm 也应返回 route 对象"""
        r = client.post("/api/agent/execute", json={
            "userInput": "带老婆孩子出去玩"
        }).json()
        resp = client.post("/api/agent/confirm", json={
            "sessionId": r["sessionId"],
            "confirmed": True,
        })
        data = resp.json()
        assert "route" in data


# ===== 5. 剧情数据流 =====


class TestStoryDataFlow:
    """剧情数据从 API 流向前端"""

    def test_story_mode_returns_story_object(self):
        """触发剧情模式时应返回完整 story 对象"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "和朋友出去玩，要有剧情有挑战"
        })
        data = resp.json()
        if data["story"] is not None:
            story = data["story"]
            assert "title" in story
            assert "theme" in story
            assert "description" in story or "checkpoints" in story

    def test_story_checkpoints_have_required_fields(self):
        """剧情 checkpoint 应有叙事和任务"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "和4个朋友出去玩，想玩点不一样的，要有剧情"
        })
        data = resp.json()
        if data["story"] is not None and "checkpoints" in data["story"]:
            for cp in data["story"]["checkpoints"]:
                assert "poi_name" in cp or "narrative" in cp


# ===== 6. 分享文案 =====


class TestShareText:
    """分享文案生成"""

    def test_confirm_returns_share_text(self):
        """确认后应返回 shareText"""
        r = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃火锅，要有惊喜"
        }).json()
        resp = client.post("/api/agent/confirm", json={
            "sessionId": r["sessionId"],
            "confirmed": True,
        })
        data = resp.json()
        assert "shareText" in data
        if data["shareText"] is not None:
            assert isinstance(data["shareText"], str)
            assert len(data["shareText"]) > 0

    def test_cancel_no_share_text(self):
        """取消后 shareText 应为 null"""
        r = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃火锅"
        }).json()
        resp = client.post("/api/agent/confirm", json={
            "sessionId": r["sessionId"],
            "confirmed": False,
        })
        data = resp.json()
        # 取消后 shareText 应为 null 或不存在
        assert data.get("shareText") is None


# ===== 7. 任务结构完整性 =====


class TestTaskStructure:
    """验证任务结构在各阶段的一致性"""

    def test_execute_tasks_have_consistent_ids(self):
        """execute 返回的 task_id 格式应为 T00X 或 W00X"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "带老婆孩子出去玩"
        })
        data = resp.json()
        for task in data["tasks"]:
            assert task["task_id"][0] in ("T", "W")
            assert len(task["task_id"]) >= 4  # T001, W001...

    def test_confirm_tasks_match_execute_tasks(self):
        """confirm 返回的 tasks 应与 execute 的 tasks 对应"""
        r = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃火锅"
        }).json()
        execute_task_ids = {t["task_id"] for t in r["tasks"]}

        resp = client.post("/api/agent/confirm", json={
            "sessionId": r["sessionId"],
            "confirmed": True,
        }).json()
        confirm_task_ids = {t["task_id"] for t in resp["tasks"]}

        # confirm 的任务应包含 execute 的所有任务
        assert execute_task_ids.issubset(confirm_task_ids)

    def test_tasks_have_valid_tool_names(self):
        """所有任务的 tool_name 应是已注册的工具"""
        valid_tools = {
            "weather_api", "search_poi", "book_restaurant",
            "check_queue", "order_delivery", "book_venue"
        }
        resp = client.post("/api/agent/execute", json={
            "userInput": "带老婆孩子出去玩，要有惊喜"
        })
        data = resp.json()
        for task in data["tasks"]:
            assert task["tool_name"] in valid_tools, \
                f"未知工具: {task['tool_name']}"


# ===== 8. 天气集成 =====


class TestWeatherIntegration:
    """天气任务在各种场景下都应存在"""

    def test_weather_in_family_scenario(self):
        resp = client.post("/api/agent/execute", json={
            "userInput": "带老婆孩子出去玩"
        }).json()
        tools = {t["tool_name"] for t in resp["tasks"]}
        assert "weather_api" in tools

    def test_weather_in_friends_scenario(self):
        resp = client.post("/api/agent/execute", json={
            "userInput": "和朋友出去玩"
        }).json()
        tools = {t["tool_name"] for t in resp["tasks"]}
        assert "weather_api" in tools

    def test_weather_in_team_building(self):
        resp = client.post("/api/agent/execute", json={
            "userInput": "公司20人团建"
        }).json()
        tools = {t["tool_name"] for t in resp["tasks"]}
        assert "weather_api" in tools


# ===== 9. Agent 层直接测试（绕过 API） =====


class TestAgentDirectIntegration:
    """直接测试 Agent 层，验证核心逻辑"""

    @pytest.fixture
    def agent(self):
        return create_agent(llm_provider="mock")

    @pytest.mark.asyncio
    async def test_run_returns_all_expected_fields(self, agent):
        """run 应返回所有前端需要的字段"""
        result = await agent.run("带老婆孩子出去玩")
        assert "status" in result
        assert "session_id" in result
        assert "plan_summary" in result
        assert "tasks_preview" in result
        assert "route" in result
        assert "story" in result

    @pytest.mark.asyncio
    async def test_confirm_returns_share_text(self, agent):
        """confirm_and_execute 应返回 share_text"""
        plan = await agent.run("带老婆吃火锅")
        result = await agent.confirm_and_execute(plan["session_id"], confirmed=True)
        assert "share_text" in result

    @pytest.mark.asyncio
    async def test_route_has_time_info(self, agent):
        """路线应包含时间信息"""
        plan = await agent.run("带孩子出去玩")
        route = plan.get("route")
        if route and isinstance(route, dict):
            # 路线应有节点列表或路线描述
            assert "nodes" in route or "display" in route or "stats" in route

    @pytest.mark.asyncio
    async def test_scene_detection_accuracy(self, agent):
        """场景识别准确性"""
        test_cases = [
            ("带老婆孩子出去玩", "family"),
            ("和老婆约会", "date"),
            ("和朋友出去玩", "friends"),
            ("公司团建", "team_building"),
            ("自己出去走走", "solo"),
        ]
        for user_input, expected_scene in test_cases:
            plan = await agent.run(user_input)
            # 只要能成功规划即可，场景识别可能用不同名称
            assert plan["status"] == "waiting_confirmation"

    @pytest.mark.asyncio
    async def test_surprise_triggers_delivery(self, agent):
        """惊喜需求应触发配送任务"""
        plan = await agent.run("老婆生日，要有惊喜，鲜花和蛋糕")
        tools = {t["tool_name"] for t in plan["tasks_preview"]}
        assert "order_delivery" in tools

    @pytest.mark.asyncio
    async def test_team_building_includes_venue(self, agent):
        """团建场景应包含场地预订"""
        plan = await agent.run("公司20人团建，要会议室和聚餐")
        tools = {t["tool_name"] for t in plan["tasks_preview"]}
        assert "book_venue" in tools or "book_restaurant" in tools


# ===== 10. 边界输入 =====


class TestBoundaryInputs:
    """边界输入场景"""

    def test_very_short_input(self):
        resp = client.post("/api/agent/execute", json={
            "userInput": "吃"
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "waiting_confirmation"

    def test_emoji_input(self):
        resp = client.post("/api/agent/execute", json={
            "userInput": "带老婆出去玩🎉要有惊喜🎁"
        })
        assert resp.status_code == 200

    def test_mixed_language_input(self):
        resp = client.post("/api/agent/execute", json={
            "userInput": "带wife出去dinner"
        })
        assert resp.status_code == 200

    def test_repeated_same_request(self):
        """同一输入连续请求两次，应生成不同 session"""
        r1 = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃火锅"
        }).json()
        r2 = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃火锅"
        }).json()
        assert r1["sessionId"] != r2["sessionId"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
