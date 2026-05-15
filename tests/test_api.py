"""
FastAPI 后端 API 测试
"""

import pytest
import sys

sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from agent.api import app
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


class TestHealthAPI:
    """健康检查接口"""

    def test_health(self):
        resp = client.get("/api/agent/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestExecuteAPI:
    """规划接口"""

    def test_execute_basic(self):
        resp = client.post("/api/agent/execute", json={
            "userInput": "带老婆孩子出去玩，孩子5岁"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "waiting_confirmation"
        assert data["sessionId"] is not None
        assert len(data["tasks"]) >= 2

    def test_execute_empty_input(self):
        resp = client.post("/api/agent/execute", json={"userInput": ""})
        assert resp.status_code == 400

    def test_execute_returns_story(self):
        resp = client.post("/api/agent/execute", json={
            "userInput": "和朋友出去玩，想玩点不一样的，要有剧情"
        })
        assert resp.status_code == 200
        data = resp.json()
        # Mock 模式下可能有 story 也可能没有，但字段应存在
        assert "story" in data

    def test_execute_returns_route(self):
        resp = client.post("/api/agent/execute", json={
            "userInput": "带孩子去儿童乐园"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "route" in data

    def test_execute_different_inputs(self):
        r1 = client.post("/api/agent/execute", json={
            "userInput": "带孩子去儿童乐园"
        }).json()
        r2 = client.post("/api/agent/execute", json={
            "userInput": "和朋友去密室逃脱"
        }).json()
        # 不同输入应生成不同任务
        assert r1["tasks"] != r2["tasks"]


class TestConfirmAPI:
    """确认接口"""

    def _create_plan(self):
        """创建一个待确认的方案"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃火锅"
        })
        return resp.json()["sessionId"]

    def test_confirm_execute(self):
        session_id = self._create_plan()
        resp = client.post("/api/agent/confirm", json={
            "sessionId": session_id,
            "confirmed": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("success", "partial")
        assert len(data["tasks"]) >= 1
        assert data["sessionId"] == session_id

    def test_confirm_cancel(self):
        session_id = self._create_plan()
        resp = client.post("/api/agent/confirm", json={
            "sessionId": session_id,
            "confirmed": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"

    def test_confirm_invalid_session(self):
        resp = client.post("/api/agent/confirm", json={
            "sessionId": "nonexistent_session",
            "confirmed": True,
        })
        # 应返回错误或 cancelled，不应 500
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("error", "cancelled")

    def test_confirm_has_results(self):
        session_id = self._create_plan()
        resp = client.post("/api/agent/confirm", json={
            "sessionId": session_id,
            "confirmed": True,
        })
        data = resp.json()
        assert "results" in data
        assert "tasks" in data
        # tasks 应包含 task_id 和 name
        for task in data["tasks"]:
            assert "task_id" in task
            assert "name" in task
            assert "status" in task


class TestFullFlow:
    """完整流程测试"""

    def test_plan_confirm_flow(self):
        # 1. 规划
        r1 = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃火锅，要有惊喜"
        }).json()
        assert r1["status"] == "waiting_confirmation"
        session_id = r1["sessionId"]

        # 2. 确认执行
        r2 = client.post("/api/agent/confirm", json={
            "sessionId": session_id,
            "confirmed": True,
        }).json()
        assert r2["status"] in ("success", "partial")
        assert r2["sessionId"] == session_id

    def test_plan_cancel_flow(self):
        # 1. 规划
        r1 = client.post("/api/agent/execute", json={
            "userInput": "带孩子出去玩"
        }).json()
        session_id = r1["sessionId"]

        # 2. 取消
        r2 = client.post("/api/agent/confirm", json={
            "sessionId": session_id,
            "confirmed": False,
        }).json()
        assert r2["status"] == "cancelled"


# ===== Day 10：集成测试 =====


class TestDataContract:
    """前端-后端数据契约校验"""

    def test_execute_response_fields(self):
        """execute 响应应包含前端需要的所有字段"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "带老婆孩子出去玩，孩子5岁"
        })
        data = resp.json()
        # 前端 chat.js 依赖的字段
        assert "status" in data
        assert "sessionId" in data
        assert "planSummary" in data
        assert "tasks" in data
        assert "route" in data
        assert "story" in data

    def test_execute_tasks_have_required_fields(self):
        """tasks 中每项应有 task_id, name, tool_name"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "带孩子去儿童乐园"
        })
        data = resp.json()
        for task in data["tasks"]:
            assert "task_id" in task, f"缺少 task_id"
            assert "name" in task, f"缺少 name"
            assert "tool_name" in task, f"缺少 tool_name"

    def test_confirm_response_fields(self):
        """confirm 响应应包含前端需要的所有字段"""
        # 先创建方案
        r = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃火锅"
        }).json()
        session_id = r["sessionId"]

        resp = client.post("/api/agent/confirm", json={
            "sessionId": session_id,
            "confirmed": True,
        })
        data = resp.json()
        # 前端 chat.js onConfirmPlan 依赖的字段
        assert "status" in data
        assert "sessionId" in data
        assert "results" in data
        assert "shareText" in data
        assert "tasks" in data

    def test_confirm_tasks_have_required_fields(self):
        """confirm 的 tasks 应有 task_id, name, status"""
        r = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃火锅"
        }).json()
        resp = client.post("/api/agent/confirm", json={
            "sessionId": r["sessionId"],
            "confirmed": True,
        })
        data = resp.json()
        for task in data["tasks"]:
            assert "task_id" in task
            assert "name" in task
            assert "status" in task
            assert task["status"] in ("SUCCESS", "PENDING")


class TestStoryIntegration:
    """剧情模式集成测试"""

    def test_story_mode_activates(self):
        """包含剧情关键词时应触发剧情模式"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "和朋友出去玩，想玩点不一样的，要有剧情"
        })
        data = resp.json()
        # story 应非空（触发了剧情模式）
        assert data["story"] is not None
        assert "title" in data["story"]
        assert "theme" in data["story"]

    def test_story_mode_not_activates(self):
        """普通需求不应触发剧情模式"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃火锅"
        })
        data = resp.json()
        # 无剧情关键词，story 应为 null
        assert data["story"] is None

    def test_story_with_route(self):
        """剧情模式应有路线信息"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "和4个朋友出去玩，要有剧情有挑战"
        })
        data = resp.json()
        if data["story"] is not None:
            assert "checkpoints" in data["story"]


