"""
餐厅预订工具
模拟美团餐厅预订 API
"""

from typing import Dict, Any
from datetime import datetime
from .base import BaseTool, ToolResult


class BookRestaurantTool(BaseTool):
    """
    餐厅预订工具
    模拟美团餐厅预订 API
    """

    name = "book_restaurant"
    description = "预订餐厅座位"
    parameters_schema = {
        "type": "object",
        "properties": {
            "restaurant_id": {
                "type": "string",
                "description": "餐厅ID"
            },
            "restaurant_name": {
                "type": "string",
                "description": "餐厅名称（用于确认）"
            },
            "time": {
                "type": "string",
                "description": "预订时间，格式：HH:MM"
            },
            "date": {
                "type": "string",
                "description": "预订日期，格式：YYYY-MM-DD"
            },
            "party_size": {
                "type": "integer",
                "description": "用餐人数"
            },
            "special_requests": {
                "type": "array",
                "items": {"type": "string"},
                "description": "特殊要求，如：宝宝椅、靠窗位置"
            }
        },
        "required": ["restaurant_id", "time", "party_size"]
    }

    # Mock 预订状态（覆盖所有餐厅 ID）
    BOOKING_STATUS = {
        "rest_001": {"available": True, "capacity": 60, "booked": 35, "name": "新元素餐厅"},
        "rest_002": {"available": True, "capacity": 100, "booked": 80, "name": "海底捞火锅"},
        "rest_003": {"available": True, "capacity": 40, "booked": 20, "name": "wagas"},
        "rest_004": {"available": True, "capacity": 80, "booked": 50, "name": "西贝莜面村"},
        "rest_005": {"available": True, "capacity": 30, "booked": 15, "name": "一兰拉面"},
        "rest_006": {"available": True, "capacity": 80, "booked": 40, "name": "木屋烧烤"},
        "rest_007": {"available": True, "capacity": 30, "booked": 10, "name": "素宿素食"},
        "rest_008": {"available": True, "capacity": 120, "booked": 90, "name": "外婆家"},
    }

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        restaurant_id = params.get("restaurant_id")
        time = params.get("time")
        party_size = params.get("party_size")
        date = params.get("date", datetime.now().strftime("%Y-%m-%d"))
        special_requests = params.get("special_requests", [])

        # 拒绝 None/空 restaurant_id（引用解析失败的产物）
        if not restaurant_id or not str(restaurant_id).strip():
            return ToolResult(
                success=False,
                error_type="invalid_params",
                error_message="restaurant_id 为空，可能是搜索结果引用解析失败",
            )

        status = self.BOOKING_STATUS.get(restaurant_id)

        # 如果 ID 不在预设列表中，自动生成可用状态（兼容非餐厅品类的预订）
        if not status:
            status = {"available": True, "capacity": 100, "booked": 0, "name": restaurant_id}

        if not status["available"]:
            return ToolResult(
                success=False,
                error_type="seat_unavailable",
                error_message=f"餐厅 {restaurant_id} 已满座，当前已预订 {status['booked']}/{status['capacity']}",
            )

        # 检查容量
        if status["booked"] + party_size > status["capacity"]:
            return ToolResult(
                success=False,
                error_type="seat_unavailable",
                error_message=f"剩余座位不足，当前剩余 {status['capacity'] - status['booked']} 位",
            )

        # 预订成功
        booking_id = f"BK{datetime.now().strftime('%Y%m%d%H%M%S')}"
        status["booked"] += party_size

        return ToolResult(
            success=True,
            data={
                "booking_id": booking_id,
                "restaurant_id": restaurant_id,
                "restaurant_name": status.get("name", restaurant_id),
                "date": date,
                "time": time,
                "party_size": party_size,
                "special_requests": special_requests,
                "status": "confirmed",
                "message": f"预订成功！预订号：{booking_id}",
            },
        )
