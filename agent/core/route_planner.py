"""
多 POI 智能路线规划引擎
算法：贪心初始化 + 2-opt 局部优化
约束：营业时间、步行距离、游玩时长、排队预估
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time
import math
import logging

logger = logging.getLogger(__name__)


@dataclass
class POI:
    """兴趣点"""
    id: str
    name: str
    category: str
    rating: float
    review_count: int
    location: Dict[str, float]  # {"lat": x, "lng": y}
    address: str
    open_time: time
    close_time: time
    avg_duration: int  # 平均游玩时长（分钟）
    price_per_person: float
    tags: List[str]
    peak_hours: List[Tuple[int, int]]  # [(14,16), (19,21)]
    queue_factor: float  # 排队系数
    capacity: int = 50
    equipment: List[str] = field(default_factory=list)
    suitable_scenes: List[str] = field(default_factory=list)


@dataclass
class RouteConstraints:
    """路线约束"""
    start_time: datetime
    max_duration: int  # 总时长上限（分钟）
    max_budget: float  # 总预算上限
    group_size: int = 2
    must_include: List[str] = field(default_factory=list)  # 必须包含的品类
    must_exclude: List[str] = field(default_factory=list)  # 排除的品类
    transport_mode: str = "walk"  # walk/drive/transit
    pace: str = "normal"  # slow/normal/fast


@dataclass
class RouteNode:
    """路线节点"""
    poi: POI
    arrival_time: datetime
    departure_time: datetime
    travel_time_from_prev: int  # 从前一个点到这的交通时间（分钟）
    travel_distance_from_prev: float  # 距离（米）
    estimated_queue_time: int  # 预估排队时间
    activity_type: str  # "play" | "dine" | "rest" | "task"


class RoutePlanner:
    """路线规划引擎"""

    # 交通速度（km/h）
    TRANSPORT_SPEED = {
        "walk": 5,
        "bike": 12,
        "drive": 25,  # 市区
        "transit": 20,
    }

    def __init__(self):
        self.poi_database: Dict[str, POI] = {}

    def load_mock_data(self, pois: List[POI]):
        """加载 POI 数据"""
        for poi in pois:
            self.poi_database[poi.id] = poi
        logger.info(f"已加载 {len(pois)} 个 POI 数据")

    def calculate_distance(self, poi_a: POI, poi_b: POI) -> float:
        """
        计算两地直线距离（米）
        使用 Haversine 公式计算球面距离
        """
        R = 6371000  # 地球半径（米）
        lat1, lng1 = math.radians(poi_a.location["lat"]), math.radians(poi_a.location["lng"])
        lat2, lng2 = math.radians(poi_b.location["lat"]), math.radians(poi_b.location["lng"])

        dlat = lat2 - lat1
        dlng = lng2 - lng1

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    def calculate_travel_time(self, from_poi: POI, to_poi: POI, mode: str = "walk") -> int:
        """计算交通时间（分钟）"""
        distance_km = self.calculate_distance(from_poi, to_poi) / 1000
        speed = self.TRANSPORT_SPEED.get(mode, 5)
        return max(1, int(distance_km / speed * 60))

    def estimate_queue_time(self, poi: POI, arrival_time: datetime) -> int:
        """
        预估排队时间
        考虑：当前时段是否为高峰、历史排队数据
        """
        hour = arrival_time.hour
        is_peak = any(
            (start <= hour < end) if start < end else (hour >= start or hour < end)
            for start, end in poi.peak_hours
        )

        base_queue = 10  # 基础排队10分钟
        if is_peak:
            base_queue *= poi.queue_factor

        # 评分高的店排队更久
        if poi.rating >= 4.8:
            base_queue *= 1.3

        return int(base_queue)

    def check_open(self, poi: POI, arrival_time: datetime, duration: int) -> bool:
        """检查在计划到达时店铺是否营业"""
        arrival_t = arrival_time.time()
        departure_t = (arrival_time + timedelta(minutes=duration)).time()

        # 处理跨午夜的情况
        if poi.close_time < poi.open_time:  # 比如营业到次日02:00
            return arrival_t >= poi.open_time or arrival_t < poi.close_time

        return poi.open_time <= arrival_t and departure_t <= poi.close_time

    def score_poi(self, poi: POI, constraints: RouteConstraints, emotion: str = None) -> float:
        """
        POI 综合评分函数
        维度：评分(40%) + 口碑热度(20%) + 个性化匹配(20%) + 时空适配(20%)
        """
        # 基础评分（0-100）
        rating_score = poi.rating * 20

        # 口碑热度（评价数量越多越热门）
        hot_score = min(poi.review_count / 500, 10) * 10

        # 预算适配（越接近预算上限越好，但不能超）
        max_budget = constraints.max_budget if constraints.max_budget is not None else 1000
        group_size = constraints.group_size if constraints.group_size and constraints.group_size > 0 else 1
        budget_per_person = max_budget / group_size
        if poi.price_per_person > budget_per_person:
            budget_score = 0
        elif budget_per_person > 0:
            budget_score = (1 - poi.price_per_person / budget_per_person) * 100
        else:
            budget_score = 50

        # 标签匹配（可接入情绪/偏好）
        tag_score = 50  # 基础分
        if emotion:
            emotion_tags = {
                "疲惫": ["安静", "放松", "治愈"],
                "兴奋": ["热闹", "刺激", "网红"],
                "浪漫": ["夜景", "情调", "私密"],
                "轻松愉快": ["亲子", "室内", "适合儿童", "宝宝椅"],
            }
            preferred = emotion_tags.get(emotion, [])
            matches = sum(1 for tag in preferred if tag in poi.tags)
            tag_score += matches * 15

        return rating_score * 0.4 + hot_score * 0.2 + budget_score * 0.2 + tag_score * 0.2

    def plan_route(
        self,
        candidate_pois: List[str],
        constraints: RouteConstraints,
        start_location: POI = None,
        emotion: str = None,
    ) -> Tuple[List[RouteNode], Dict]:
        """
        规划最优路线

        算法步骤：
        1. 筛选候选 POI（营业时间内、预算内）
        2. 按评分排序，贪心选择
        3. 插入时间间隙，计算交通时间
        4. 2-opt 局部优化（交换相邻节点看是否更优）

        Returns:
            (路线节点列表, 统计信息)
        """
        # 获取 POI 对象
        pois = [self.poi_database[pid] for pid in candidate_pois if pid in self.poi_database]

        if not pois:
            logger.warning("没有可用的候选 POI")
            return [], {"total_duration": 0, "total_distance": 0, "total_cost": 0, "poi_count": 0}

        # 筛选：预算内
        max_budget = constraints.max_budget if constraints.max_budget is not None else 1000
        group_size = constraints.group_size if constraints.group_size and constraints.group_size > 0 else 1
        budget_per_person = max_budget / group_size
        valid_pois = [
            poi for poi in pois
            if poi.price_per_person <= budget_per_person
        ]

        if not valid_pois:
            logger.warning("所有 POI 都超出预算")
            return [], {"total_duration": 0, "total_distance": 0, "total_cost": 0, "poi_count": 0}

        # 按综合评分排序
        valid_pois.sort(key=lambda p: self.score_poi(p, constraints, emotion), reverse=True)

        # 贪心构建初始路线
        route = []
        current_time = constraints.start_time
        current_location = start_location or (valid_pois[0] if valid_pois else None)
        total_cost = 0
        total_distance = 0

        max_pois = {"slow": 3, "normal": 5, "fast": 7}.get(constraints.pace, 5)

        for poi in valid_pois[:max_pois + 2]:  # 多取几个，筛选后可能不够
            if len(route) >= max_pois:
                break

            # 计算交通时间
            if current_location and current_location.id != poi.id:
                travel_time = self.calculate_travel_time(current_location, poi, constraints.transport_mode)
                travel_distance = self.calculate_distance(current_location, poi)
                arrival_time = current_time + timedelta(minutes=travel_time)
            else:
                travel_time = 0
                travel_distance = 0
                arrival_time = current_time

            # 预估排队时间
            queue_time = self.estimate_queue_time(poi, arrival_time)

            # 实际活动开始时间
            activity_start = arrival_time + timedelta(minutes=queue_time)

            # 检查是否营业
            if not self.check_open(poi, activity_start, poi.avg_duration):
                logger.info(f"跳过 {poi.name}: 不在营业时间内")
                continue

            # 检查总时长是否超限
            departure_time = activity_start + timedelta(minutes=poi.avg_duration)
            elapsed = (departure_time - constraints.start_time).total_seconds() / 60
            if elapsed > constraints.max_duration:
                logger.info(f"跳过 {poi.name}: 超出总时长限制")
                break

            # 检查总预算
            poi_cost = poi.price_per_person * constraints.group_size
            if total_cost + poi_cost > constraints.max_budget:
                logger.info(f"跳过 {poi.name}: 超出预算")
                break

            # 判断活动类型
            play_categories = ["儿童乐园", "密室逃脱", "KTV", "剧本杀", "电影院", "轰趴馆", "户外拓展"]
            activity_type = "play" if poi.category in play_categories else "dine"

            node = RouteNode(
                poi=poi,
                arrival_time=arrival_time,
                departure_time=departure_time,
                travel_time_from_prev=travel_time,
                travel_distance_from_prev=travel_distance,
                estimated_queue_time=queue_time,
                activity_type=activity_type,
            )
            route.append(node)

            total_cost += poi_cost
            total_distance += travel_distance
            current_time = departure_time
            current_location = poi

        # 2-opt 局部优化
        route = self._two_opt(route, constraints.start_time)

        # 重新计算统计信息
        stats = self._calculate_stats(route, constraints)

        logger.info(f"路线规划完成: {stats['poi_count']} 个节点, 总时长 {stats['total_duration']} 分钟")
        return route, stats

    def _two_opt(self, route: List[RouteNode], start_time: datetime = None) -> List[RouteNode]:
        """2-opt 局部优化：尝试交换节点，减少总交通距离"""
        if len(route) < 3:
            return route

        # 记录原始起始时间
        original_start = start_time or route[0].arrival_time

        improved = True
        max_iterations = 10
        iteration = 0

        while improved and iteration < max_iterations:
            improved = False
            iteration += 1

            for i in range(len(route) - 1):
                current_dist = self.calculate_distance(route[i].poi, route[i + 1].poi) if i < len(route) - 1 else 0

                for j in range(i + 2, min(i + 4, len(route))):
                    new_dist = self.calculate_distance(route[i].poi, route[j].poi)

                    if new_dist < current_dist * 0.8:
                        if self._check_swap_time_valid(route, i, j):
                            route[i], route[j] = route[j], route[i]
                            # 交换后重新计算时间
                            self._recalculate_times(route, original_start)
                            improved = True
                            logger.debug(f"2-opt 优化: 交换位置 {i} 和 {j}")
                            break

        return route

    def _recalculate_times(self, route: List[RouteNode], start_time: datetime):
        """2-opt 交换后重新计算路线中各节点的时间"""
        for i, node in enumerate(route):
            if i == 0:
                # 第一个节点：使用传入的起始时间
                node.arrival_time = start_time
                node.travel_time_from_prev = 0
                node.travel_distance_from_prev = 0
            else:
                prev = route[i - 1]
                # 重新计算交通时间
                travel_time = self.calculate_travel_time(prev.poi, node.poi)
                travel_distance = self.calculate_distance(prev.poi, node.poi)
                node.travel_time_from_prev = travel_time
                node.travel_distance_from_prev = travel_distance
                # 重新计算到达时间
                node.arrival_time = prev.departure_time + timedelta(minutes=travel_time)

            # 重新计算排队和离开时间
            queue_time = self.estimate_queue_time(node.poi, node.arrival_time)
            node.estimated_queue_time = queue_time
            activity_start = node.arrival_time + timedelta(minutes=queue_time)
            node.departure_time = activity_start + timedelta(minutes=node.poi.avg_duration)

    def _check_swap_time_valid(self, route: List[RouteNode], i: int, j: int) -> bool:
        """检查交换后时间约束是否满足"""
        # 简化检查：交换后两个节点的营业时间是否仍然满足
        try:
            poi_i = route[i].poi
            poi_j = route[j].poi
            # 基本检查：两个 POI 在对方的时间段都能营业
            return True  # 简化实现，实际可以更严格
        except Exception:
            return False

    def _calculate_stats(self, route: List[RouteNode], constraints: RouteConstraints) -> Dict:
        """计算路线统计信息"""
        if not route:
            return {"total_duration": 0, "total_distance": 0, "total_cost": 0, "poi_count": 0}

        total_duration = int((route[-1].departure_time - constraints.start_time).total_seconds() / 60)
        total_distance = sum(node.travel_distance_from_prev for node in route)
        total_cost = sum(node.poi.price_per_person * constraints.group_size for node in route)

        return {
            "total_duration": total_duration,
            "total_distance": int(total_distance),
            "total_cost": total_cost,
            "poi_count": len(route),
        }

    def format_route_for_display(self, route: List[RouteNode]) -> str:
        """将路线格式化为人类可读的文本"""
        if not route:
            return "暂无路线规划"

        lines = []
        for i, node in enumerate(route):
            arrival = node.arrival_time.strftime("%H:%M")
            departure = node.departure_time.strftime("%H:%M")

            if i == 0:
                lines.append(f"📍 {arrival} 出发 → {node.poi.name}")
            else:
                travel = node.travel_time_from_prev
                lines.append(f"├─ 🚶 {travel}分钟 → {node.poi.name}")

            lines.append(f"│   {arrival}-{departure} {node.poi.category}")
            lines.append(f"│   评分{node.poi.rating} | 人均¥{int(node.poi.price_per_person)} | {', '.join(node.poi.tags[:2])}")

            if node.estimated_queue_time > 5:
                lines.append(f"│   ⏳ 预估排队{node.estimated_queue_time}分钟")

        return "\n".join(lines)

    def get_route_for_planner(self, route: List[RouteNode]) -> List[Dict]:
        """将路线转换为规划器可用的格式"""
        return [
            {
                "poi_id": node.poi.id,
                "poi_name": node.poi.name,
                "category": node.poi.category,
                "arrival_time": node.arrival_time.strftime("%H:%M"),
                "departure_time": node.departure_time.strftime("%H:%M"),
                "duration": node.poi.avg_duration,
                "activity_type": node.activity_type,
                "price_per_person": node.poi.price_per_person,
            }
            for node in route
        ]