class TestTeamBuildingIntegration:
    """团建场景集成测试"""

    def test_team_building_flow(self):
        """团建场景完整流程"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "公司20人团建，要会议室和聚餐"
        })
        data = resp.json()
        assert data["status"] == "waiting_confirmation"
        assert len(data["tasks"]) >= 2

        # 确认执行
        confirm_resp = client.post("/api/agent/confirm", json={
            "sessionId": data["sessionId"],
            "confirmed": True,
        })
        result = confirm_resp.json()
        assert result["status"] in ("success", "partial")


class TestWeatherIntegration:
    """天气异常集成测试"""

    def test_weather_task_included(self):
        """所有方案都应包含天气查询任务"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "带孩子出去玩"
        })
        data = resp.json()
        tool_names = [t["tool_name"] for t in data["tasks"]]
        assert "weather_api" in tool_names


class TestMultiScenario:
    """多场景覆盖测试"""

    def test_family_scenario(self):
        """家庭出游场景"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜"
        })
        data = resp.json()
        assert data["status"] == "waiting_confirmation"
        tool_names = {t["tool_name"] for t in data["tasks"]}
        assert "weather_api" in tool_names
        assert "search_poi" in tool_names

    def test_date_scenario(self):
        """约会场景"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "想和老婆约会，要有惊喜，吃点好的"
        })
        data = resp.json()
        assert data["status"] == "waiting_confirmation"

    def test_friends_scenario(self):
        """朋友聚会场景"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "周末和4个朋友一起出去玩，想找好玩的地方"
        })
        data = resp.json()
        assert data["status"] == "waiting_confirmation"

    def test_surprise_includes_delivery(self):
        """惊喜需求应包含配送任务"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "老婆生日，想给她一个惊喜，要有鲜花和蛋糕"
        })
        data = resp.json()
        tool_names = {t["tool_name"] for t in data["tasks"]}
        assert "order_delivery" in tool_names, f"惊喜场景应包含配送任务，实际工具: {tool_names}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
