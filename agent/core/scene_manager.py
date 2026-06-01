"""
场景管理器
识别用户场景，加载对应的默认配置
支持规则快速通道 + LLM 兜底
"""

import logging
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SceneType(Enum):
    FAMILY = "family"
    FRIENDS = "friends"
    DATE = "date"
    TEAM_BUILDING = "team_building"
    SOLO = "solo"
    PARENT_CHILD = "parent_child"


SCENE_POI_PREFERENCES = {
    SceneType.FAMILY: {
        "poi_types": ["儿童乐园", "博物馆", "公园", "餐厅", "小吃街", "酒店"],
        "default_budget_per_person": 200,
        "default_duration": 420,
        "pace": "normal",
    },
    SceneType.FRIENDS: {
        "poi_types": ["密室逃脱", "剧本杀", "KTV", "餐厅", "咖啡馆", "小吃街", "酒店"],
        "default_budget_per_person": 150,
        "default_duration": 420,
        "pace": "normal",
    },
    SceneType.DATE: {
        "poi_types": ["花店", "咖啡馆", "餐厅", "电影院", "书店", "SPA", "酒店"],
        "default_budget_per_person": 300,
        "default_duration": 300,
        "pace": "slow",
    },
    SceneType.TEAM_BUILDING: {
        "poi_types": ["会议室", "轰趴馆", "KTV", "餐厅", "户外拓展", "酒店"],
        "default_budget_per_person": 200,
        "default_duration": 480,
        "pace": "normal",
    },
    SceneType.SOLO: {
        "poi_types": ["书店", "咖啡馆", "餐厅", "SPA", "电影院", "酒店"],
        "default_budget_per_person": 150,
        "default_duration": 240,
        "pace": "slow",
    },
    SceneType.PARENT_CHILD: {
        "poi_types": ["儿童乐园", "博物馆", "公园", "餐厅", "酒店"],
        "default_budget_per_person": 200,
        "default_duration": 360,
        "pace": "slow",
    },
}


class SceneManager:
    """场景管理器"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def detect_scene(self, intent: Dict) -> SceneType:
        """从意图中识别场景类型（规则快速通道）"""
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

    async def detect_scene_with_llm(self, intent: Dict) -> SceneType:
        """规则 + LLM 联合场景识别（规则优先，不确定时用 LLM）"""
        # 规则快速通道
        rule_result = self.detect_scene(intent)

        # 如果规则结果明确（有孩子/伴侣/团建关键词），直接返回
        people = intent.get("people", [])
        roles = [p.get("role", "") for p in people]
        user_input = intent.get("raw_input", "")
        if ("child" in roles
                or any(r in ("wife", "husband", "girlfriend", "boyfriend") for r in roles)
                or any(kw in user_input for kw in ["团建", "公司", "同事"])):
            return rule_result

        # 不确定的情况：用 LLM 兜底
        if not self.llm_client or not self.llm_client.is_available():
            return rule_result

        try:
            people_desc = "、".join(
                f"{p.get('role', '朋友')}" + (f"({p.get('age', '')}岁)" if p.get("age") else "")
                for p in people
            ) or "未知"
            prompt = f"""判断用户出行场景，只输出一个词：
family/friends/date/team_building/solo/parent_child

用户：{user_input}
同行人：{people_desc}

只输出一个英文单词，不要其他文字。"""

            resp = await self.llm_client.chat([{"role": "user", "content": prompt}])
            resp = resp.strip().lower()

            # 解析 LLM 返回
            scene_map = {s.value: s for s in SceneType}
            for key, scene in scene_map.items():
                if key in resp:
                    logger.info(f"LLM 场景识别: {user_input[:20]}... → {scene.value}")
                    return scene

            return rule_result
        except Exception as e:
            logger.warning(f"LLM 场景识别失败，使用规则结果: {e}")
            return rule_result

    def get_scene_config(self, scene_type: SceneType) -> Dict:
        return SCENE_POI_PREFERENCES.get(scene_type, SCENE_POI_PREFERENCES[SceneType.FRIENDS])

    def get_default_pois(self, scene_type: SceneType, poi_database: Dict) -> List[str]:
        config = self.get_scene_config(scene_type)
        preferred_types = config["poi_types"]
        return [
            poi_id for poi_id, poi in poi_database.items()
            if poi.category in preferred_types
        ]
