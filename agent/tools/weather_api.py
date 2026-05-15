"""
天气查询工具
模拟天气 API
"""

from typing import Dict, Any
from datetime import datetime
from .base import BaseTool, ToolResult


class WeatherAPITool(BaseTool):
    """
    天气查询工具
    模拟天气 API，用于检测天气变化触发重新规划
    """

    name = "weather_api"
    description = "查询天气信息，用于判断是否需要调整行程"
    parameters_schema = {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "日期，格式：YYYY-MM-DD"
            },
            "time": {
                "type": "string",
                "description": "时间，格式：HH:MM（可选）"
            },
            "location": {
                "type": "string",
                "description": "位置（可选，默认当前位置）"
            }
        },
        "required": ["date"]
    }

    # Mock 天气数据 - 模拟天气变化场景
    WEATHER_DATA = {
        "sunny": {
            "condition": "晴",
            "temperature": 28,
            "humidity": 45,
            "wind": "微风",
            "outdoor_friendly": True,
            "suggestion": "天气晴好，适合户外活动",
        },
        "rainy": {
            "condition": "阵雨",
            "temperature": 22,
            "humidity": 85,
            "wind": "东北风3级",
            "outdoor_friendly": False,
            "suggestion": "有降雨，建议安排室内活动",
        },
        "cloudy": {
            "condition": "多云",
            "temperature": 25,
            "humidity": 60,
            "wind": "微风",
            "outdoor_friendly": True,
            "suggestion": "天气舒适，适合外出",
        },
    }

    # 默认返回晴天，但可以通过配置切换为雨天来测试异常处理
    _mock_weather = "sunny"

    def set_mock_weather(self, weather: str):
        """设置 mock 天气状态（用于测试）"""
        self._mock_weather = weather

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        date = params.get("date")
        time = params.get("time", "14:00")
        location = params.get("location", "当前位置")

        weather = self.WEATHER_DATA.get(self._mock_weather, self.WEATHER_DATA["sunny"])

        # 模拟下午可能有雨的情况
        hour = int(time.split(":")[0]) if time else 14
        if 14 <= hour <= 17 and self._mock_weather == "rainy":
            weather = self.WEATHER_DATA["rainy"]

        return ToolResult(
            success=True,
            data={
                "date": date,
                "time": time,
                "location": location,
                **weather,
                "outdoor_recommendation": weather["outdoor_friendly"],
            },
        )
