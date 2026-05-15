"""
场地预订工具
支持会议室、轰趴馆、拓展基地等团建场地预订
"""

from typing import Dict, Any
from datetime import datetime
from .base import BaseTool, ToolResult


class BookVenueTool(BaseTool):
    """场地预订工具（会议室/轰趴馆/拓展基地）"""

    name = "book_venue"
    description = "预订团建/聚会场地（会议室、轰趴馆、拓展基地）"
    parameters_schema = {
        "type": "object",
        "properties": {
            "venue_id": {"type": "string", "description": "场地ID"},
            "venue_name": {"type": "string", "description": "场地名称"},
            "date": {"type": "string", "description": "日期 YYYY-MM-DD"},
            "start_time": {"type": "string", "description": "开始时间 HH:MM"},
            "end_time": {"type": "string", "description": "结束时间 HH:MM"},
            "group_size": {"type": "integer", "description": "人数"},
            "requirements": {
                "type": "array",
                "items": {"type": "string"},
                "description": "特殊需求（投影、白板、KTV设备等）",
            },
        },
        "required": ["venue_id", "date", "start_time", "end_time", "group_size"],
    }

    MOCK_VENUES = {
        "party_001": {
            "name": "Party King 轰趴馆",
            "capacity": 50,
            "price_per_hour": 300,
            "available": True,
            "equipment": ["KTV", "桌游", "台球", "Switch", "投影", "自助厨房"],
        },
        "meet_001": {
            "name": "WeWork 联合办公",
            "capacity": 30,
            "price_per_hour": 200,
            "available": True,
            "equipment": ["投影", "白板", "音响", "视频会议", "打印机"],
        },
        "outdoor_001": {
            "name": "勇者户外拓展基地",
            "capacity": 100,
            "price_per_hour": 500,
            "available": True,
            "equipment": ["攀岩墙", "真人CS装备", "烧烤架", "篝火场地"],
        },
    }

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        venue_id = params.get("venue_id")
        group_size = params.get("group_size", 1)
        date = params.get("date", "")
        start_time = params.get("start_time", "")
        end_time = params.get("end_time", "")
        requirements = params.get("requirements", [])

        venue = self.MOCK_VENUES.get(venue_id)
        if not venue:
            # 兼容未知 ID：自动生成可用状态
            venue = {
                "name": venue_id,
                "capacity": 100,
                "price_per_hour": 200,
                "available": True,
                "equipment": [],
            }

        if not venue["available"]:
            return ToolResult(
                success=False,
                error_type="venue_unavailable",
                error_message=f"{venue['name']} 当前不可用",
            )

        if venue["capacity"] < group_size:
            return ToolResult(
                success=False,
                error_type="capacity_exceeded",
                error_message=f"{venue['name']} 容量{venue['capacity']}人，需要{group_size}人",
            )

        # 计算费用（支持跨午夜）
        try:
            start_h, start_m = map(int, start_time.split(":"))
            end_h, end_m = map(int, end_time.split(":"))
            start_total = start_h * 60 + start_m
            end_total = end_h * 60 + end_m
            if end_total <= start_total:
                end_total += 24 * 60  # 跨午夜：加 24 小时
            hours = max(1, (end_total - start_total + 59) // 60)
        except (ValueError, AttributeError):
            hours = 4  # 默认半天

        total_price = venue["price_per_hour"] * hours

        booking_id = f"VN{datetime.now().strftime('%Y%m%d%H%M%S')}"

        return ToolResult(
            success=True,
            data={
                "booking_id": booking_id,
                "venue_id": venue_id,
                "venue_name": venue["name"],
                "date": date,
                "start_time": start_time,
                "end_time": end_time,
                "group_size": group_size,
                "hours": hours,
                "total_price": total_price,
                "equipment": venue["equipment"],
                "requirements": requirements,
                "status": "confirmed",
            },
        )
