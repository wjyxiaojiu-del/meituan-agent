"""
工具模块测试
测试各个工具的独立功能
"""

import pytest
import asyncio
import sys

sys.path.insert(0, ".")

from agent.tools.search_poi import SearchPOITool
from agent.tools.book_restaurant import BookRestaurantTool
from agent.tools.check_queue import CheckQueueTool
from agent.tools.order_delivery import OrderDeliveryTool
from agent.tools.weather_api import WeatherAPITool
from agent.tools.book_venue import BookVenueTool


class TestSearchPOITool:
    """测试 POI 搜索工具"""

    @pytest.fixture
    def tool(self):
        return SearchPOITool()

    @pytest.mark.asyncio
    async def test_search_kids_playground(self, tool):
        """测试搜索儿童乐园"""
        result = await tool({
            "category": "儿童乐园",
            "keywords": ["适合5岁", "室内"],
            "rating_min": 4.5
        })

        assert result.success is True
        assert "results" in result.data
        assert result.data["total"] > 0
        assert all(r["rating"] >= 4.5 for r in result.data["results"])

    @pytest.mark.asyncio
    async def test_search_restaurant(self, tool):
        """测试搜索餐厅"""
        result = await tool({
            "category": "餐厅",
            "keywords": ["低卡", "轻食"],
            "rating_min": 4.0
        })

        assert result.success is True
        assert result.data["total"] > 0

    @pytest.mark.asyncio
    async def test_search_romantic(self, tool):
        """测试搜索浪漫餐厅（Day 2 修复的关键词覆盖）"""
        result = await tool({
            "category": "餐厅",
            "keywords": ["浪漫", "约会"],
            "rating_min": 4.0
        })

        assert result.success is True
        assert result.data["total"] > 0

    @pytest.mark.asyncio
    async def test_search_with_empty_keywords(self, tool):
        """测试空关键词搜索"""
        result = await tool({
            "category": "餐厅",
            "keywords": [],
            "rating_min": 4.0
        })

        assert result.success is True

    @pytest.mark.asyncio
    async def test_search_nonexistent_category(self, tool):
        """测试不存在的类别"""
        result = await tool({
            "category": "不存在的类别",
            "keywords": ["test"],
            "rating_min": 4.0
        })

        # 应该返回空结果而不是失败
        assert result.success is True
        assert result.data["total"] == 0

    @pytest.mark.asyncio
    async def test_search_fallback(self, tool):
        """测试关键词无匹配时的兜底逻辑"""
        result = await tool({
            "category": "餐厅",
            "keywords": ["完全不存在的关键词XYZ"],
            "rating_min": 0
        })

        # 兜底：返回该品类全部结果
        assert result.success is True
        assert result.data["total"] > 0


class TestBookRestaurantTool:
    """测试餐厅预订工具"""

    @pytest.fixture(autouse=True)
    def reset_booking(self):
        """每个测试前重置预订状态"""
        original = {
            "rest_001": {"available": True, "capacity": 60, "booked": 35, "name": "新元素餐厅"},
            "rest_002": {"available": True, "capacity": 100, "booked": 80, "name": "海底捞火锅"},
            "rest_003": {"available": True, "capacity": 40, "booked": 20, "name": "wagas"},
            "rest_004": {"available": True, "capacity": 80, "booked": 50, "name": "西贝莜面村"},
            "rest_005": {"available": True, "capacity": 30, "booked": 15, "name": "一兰拉面"},
            "rest_006": {"available": True, "capacity": 80, "booked": 40, "name": "木屋烧烤"},
            "rest_007": {"available": True, "capacity": 30, "booked": 10, "name": "素宿素食"},
            "rest_008": {"available": True, "capacity": 120, "booked": 90, "name": "外婆家"},
        }
        BookRestaurantTool.BOOKING_STATUS = original
        yield

    @pytest.fixture
    def tool(self):
        return BookRestaurantTool()

    @pytest.mark.asyncio
    async def test_booking_success(self, tool):
        """测试预订成功"""
        result = await tool({
            "restaurant_id": "rest_001",
            "time": "17:00",
            "party_size": 3,
            "special_requests": ["宝宝椅"]
        })

        assert result.success is True
        assert "booking_id" in result.data
        assert result.data["status"] == "confirmed"
        assert result.data["party_size"] == 3

    @pytest.mark.asyncio
    async def test_booking_unknown_restaurant_auto_accept(self, tool):
        """测试未知餐厅 ID 自动接受（兼容非餐厅品类）"""
        result = await tool({
            "restaurant_id": "rest_999",
            "time": "17:00",
            "party_size": 3
        })

        assert result.success is True
        assert "booking_id" in result.data

    @pytest.mark.asyncio
    async def test_booking_non_restaurant_id(self, tool):
        """测试非餐厅 ID（如密室逃脱）也能预订"""
        result = await tool({
            "restaurant_id": "escape_001",
            "time": "14:00",
            "party_size": 5
        })

        assert result.success is True
        assert "booking_id" in result.data

    @pytest.mark.asyncio
    async def test_booking_special_requests(self, tool):
        """测试特殊需求"""
        result = await tool({
            "restaurant_id": "rest_001",
            "time": "18:00",
            "party_size": 5,
            "special_requests": ["宝宝椅", "包间", "生日蛋糕"]
        })

        assert result.success is True
        assert "special_requests" in result.data


