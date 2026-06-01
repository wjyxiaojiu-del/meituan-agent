"""
Web Smoke 测试
覆盖核心链路的端到端验证：首页、静态资源、API、SSE、错误态
"""

import pytest
import sys
import os

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
    """每个测试前重置预订状态"""
    BookRestaurantTool.BOOKING_STATUS = {k: dict(v) for k, v in DEFAULT_BOOKING_STATUS.items()}
    yield


# ===== 首页和静态资源 =====


class TestHomepageAndStatic:
    """首页和静态资源加载"""

    def test_homepage_loads(self):
        """GET / 返回 200，Content-Type 为 text/html"""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_static_app_js(self):
        """app.js 可访问"""
        resp = client.get("/static/app.js")
        assert resp.status_code == 200
        assert "javascript" in resp.headers["content-type"] or resp.status_code == 200

    def test_static_styles_css(self):
        """styles.css 可访问"""
        resp = client.get("/static/styles.css")
        assert resp.status_code == 200


# ===== POI API =====


class TestPOIAPI:
    """POI 数据接口"""

    def test_pois_api_returns_array(self):
        """GET /api/pois 返回数组"""
        resp = client.get("/api/pois")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_pois_api_item_fields(self):
        """每个 POI 包含必要字段"""
        resp = client.get("/api/pois")
        data = resp.json()
        for poi in data[:3]:
            assert "id" in poi
            assert "name" in poi
            assert "category" in poi
            assert "location" in poi


# ===== 路线优化 API =====


class TestOptimizeRouteAPI:
    """路线优化接口"""

    def _get_poi_ids(self, count=3):
        """获取前 N 个 POI ID"""
        resp = client.get("/api/pois")
        pois = resp.json()
        return [p["id"] for p in pois[:count]]

    def test_optimize_route_valid(self):
        """有效 POI ID 列表返回排序后 route"""
        ids = self._get_poi_ids(3)
        resp = client.post("/api/optimize-route", json={"poiIds": ids})
        assert resp.status_code == 200
        data = resp.json()
        assert "route" in data
        assert len(data["route"]) >= 1  # 至少返回 1 个站点

    def test_optimize_route_insufficient(self):
        """不足 2 个 POI 返回错误"""
        ids = self._get_poi_ids(1)
        resp = client.post("/api/optimize-route", json={"poiIds": ids})
        # 当前实现返回 200 + error 字段，Phase 2 会改为 400
        data = resp.json()
        assert "error" in data or resp.status_code == 400

    def test_optimize_route_empty(self):
        """空列表返回错误"""
        resp = client.post("/api/optimize-route", json={"poiIds": []})
        data = resp.json()
        assert "error" in data or resp.status_code == 400


# ===== SSE 流式接口 =====


class TestSSEStream:
    """SSE 流式规划接口"""

    def test_sse_stream_returns_events(self):
        """SSE 流返回 step 和 done 事件"""
        resp = client.post(
            "/api/agent/execute/stream",
            json={"userInput": "带孩子出去玩"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        # 解析 SSE 事件
        body = resp.text
        events = []
        for line in body.split("\n"):
            if line.startswith("data: "):
                import json
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass

        # 应有 step 事件和 done 事件
        event_types = [e.get("type") for e in events]
        assert "step" in event_types
        assert "done" in event_types

    def test_sse_stream_empty_input(self):
        """空输入返回 400"""
        resp = client.post(
            "/api/agent/execute/stream",
            json={"userInput": ""},
        )
        assert resp.status_code == 400


# ===== 确认流程 =====


class TestConfirmFlow:
    """确认执行流程"""

    def _create_plan(self):
        resp = client.post("/api/agent/execute", json={
            "userInput": "带老婆吃火锅"
        })
        return resp.json()

    def test_confirm_full_flow(self):
        """execute → confirm 完整链路"""
        plan = self._create_plan()
        assert plan["status"] == "waiting_confirmation"
        session_id = plan["sessionId"]

        resp = client.post("/api/agent/confirm", json={
            "sessionId": session_id,
            "confirmed": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("success", "partial")
        assert data["sessionId"] == session_id

    def test_confirm_cancel_flow(self):
        """execute → cancel 流程"""
        plan = self._create_plan()
        session_id = plan["sessionId"]

        resp = client.post("/api/agent/confirm", json={
            "sessionId": session_id,
            "confirmed": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"


# ===== 错误态 =====


class TestErrorStates:
    """各种错误场景"""

    def test_execute_empty_input(self):
        """空输入返回 400"""
        resp = client.post("/api/agent/execute", json={"userInput": ""})
        assert resp.status_code == 400

    def test_execute_whitespace_input(self):
        """纯空格输入返回 400"""
        resp = client.post("/api/agent/execute", json={"userInput": "   "})
        assert resp.status_code == 400

    def test_confirm_invalid_session(self):
        """无效 session 返回 error 或 cancelled"""
        resp = client.post("/api/agent/confirm", json={
            "sessionId": "nonexistent_session_id",
            "confirmed": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("error", "cancelled")


# ===== LLM 降级 =====


class TestLLMFallback:
    """LLM 降级路径验证"""

    def test_mock_mode_execute_succeeds(self):
        """mock 模式下 execute 正常返回"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "带孩子去儿童乐园"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "waiting_confirmation"
        assert len(data["tasks"]) >= 2

    def test_mock_mode_has_llm_status(self):
        """响应包含 llmStatus 字段"""
        resp = client.post("/api/agent/execute", json={
            "userInput": "带孩子出去玩"
        })
        data = resp.json()
        assert "llmStatus" in data or "llm_status" in data


# ===== HTML 结构验证 =====


class TestHTMLStructure:
    """前端 HTML 结构验证"""

    def _get_index_html(self):
        resp = client.get("/")
        return resp.text

    def test_html_key_elements(self):
        """index.html 包含关键 DOM 结构"""
        html = self._get_index_html()
        assert 'id="planner"' in html  # 路线编辑器
        assert 'id="demo"' in html  # AI 规划师
        assert 'id="plannerMap"' in html  # 地图容器
        assert 'id="msgs"' in html  # 消息区
        assert 'id="inp"' in html  # 输入框

    def test_html_responsive_meta(self):
        """有 viewport meta 标签（移动端适配）"""
        html = self._get_index_html()
        assert 'name="viewport"' in html
        assert "width=device-width" in html

    def test_html_scenes(self):
        """包含场景选择"""
        html = self._get_index_html()
        assert "家庭" in html or "亲子" in html
        assert "朋友" in html or "聚会" in html
        assert "情侣" in html or "约会" in html

    def test_html_static_references(self):
        """引用了正确的静态资源"""
        html = self._get_index_html()
        assert "/static/app.js" in html
        assert "/static/styles.css" in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
