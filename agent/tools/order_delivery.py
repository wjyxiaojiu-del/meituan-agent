"""
即时配送工具
模拟美团闪购/外卖配送 API
"""

from typing import Dict, Any
from datetime import datetime, timedelta
from .base import BaseTool, ToolResult


class OrderDeliveryTool(BaseTool):
    """
    即时配送工具
    模拟美团闪购 API，支持定时配送
    """

    name = "order_delivery"
    description = "下单即时配送（鲜花、蛋糕、外卖等）"
    parameters_schema = {
        "type": "object",
        "properties": {
            "item_type": {
                "type": "string",
                "description": "商品类型，如：鲜花、蛋糕、外卖"
            },
            "item_name": {
                "type": "string",
                "description": "商品名称"
            },
            "quantity": {
                "type": "integer",
                "description": "数量"
            },
            "deliver_to": {
                "type": "string",
                "description": "配送地址，如：餐厅名称+座位号"
            },
            "deliver_time": {
                "type": "string",
                "description": "期望配送时间，格式：HH:MM，为空则尽快配送"
            },
            "message": {
                "type": "string",
                "description": "附带消息，如：贺卡内容"
            }
        },
        "required": ["item_type", "item_name", "deliver_to"]
    }

    # Mock 商品数据
    ITEMS = {
        "鲜花": {
            "rose_bouquet": {"name": "红玫瑰花束", "price": 199, "delivery_time": 40},
            "mixed_bouquet": {"name": "混搭花束", "price": 159, "delivery_time": 35},
            "sunflower": {"name": "向日葵花束", "price": 129, "delivery_time": 30},
        },
        "蛋糕": {
            "low_cal_chocolate": {"name": "低卡黑巧克力蛋糕", "price": 168, "delivery_time": 60},
            "fruit_cake": {"name": "水果鲜奶蛋糕", "price": 138, "delivery_time": 50},
        },
    }

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        item_type = params.get("item_type")
        item_name = params.get("item_name")
        deliver_to = params.get("deliver_to")
        deliver_time = params.get("deliver_time")
        quantity = params.get("quantity", 1)
        message = params.get("message", "")

        # 生成订单号
        order_id = f"DL{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 计算配送时间
        if deliver_time:
            delivery_estimate = f"预计 {deliver_time} 送达"
            scheduled = True
        else:
            delivery_estimate = "预计 40 分钟内送达"
            scheduled = False

        # 查找商品
        item_info = None
        items_of_type = self.ITEMS.get(item_type, {})
        for key, info in items_of_type.items():
            if item_name.lower() in info["name"].lower() or key in item_name.lower():
                item_info = info
                break

        if not item_info:
            # 默认商品
            item_info = {"name": item_name, "price": 99, "delivery_time": 40}

        total_price = item_info["price"] * quantity

        return ToolResult(
            success=True,
            data={
                "order_id": order_id,
                "item_name": item_info["name"],
                "quantity": quantity,
                "unit_price": item_info["price"],
                "total_price": total_price,
                "deliver_to": deliver_to,
                "deliver_time": deliver_time,
                "scheduled": scheduled,
                "delivery_estimate": delivery_estimate,
                "message": message,
                "status": "ordered",
                "tracking_url": f"https://m.meituan.com/track/{order_id}",
            },
        )