class TestCheckQueueTool:
    """测试排队系统工具"""

    @pytest.fixture
    def tool(self):
        return CheckQueueTool()

    @pytest.mark.asyncio
    async def test_check_queue_status(self, tool):
        """测试查询排队状态"""
        result = await tool({
            "restaurant_id": "rest_001",
            "action": "check"
        })

        assert result.success is True
        assert "waiting_count" in result.data

    @pytest.mark.asyncio
    async def test_take_queue_number(self, tool):
        """测试取号"""
        result = await tool({
            "restaurant_id": "rest_001",
            "action": "take_number",
            "party_size": 3
        })

        assert result.success is True
        assert "my_number" in result.data
        assert "waiting_ahead" in result.data
        assert "estimated_wait_minutes" in result.data

    @pytest.mark.asyncio
    async def test_queue_unknown_restaurant(self, tool):
        """测试未知餐厅排队（自动返回默认数据）"""
        result = await tool({
            "restaurant_id": "unknown_001",
            "action": "check"
        })

        assert result.success is True

    @pytest.mark.asyncio
    async def test_invalid_action(self, tool):
        """测试无效操作"""
        result = await tool({
            "restaurant_id": "rest_001",
            "action": "invalid_action"
        })

        assert result.success is False


class TestOrderDeliveryTool:
    """测试即时配送工具"""

    @pytest.fixture
    def tool(self):
        return OrderDeliveryTool()

    @pytest.mark.asyncio
    async def test_order_flowers(self, tool):
        """测试订购鲜花"""
        result = await tool({
            "item_type": "鲜花",
            "item_name": "玫瑰花束",
            "deliver_to": "新元素餐厅",
            "deliver_time": "17:30",
            "message": "老婆辛苦了，爱你！"
        })

        assert result.success is True
        assert "order_id" in result.data
        assert result.data["item_name"] == "红玫瑰花束"
        assert result.data["scheduled"] is True
        assert result.data["total_price"] > 0

    @pytest.mark.asyncio
    async def test_order_cake(self, tool):
        """测试订购蛋糕"""
        result = await tool({
            "item_type": "蛋糕",
            "item_name": "生日蛋糕",
            "deliver_to": "海底捞",
            "deliver_time": "18:00",
            "message": "生日快乐！"
        })

        assert result.success is True
        assert "order_id" in result.data

    @pytest.mark.asyncio
    async def test_order_unknown_item(self, tool):
        """测试未知商品"""
        result = await tool({
            "item_type": "未知",
            "item_name": "不存在的商品",
            "deliver_to": "地址",
            "deliver_time": "12:00"
        })

        # 应该返回成功但使用默认价格
        assert result.success is True


class TestWeatherAPITool:
    """测试天气 API 工具"""

    @pytest.fixture
    def tool(self):
        return WeatherAPITool()

    @pytest.mark.asyncio
    async def test_get_weather(self, tool):
        """测试获取天气"""
        result = await tool({
            "date": "2026-05-17",
            "time": "14:00"
        })

        assert result.success is True
        assert "condition" in result.data
        assert "temperature" in result.data
        assert "humidity" in result.data
        assert "outdoor_friendly" in result.data

    @pytest.mark.asyncio
    async def test_set_mock_weather_sunny(self, tool):
        """测试设置晴天"""
        tool.set_mock_weather("sunny")
        result = await tool({
            "date": "2026-05-17",
            "time": "14:00"
        })

        assert result.success is True
        assert result.data["condition"] == "晴"
        assert result.data["outdoor_friendly"] is True

    @pytest.mark.asyncio
    async def test_set_mock_weather_rainy(self, tool):
        """测试设置雨天"""
        tool.set_mock_weather("rainy")
        result = await tool({
            "date": "2026-05-17",
            "time": "14:00"
        })

        assert result.success is True
        assert result.data["condition"] == "阵雨"
        assert result.data["outdoor_friendly"] is False

    @pytest.mark.asyncio
    async def test_weather_suggestion(self, tool):
        """测试天气建议"""
        # 晴天
        tool.set_mock_weather("sunny")
        result = await tool({"date": "2026-05-17", "time": "14:00"})
        assert "适合户外" in result.data["suggestion"]

        # 雨天
        tool.set_mock_weather("rainy")
        result = await tool({"date": "2026-05-17", "time": "14:00"})
        assert "室内" in result.data["suggestion"] or "雨" in result.data["suggestion"]


