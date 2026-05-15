"""
排队查询工具
模拟美团排队取号 API
"""

from typing import Dict, Any
from datetime import datetime
from .base import BaseTool, ToolResult


class CheckQueueTool(BaseTool):
    """
    排队查询工具
    模拟美团排队取号 API
    """

    name = "check_queue"
    description = "查询餐厅排队状态并取号"
    parameters_schema = {
        "type": "object",
        "properties": {
            "restaurant_id": {
                "type": "string",
                "description": "餐厅ID"
            },
            "action": {
                "type": "string",
                "enum": ["check", "take_number"],
                "description": "操作类型：check=查询排队状态，take_number=取号"
            },
            "party_size": {
                "type": "integer",
                "description": "用餐人数（取号时需要）"
            }
        },
        "required": ["restaurant_id", "action"]
    }

    # Mock 排队数据（覆盖所有餐厅 ID）
    QUEUE_DATA = {
        "rest_001": {"waiting": 5, "estimated_wait": 25, "current_number": "A035", "next_number": "A036"},
        "rest_002": {"waiting": 25, "estimated_wait": 90, "current_number": "B120", "next_number": "B121"},
        "rest_003": {"waiting": 2, "estimated_wait": 10, "current_number": "C008", "next_number": "C009"},
        "rest_004": {"waiting": 8, "estimated_wait": 35, "current_number": "D012", "next_number": "D013"},
        "rest_005": {"waiting": 12, "estimated_wait": 45, "current_number": "E045", "next_number": "E046"},
        "rest_006": {"waiting": 6, "estimated_wait": 30, "current_number": "F020", "next_number": "F021"},
        "rest_007": {"waiting": 0, "estimated_wait": 0, "current_number": "G001", "next_number": "G002"},
        "rest_008": {"waiting": 15, "estimated_wait": 50, "current_number": "H078", "next_number": "H079"},
    }

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        restaurant_id = params.get("restaurant_id")
        action = params.get("action")

        queue_info = self.QUEUE_DATA.get(restaurant_id)
        # 如果 ID 不在预设列表中，自动生成默认排队数据（兼容非餐厅品类）
        if not queue_info:
            queue_info = {"waiting": 0, "estimated_wait": 0, "current_number": "Z001", "next_number": "Z002"}

        if action == "check":
            return ToolResult(
                success=True,
                data={
                    "restaurant_id": restaurant_id,
                    "waiting_count": queue_info["waiting"],
                    "estimated_wait_minutes": queue_info["estimated_wait"],
                    "current_number": queue_info["current_number"],
                    "message": f"当前排队 {queue_info['waiting']} 桌，预计等待 {queue_info['estimated_wait']} 分钟",
                },
            )

        elif action == "take_number":
            party_size = params.get("party_size", 2)
            my_number = queue_info["next_number"]

            # 更新排队数据
            queue_info["waiting"] += 1
            queue_info["next_number"] = chr(ord(my_number[0])) + str(int(my_number[1:]) + 1).zfill(3)

            return ToolResult(
                success=True,
                data={
                    "restaurant_id": restaurant_id,
                    "my_number": my_number,
                    "party_size": party_size,
                    "waiting_ahead": queue_info["waiting"] - 1,
                    "estimated_wait_minutes": queue_info["estimated_wait"],
                    "status": "queued",
                    "message": f"取号成功！您的排队号：{my_number}，前面还有 {queue_info['waiting'] - 1} 桌",
                },
            )

        return ToolResult(
            success=False,
            error_type="invalid_action",
            error_message=f"未知操作: {action}",
        )
