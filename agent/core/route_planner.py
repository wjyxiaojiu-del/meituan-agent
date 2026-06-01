"""
多 POI 智能路线规划引擎
算法：贪心初始化 + 2-opt 局部优化
约束：营业时间、步行距离、游玩时长、排队预估
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time
import math
import random
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
    coupon_price: Optional[float] = None  # 团购价（None 表示无优惠）
    original_price: Optional[float] = None  # 原价（用于展示折扣）
    reviews: List[str] = field(default_factory=list)  # 典型用户评价
    # ---- Meituan capability surface (P5) ----
    # Tags drawn from the closed set: {"团购券", "闪送", "会员折扣", "秒杀", "积分", "扫码点餐", "免预约"}
    capability_tags: List[str] = field(default_factory=list)
    deal_label: Optional[str] = None  # e.g. "团购券 ¥158（省 ¥42）"


@dataclass
class RouteConstraints:
    """路线约束"""
    start_time: datetime
    max_duration: int  # 总时长上限（分钟）
    max_budget: float  # 总预算上限
    group_size: int = 2
    must_include: List[str] = field(default_factory=list)  # 必须包含的品类
    must_exclude: List[str] = field(default_factory=list)  # 排除的品类
    excluded_poi_ids: List[str] = field(default_factory=list)  # 黑名单 POI ID（用户表达过 dislike）
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

    def score_poi(self, poi: POI, constraints: RouteConstraints, emotion: str = None, seed: int = None) -> float:
        """
        POI 综合评分函数
        维度：评分(30%) + 口碑热度(15%) + 预算适配(15%) + 性价比(10%) + 标签匹配(15%) + 多样性扰动(15%)
        """
        # 基础评分（0-100）
        rating_score = poi.rating * 20

        # 口碑热度（评价数量越多越热门）
        hot_score = min(poi.review_count / 500, 10) * 10

        # 预算适配（越接近预算上限越好，但不能超）
        max_budget = constraints.max_budget if constraints.max_budget is not None else 1000
        group_size = constraints.group_size if constraints.group_size and constraints.group_size > 0 else 1
        budget_per_person = max_budget / group_size
        effective_price = poi.coupon_price if poi.coupon_price is not None else poi.price_per_person
        if effective_price > budget_per_person:
            budget_score = 0
        elif budget_per_person > 0:
            budget_score = (1 - effective_price / budget_per_person) * 100
        else:
            budget_score = 50

        # 性价比：有团购券的 POI 获得额外加分
        value_score = 50  # 基础分
        if poi.coupon_price is not None and poi.original_price is not None and poi.original_price > 0:
            discount = 1 - poi.coupon_price / poi.original_price
            value_score = 50 + discount * 100  # 折扣越大，分越高

        # 标签匹配（可接入情绪/偏好）
        tag_score = 50  # 基础分
        if emotion:
            emotion_tags = {
                "疲惫": ["安静", "放松", "治愈"],
                "兴奋": ["热闹", "刺激", "网红"],
                "浪漫": ["夜景", "情调", "私密"],
                "轻松愉快": ["亲子", "室内", "适合儿童", "宝宝椅"],
                "团队凝聚": ["团建", "KTV", "桌游", "台球", "投影", "团队合作", "会议"],
            }
            preferred = emotion_tags.get(emotion, [])
            matches = sum(1 for tag in preferred if tag in poi.tags)
            tag_score += matches * 15

        # 确定性扰动：基于 POI id 的 hash 产生伪随机值，同一批次结果一致
        hash_val = hash((poi.id, seed or 0)) % 1000 / 1000.0
        variety = hash_val * 30

        return (rating_score * 0.30 + hot_score * 0.15 + budget_score * 0.15
                + value_score * 0.10 + tag_score * 0.15 + variety * 0.15)

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

        # 筛选：预算内 + 不在黑名单 POI + 不在排除品类
        max_budget = constraints.max_budget if constraints.max_budget is not None else 1000
        group_size = constraints.group_size if constraints.group_size and constraints.group_size > 0 else 1
        budget_per_person = max_budget / group_size
        excluded_ids = set(constraints.excluded_poi_ids or [])
        excluded_cats = set(constraints.must_exclude or [])
        valid_pois = [
            poi for poi in pois
            if poi.price_per_person <= budget_per_person
            and poi.id not in excluded_ids
            and poi.category not in excluded_cats
        ]

        if not valid_pois:
            logger.warning("所有 POI 都超出预算")
            return [], {"total_duration": 0, "total_distance": 0, "total_cost": 0, "poi_count": 0}

        # 按综合评分排序
        valid_pois.sort(key=lambda p: self.score_poi(p, constraints, emotion), reverse=True)

        # 贪心构建初始路线（带品类多样性）
        route = []
        current_time = constraints.start_time
        current_location = start_location or (valid_pois[0] if valid_pois else None)
        total_cost = 0
        total_distance = 0
        used_categories = set()

        max_pois = {"slow": 4, "normal": 6, "fast": 8}.get(constraints.pace, 6)

        # 候选池：每个品类从 top-2 中随机选 1 个，保证多样性 + 变化感
        def _best_per_category(pois_list, categories=None):
            """从候选列表中每个品类随机选 1 个（top-2 候选）"""
            by_cat = {}
            for p in pois_list:
                cat = p.category
                if categories and cat not in categories:
                    continue
                by_cat.setdefault(cat, []).append(p)
            result = {}
            for cat, pois in by_cat.items():
                scored = [(self.score_poi(p, constraints, emotion), p) for p in pois]
                scored.sort(key=lambda x: x[0], reverse=True)
                top = scored[:3]
                result[cat] = random.choice(top)[1] if len(top) > 1 else top[0][1]
            return list(result.values())

        # 优先安排 must_include 品类（每个品类选最优的 1 个）
        must_pool = _best_per_category(valid_pois, set(constraints.must_include))
        other_pool = _best_per_category(valid_pois)
        # 去掉已选的 must_include 品类
        must_cats = {p.category for p in must_pool}
        other_pool = [p for p in other_pool if p.category not in must_cats]
        # must_include 按关门时间排序（早关门的优先安排）
        must_pool.sort(key=lambda p: p.close_time)
        # 其他按评分排序
        other_pool.sort(key=lambda p: self.score_poi(p, constraints, emotion), reverse=True)
        candidates_pool = must_pool + other_pool

        for poi in candidates_pool:
            if len(route) >= max_pois:
                break

            # 品类去重：每个品类最多 1 个
            if poi.category in used_categories:
                continue

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

            # 检查总时长是否超限（跳过这个 POI，继续尝试更短的）
            departure_time = activity_start + timedelta(minutes=poi.avg_duration)
            elapsed = (departure_time - constraints.start_time).total_seconds() / 60
            if elapsed > constraints.max_duration:
                logger.info(f"跳过 {poi.name}: 超出总时长限制")
                continue

            # 检查总预算（跳过这个 POI，继续尝试更便宜的）
            poi_cost = poi.price_per_person * constraints.group_size
            if total_cost + poi_cost > constraints.max_budget:
                logger.info(f"跳过 {poi.name}: 超出预算")
                continue

            # 判断活动类型
            play_categories = ["儿童乐园", "密室逃脱", "KTV", "剧本杀", "电影院", "轰趴馆", "户外拓展",
                               "桌游", "电竞馆", "射箭", "保龄球", "陶艺", "猫咖", "VR体验", "台球",
                               "水族馆", "动物园", "健身房", "博物馆", "公园", "书店"]
            rest_categories = ["酒店"]
            if poi.category in rest_categories:
                activity_type = "rest"
            elif poi.category in play_categories:
                activity_type = "play"
            else:
                activity_type = "dine"

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
            used_categories.add(poi.category)

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
        max_iterations = 15
        iteration = 0

        while improved and iteration < max_iterations:
            improved = False
            iteration += 1

            for i in range(len(route) - 1):
                current_dist = self.calculate_distance(route[i].poi, route[i + 1].poi) if i < len(route) - 1 else 0

                for j in range(i + 2, min(i + 6, len(route))):
                    new_dist = self.calculate_distance(route[i].poi, route[j].poi)

                    if new_dist < current_dist * 0.9:
                        if self._check_swap_time_valid(route, i, j, original_start):
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

    def _check_swap_time_valid(self, route: List[RouteNode], i: int, j: int, start_time: datetime = None) -> bool:
        """检查交换后时间约束是否满足：模拟交换并校验营业时间窗口"""
        try:
            # 模拟交换：创建临时路线副本
            temp = list(route)
            temp[i], temp[j] = temp[j], temp[i]

            # 从交换点开始重新计算时间
            base_time = start_time or route[0].arrival_time
            if i > 0:
                base_time = route[i - 1].departure_time + timedelta(minutes=self.calculate_travel_time(route[i - 1].poi, temp[i].poi))

            for k in range(i, min(j + 1, len(temp))):
                node = temp[k]
                poi = node.poi

                if k == i:
                    arrival = base_time
                else:
                    prev = temp[k - 1]
                    travel = self.calculate_travel_time(prev.poi, poi)
                    arrival = prev.departure_time + timedelta(minutes=travel)

                # 检查是否在营业时间内
                arrival_t = arrival.time()
                departure_t = (arrival + timedelta(minutes=poi.avg_duration)).time()

                if poi.close_time < poi.open_time:
                    # 跨午夜营业
                    if not (arrival_t >= poi.open_time or arrival_t < poi.close_time):
                        return False
                else:
                    if not (poi.open_time <= arrival_t and departure_t <= poi.close_time):
                        return False

                # 更新 departure 供下一个节点使用
                queue_time = self.estimate_queue_time(poi, arrival)
                temp[k].arrival_time = arrival
                temp[k].estimated_queue_time = queue_time
                temp[k].departure_time = arrival + timedelta(minutes=queue_time + poi.avg_duration)

            return True
        except Exception:
            return False

    def _calculate_stats(self, route: List[RouteNode], constraints: RouteConstraints) -> Dict:
        """计算路线统计信息"""
        if not route:
            return {"total_duration": 0, "total_distance": 0, "total_cost": 0, "poi_count": 0,
                    "walking_distance": 0, "total_savings": 0}

        total_duration = int((route[-1].departure_time - constraints.start_time).total_seconds() / 60)
        total_distance = sum(node.travel_distance_from_prev for node in route)
        total_cost = sum(node.poi.price_per_person * constraints.group_size for node in route)

        # 步行距离（距离<2km的算步行）
        walking_distance = sum(
            node.travel_distance_from_prev
            for node in route
            if node.travel_distance_from_prev <= 2000
        )

        # 团购节省金额
        total_savings = 0
        for node in route:
            if node.poi.coupon_price and node.poi.original_price:
                total_savings += (node.poi.original_price - node.poi.coupon_price) * constraints.group_size

        return {
            "total_duration": total_duration,
            "total_distance": int(total_distance),
            "total_cost": total_cost,
            "poi_count": len(route),
            "walking_distance": int(walking_distance),
            "total_savings": int(total_savings),
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

    def _get_transport_info(self, distance_m: float) -> Tuple[str, str]:
        """根据距离智能选择交通方式，返回 (mode, description)"""
        if distance_m <= 0:
            return "walk", ""
        if distance_m <= 800:
            mins = max(1, int(distance_m / 80))
            return "walk", f"步行约{mins}分钟({int(distance_m)}m)"
        elif distance_m <= 2000:
            mins = max(2, int(distance_m / 200))
            return "walk", f"步行约{mins}分钟({int(distance_m)}m)"
        elif distance_m <= 5000:
            mins = max(5, int(distance_m / 500))
            cost = max(5, int(distance_m / 1000 * 3 + 5))
            return "bike", f"骑行约{mins}分钟({(distance_m/1000):.1f}km)或打车约¥{cost}"
        else:
            mins = max(10, int(distance_m / 600))
            cost = max(15, int(distance_m / 1000 * 3 + 13))
            return "taxi", f"打车约{mins}分钟({(distance_m/1000):.1f}km,约¥{cost})"

    def _get_activity_desc(self, poi: POI) -> str:
        """生成站点活动描述"""
        descs = {
            "儿童乐园": f"带孩子在{poi.name}尽情玩耍，体验各种游乐设施",
            "餐厅": f"在{poi.name}享用美食，推荐提前预订避免排队",
            "咖啡馆": f"在{poi.name}点一杯招牌饮品，享受悠闲时光",
            "书店": f"在{poi.name}逛逛书架，找一本心仪的书坐下来阅读",
            "博物馆": f"参观{poi.name}，感受文化与历史的魅力",
            "公园": f"在{poi.name}散步休闲，呼吸新鲜空气",
            "KTV": f"在{poi.name}尽情欢唱，释放压力",
            "密室逃脱": f"在{poi.name}挑战解谜，考验团队默契",
            "剧本杀": f"在{poi.name}沉浸式体验剧情，扮演角色解谜",
            "电影院": f"在{poi.name}看一场电影，享受视听盛宴",
            "轰趴馆": f"在{poi.name}尽情玩耍，KTV、桌游、台球一应俱全",
            "花店": f"在{poi.name}挑选一束鲜花，制造浪漫惊喜",
            "甜品店": f"在{poi.name}品尝招牌甜品，补充能量",
            "小吃街": f"逛{poi.name}，品尝各种地道小吃",
            "SPA": f"在{poi.name}享受专业按摩放松，舒缓身心",
            "步行街": f"漫步{poi.name}，感受城市繁华与夜景",
            "桌游": f"在{poi.name}玩桌游，和朋友一起享受欢乐时光",
            "电竞馆": f"在{poi.name}开黑打游戏，体验高配设备",
            "射箭": f"在{poi.name}体验射箭运动，教练现场指导",
            "保龄球": f"在{poi.name}打保龄球，适合朋友聚会",
            "陶艺": f"在{poi.name}亲手制作陶艺作品，体验手作乐趣",
            "猫咖": f"在{poi.name}边喝咖啡边撸猫，治愈身心",
            "VR体验": f"在{poi.name}体验虚拟现实，沉浸式冒险",
            "台球": f"在{poi.name}打台球，休闲娱乐好去处",
            "健身房": f"在{poi.name}上一节团课，挥洒汗水",
            "水族馆": f"参观{poi.name}，近距离观赏海洋生物",
            "动物园": f"游览{poi.name}，观赏各种珍稀动物",
            "酒店": f"入住{poi.name}，休息放松为明天充电",
        }
        return descs.get(poi.category, f"在{poi.name}享受美好时光")

    def _get_tips(self, poi: POI) -> str:
        """生成实用贴士"""
        tips_map = {
            "儿童乐园": "建议带水和小零食，注意看管好孩子",
            "餐厅": "热门时段建议提前30分钟取号",
            "咖啡馆": "下午2-4点人较少，适合拍照",
            "书店": "周末下午人较多，工作日更安静",
            "博物馆": "建议提前在官网预约门票",
            "公园": "注意防晒，建议穿舒适的鞋子",
            "KTV": "下午场价格更优惠，建议提前预约包间",
            "密室逃脱": "建议4-6人组队，提前10分钟到场",
            "剧本杀": "提前选好剧本，全程约2-3小时",
            "电影院": "建议提前在APP上选座购票",
            "花店": "可以提前电话预订，到店自取",
            "甜品店": "招牌款容易售罄，建议早去",
            "小吃街": "现金和手机支付都支持，注意保管财物",
            "SPA": "建议提前预约，到店后先泡再按",
            "酒店": "建议提前在美团预订，到店出示订单即可",
        }
        return tips_map.get(poi.category, "")

    def _get_highlights(self, poi: POI) -> List[str]:
        """生成亮点标签"""
        hl = []
        if poi.rating >= 4.7:
            hl.append("高评分")
        if poi.coupon_price and poi.original_price and poi.coupon_price < poi.original_price:
            discount = int((1 - poi.coupon_price / poi.original_price) * 100)
            if discount >= 15:
                hl.append(f"省{discount}%")
        if poi.review_count >= 3000:
            hl.append("热门")
        # 基于 tags 的亮点
        hot_tags = ["网红", "打卡", "拍照", "亲子", "浪漫", "约会", "沉浸式", "新手友好"]
        for t in poi.tags:
            if t in hot_tags:
                hl.append(t)
        return hl[:4]  # 最多4个

    def get_route_for_planner(self, route: List[RouteNode]) -> List[Dict]:
        """将路线转换为规划器可用的格式（增强版）"""
        result = []
        for i, node in enumerate(route):
            # 交通方式
            transport_mode, transport_desc = self._get_transport_info(node.travel_distance_from_prev)

            result.append({
                "poi_id": node.poi.id,
                "poi_name": node.poi.name,
                "category": node.poi.category,
                "arrival_time": node.arrival_time.strftime("%H:%M"),
                "departure_time": node.departure_time.strftime("%H:%M"),
                "duration": node.poi.avg_duration,
                "activity_type": node.activity_type,
                "price_per_person": node.poi.price_per_person,
                "coupon_price": node.poi.coupon_price,
                "original_price": node.poi.original_price,
                "location": node.poi.location,
                "travel_time_from_prev": node.travel_time_from_prev,
                "travel_distance_from_prev": node.travel_distance_from_prev,
                "transport_mode": transport_mode,
                "transport_desc": transport_desc,
                "activity_desc": self._get_activity_desc(node.poi),
                "tips": self._get_tips(node.poi),
                "highlights": self._get_highlights(node.poi),
                "rating": node.poi.rating,
                "review_count": node.poi.review_count,
                "address": node.poi.address,
            })
        return result
