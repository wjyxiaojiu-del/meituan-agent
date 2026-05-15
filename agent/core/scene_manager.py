"""
场景管理器
识别用户场景，加载对应的默认配置
"""

from enum import Enum
from typing import Dict, List


class SceneType(Enum):
    FAMILY = "family"
    FRIENDS = "friends"
    DATE = "date"
    TEAM_BUILDING = "team_building"
    SOLO = "solo"
    PARENT_CHILD = "parent_child"


SCENE_POI_PREFERENCES = {
    SceneType.FAMILY: {
        "poi_types": ["儿童乐园", "博物馆", "公园", "餐厅", "小吃街"],
        "default_budget_per_person": 200,
        "default_duration": 360,
        "pace": "slow",
    },
    SceneType.FRIENDS: {
        "poi_types": ["密室逃脱", "剧本杀", "KTV", "餐厅", "咖啡馆", "小吃街"],
        "default_budget_per_person": 150,
        "default_duration": 420,
        "pace": "normal",
    },
    SceneType.DATE: {
        "poi_types": ["花店", "咖啡馆", "餐厅", "电影院", "书店", "SPA"],
        "default_budget_per_person": 300,
        "default_duration": 300,
        "pace": "slow",
    },
    SceneType.TEAM_BUILDING: {
        "poi_types": ["会议室", "轰趴馆", "户外拓展", "餐厅", "KTV"],
        "default_budget_per_person": 200,
        "default_duration": 480,
        "pace": "normal",
    },
    SceneType.SOLO: {
        "poi_types": ["书店", "咖啡馆", "餐厅", "SPA", "电影院"],
        "default_budget_per_person": 150,
        "default_duration": 240,
        "pace": "slow",
    },
    SceneType.PARENT_CHILD: {
        "poi_types": ["儿童乐园", "博物馆", "公园", "餐厅"],
        "default_budget_per_person": 200,
        "default_duration": 360,
        "pace": "slow",
    },
}


class SceneManager:
    """场景管理器"""

    def detect_scene(self, intent: Dict) -> SceneType:
        """从意图中识别场景类型"""
        people = intent.get("people", [])
        user_input = intent.get("raw_input", "")

        if any(kw in user_input for kw in ["团建", "公司", "同事", "部门", "年会"]):
            return SceneType.TEAM_BUILDING

        roles = [p.get("role", "") for p in people]
        has_child = "child" in roles
        has_partner = any(r in ("wife", "husband", "girlfriend", "boyfriend") for r in roles)

        if has_child:
            return SceneType.FAMILY if has_partner else SceneType.PARENT_CHILD

        if has_partner:
            return SceneType.DATE

        if len(people) >= 3:
            return SceneType.FRIENDS

        if len(people) <= 1:
            return SceneType.SOLO

        return SceneType.FRIENDS

    def get_scene_config(self, scene_type: SceneType) -> Dict:
        return SCENE_POI_PREFERENCES.get(scene_type, SCENE_POI_PREFERENCES[SceneType.FRIENDS])

    def get_default_pois(self, scene_type: SceneType, poi_database: Dict) -> List[str]:
        config = self.get_scene_config(scene_type)
        preferred_types = config["poi_types"]
        return [
            poi_id for poi_id, poi in poi_database.items()
            if poi.category in preferred_types
        ]
