"""
路线规划服务
从 Planner 中提取的路线规划相关逻辑
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta

from ..route_planner import RouteConstraints, RouteNode

logger = logging.getLogger(__name__)


class RouteService:
    """路线规划服务"""

    def __init__(self, route_planner, scene_manager=None):
        self.route_planner = route_planner
        self.scene_manager = scene_manager

    async def plan_from_intent(
        self,
        intent: Dict[str, Any],
        session_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[list, dict]:
        """
        根据意图规划路线

        Args:
            intent: 解析后的用户意图
            session_context: 会话上下文（用于读取 disliked_poi_ids / disliked_categories）

        Returns:
            (route_nodes, route_stats) 元组
        """
        session_context = session_context or {}
        disliked_poi_ids = list(session_context.get("disliked_poi_ids", []) or [])
        disliked_categories = list(session_context.get("disliked_categories", []) or [])
        people = intent.get("people", [])

        # === 用户指定了具体 POI：直接按顺序构建路线 ===
        specific_pois = intent.get("specific_pois")
        if specific_pois and self.route_planner:
            route = self.build_from_specific_pois(specific_pois, intent)
            if route:
                constraints = RouteConstraints(
                    start_time=datetime.now().replace(hour=14, minute=0, second=0, microsecond=0),
                    max_duration=480,
                    max_budget=5000,
                    group_size=max(len(people), 1),
                    transport_mode="walk",
                    excluded_poi_ids=disliked_poi_ids,
                    must_exclude=disliked_categories,
                )
                stats = self.route_planner._calculate_stats(route, constraints)
                return route, stats

        # 用 SceneManager 识别场景（规则 + LLM 联合），选择候选 POI
        if self.scene_manager:
            if hasattr(self.scene_manager, 'detect_scene_with_llm'):
                scene_type = await self.scene_manager.detect_scene_with_llm(intent)
            else:
                scene_type = self.scene_manager.detect_scene(intent)
            candidates = self.scene_manager.get_default_pois(
                scene_type, self.route_planner.poi_database
            )
            scene_config = self.scene_manager.get_scene_config(scene_type)
            default_duration = scene_config.get("default_duration", 360)
        else:
            # 降级：全选
            candidates = list(self.route_planner.poi_database.keys())
            default_duration = 360

        if not candidates:
            candidates = list(self.route_planner.poi_database.keys())

        # 构建约束
        group_size = len(people)
        budget = 1000
        for c in intent.get("constraints", []):
            if c.get("type") == "budget":
                if c.get("max"):
                    budget = c["max"]
                elif c.get("per_person") and group_size > 0:
                    budget = c["per_person"] * group_size
                break

        # 从场景配置获取 must_include 和 pace
        must_include = []
        pace = "normal"
        if self.scene_manager:
            must_include = scene_config.get("poi_types", [])[:3]  # 前3个品类作为必须
            pace = scene_config.get("pace", "normal")

        # 从 intent 读取时间偏好
        start_hour = 14
        tp = intent.get("time_preference", "") or ""
        if "上午" in tp or "早上" in tp:
            start_hour = 9
        elif "中午" in tp:
            start_hour = 11
        elif "下午" in tp:
            start_hour = 14
        elif "晚上" in tp or "傍晚" in tp:
            start_hour = 18

        constraints = RouteConstraints(
            start_time=datetime.now().replace(hour=start_hour, minute=0, second=0, microsecond=0),
            max_duration=default_duration,
            max_budget=budget,
            group_size=max(group_size, 1),
            transport_mode="walk",
            must_include=must_include,
            must_exclude=disliked_categories,
            excluded_poi_ids=disliked_poi_ids,
            pace=pace,
        )

        route, stats = self.route_planner.plan_route(
            candidate_pois=candidates,
            constraints=constraints,
            emotion=intent.get("mood"),
        )

        return route, stats

    def build_from_specific_pois(self, specific_pois: list, intent: dict) -> Optional[list]:
        """
        用户指定了具体 POI，按顺序构建路线

        Args:
            specific_pois: POI 名称列表
            intent: 用户意图

        Returns:
            RouteNode 列表，或 None（匹配不足时）
        """
        logger.info(f"build_from_specific_pois called with: {specific_pois}")

        if not self.route_planner:
            logger.warning("route_planner is None")
            return None

        # 按名称匹配 POI
        matched = []
        for name in specific_pois:
            name_lower = name.strip().lower()
            found = None
            for poi in self.route_planner.poi_database.values():
                if poi.name.lower() == name_lower or name_lower in poi.name.lower():
                    found = poi
                    break
            if found:
                matched.append(found)
                logger.info(f"匹配到 POI: {name} -> {found.name}")
            else:
                logger.warning(f"未找到 POI: {name}")

        if len(matched) < 2:
            logger.warning(f"匹配到的 POI 不足 2 个，降级到场景规划")
            return None

        # 根据时间偏好确定起始时间
        start_hour = 14
        tp = intent.get("time_preference", "") or ""
        if "上午" in tp or "早上" in tp:
            start_hour = 9
        elif "中午" in tp:
            start_hour = 11
        elif "下午" in tp:
            start_hour = 14
        elif "晚上" in tp or "傍晚" in tp:
            start_hour = 18

        current_time = datetime.now().replace(hour=start_hour, minute=0, second=0, microsecond=0)
        route = []

        for i, poi in enumerate(matched):
            if i == 0:
                # 第一个站点
                node = RouteNode(
                    poi=poi,
                    arrival_time=current_time,
                    departure_time=current_time + timedelta(minutes=poi.avg_duration),
                    travel_time_from_prev=0,
                    travel_distance_from_prev=0,
                    estimated_queue_time=0,
                    activity_type="play",
                )
            else:
                # 计算与上一个站点的距离和时间
                prev_poi = matched[i - 1]
                dist = self.route_planner.calculate_distance(prev_poi, poi)
                travel_time = max(1, int(dist / 1000 / 5 * 60))  # 步行 5km/h

                arrival = route[-1].departure_time + timedelta(minutes=travel_time)
                departure = arrival + timedelta(minutes=poi.avg_duration)

                node = RouteNode(
                    poi=poi,
                    arrival_time=arrival,
                    departure_time=departure,
                    travel_time_from_prev=travel_time,
                    travel_distance_from_prev=dist,
                    estimated_queue_time=0,
                    activity_type="play",
                )
            route.append(node)

        logger.info(f"用户指定路线构建完成: {[n.poi.name for n in route]}")
        return route