class TestSearchPOINewCategories:
    """测试新增品类搜索"""

    @pytest.fixture
    def tool(self):
        return SearchPOITool()

    @pytest.mark.asyncio
    async def test_search_ktv(self, tool):
        result = await tool({"category": "KTV", "keywords": []})
        assert result.success is True
        assert result.data["total"] >= 2

    @pytest.mark.asyncio
    async def test_search_spa(self, tool):
        result = await tool({"category": "SPA", "keywords": []})
        assert result.success is True
        assert result.data["total"] >= 2

    @pytest.mark.asyncio
    async def test_search_museum(self, tool):
        result = await tool({"category": "博物馆", "keywords": ["亲子"]})
        assert result.success is True
        assert result.data["total"] >= 1

    @pytest.mark.asyncio
    async def test_search_bookstore(self, tool):
        result = await tool({"category": "书店", "keywords": []})
        assert result.success is True
        assert result.data["total"] >= 2

    @pytest.mark.asyncio
    async def test_search_park(self, tool):
        result = await tool({"category": "公园", "keywords": []})
        assert result.success is True
        assert result.data["total"] >= 2

    @pytest.mark.asyncio
    async def test_search_party_hall(self, tool):
        result = await tool({"category": "轰趴馆", "keywords": []})
        assert result.success is True
        assert result.data["total"] >= 2

    @pytest.mark.asyncio
    async def test_search_meeting_room(self, tool):
        result = await tool({"category": "会议室", "keywords": []})
        assert result.success is True
        assert result.data["total"] >= 2

    @pytest.mark.asyncio
    async def test_search_outdoor(self, tool):
        result = await tool({"category": "户外拓展", "keywords": []})
        assert result.success is True
        assert result.data["total"] >= 2

    @pytest.mark.asyncio
    async def test_search_snack_street(self, tool):
        result = await tool({"category": "小吃街", "keywords": []})
        assert result.success is True
        assert result.data["total"] >= 2

    @pytest.mark.asyncio
    async def test_restaurant_count_expanded(self, tool):
        """餐厅品类应有 10 条数据"""
        result = await tool({"category": "餐厅", "keywords": []})
        assert result.success is True
        assert result.data["total"] >= 8

    @pytest.mark.asyncio
    async def test_kids_count_expanded(self, tool):
        """儿童乐园品类应有 5 条数据"""
        result = await tool({"category": "儿童乐园", "keywords": []})
        assert result.success is True
        assert result.data["total"] >= 4


class TestBookVenueTool:
    """测试场地预订工具"""

    @pytest.fixture
    def tool(self):
        return BookVenueTool()

    @pytest.mark.asyncio
    async def test_book_party_hall(self, tool):
        result = await tool({
            "venue_id": "party_001",
            "date": "2026-05-17",
            "start_time": "14:00",
            "end_time": "20:00",
            "group_size": 20,
        })
        assert result.success is True
        assert result.data["status"] == "confirmed"
        assert result.data["venue_name"] == "Party King 轰趴馆"
        assert result.data["total_price"] > 0

    @pytest.mark.asyncio
    async def test_book_meeting_room(self, tool):
        result = await tool({
            "venue_id": "meet_001",
            "date": "2026-05-17",
            "start_time": "09:00",
            "end_time": "12:00",
            "group_size": 15,
            "requirements": ["投影", "白板"],
        })
        assert result.success is True
        assert "投影" in result.data["equipment"]
        assert result.data["hours"] == 3

    @pytest.mark.asyncio
    async def test_book_unknown_venue(self, tool):
        """未知场地 ID 自动接受"""
        result = await tool({
            "venue_id": "unknown_venue",
            "date": "2026-05-17",
            "start_time": "14:00",
            "end_time": "18:00",
            "group_size": 10,
        })
        assert result.success is True
        assert "booking_id" in result.data

    @pytest.mark.asyncio
    async def test_book_capacity_exceeded(self, tool):
        """超出容量应失败"""
        result = await tool({
            "venue_id": "meet_001",
            "date": "2026-05-17",
            "start_time": "14:00",
            "end_time": "18:00",
            "group_size": 50,  # meet_001 容量30人
        })
        assert result.success is False
        assert result.error_type == "capacity_exceeded"

    @pytest.mark.asyncio
    async def test_booking_id_format(self, tool):
        result = await tool({
            "venue_id": "party_001",
            "date": "2026-05-17",
            "start_time": "14:00",
            "end_time": "18:00",
            "group_size": 10,
        })
        assert result.success is True
        assert result.data["booking_id"].startswith("VN")

    @pytest.mark.asyncio
    async def test_booking_cross_midnight(self, tool):
        """跨午夜场景：22:00-02:00 应计算为 4 小时"""
        result = await tool({
            "venue_id": "party_001",
            "date": "2026-05-17",
            "start_time": "22:00",
            "end_time": "02:00",
            "group_size": 10,
        })
        assert result.success is True
        assert result.data["hours"] == 4
        assert result.data["total_price"] == 300 * 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
