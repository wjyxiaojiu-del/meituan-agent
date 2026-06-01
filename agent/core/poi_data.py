"""
POI Mock 数据
覆盖 16+ 品类，55+ 条数据
美团特色：团购券、用户评价、真实地址
"""

import functools
from datetime import time
from .route_planner import POI


# Closed capability vocabulary (P5 — Meituan flavor surface)
CAPABILITY_VOCAB = {"团购券", "闪送", "会员折扣", "秒杀", "积分", "扫码点餐", "免预约"}

# Category → extra capabilities (beyond the coupon-driven ones)
_CATEGORY_CAPS = {
    "餐厅": ["扫码点餐"],
    "咖啡馆": ["扫码点餐"],
    "甜品店": ["扫码点餐", "闪送"],
    "小吃街": ["扫码点餐"],
    "花店": ["闪送"],
    "书店": ["闪送"],
    "酒店": ["会员折扣", "免预约"],
    "SPA": ["会员折扣"],
    "健身房": ["会员折扣"],
    "KTV": ["免预约"],
    "电影院": ["免预约"],
    "密室逃脱": ["免预约"],
    "剧本杀": ["免预约"],
    "桌游": ["免预约"],
    "电竞馆": ["免预约"],
    "VR体验": ["免预约"],
}


def _derive_capabilities(poi: POI) -> tuple[list, str | None]:
    """Infer (capability_tags, deal_label) from category + coupon pricing.

    Keeps mock data terse — single source of truth for capability mapping.
    """
    caps: list = []
    deal_label = None
    if poi.coupon_price and poi.original_price and poi.coupon_price < poi.original_price:
        caps.append("团购券")
        caps.append("积分")
        saved = int(poi.original_price - poi.coupon_price)
        deal_label = f"团购券 ¥{int(poi.coupon_price)}（省 ¥{saved}）"
    for cap in _CATEGORY_CAPS.get(poi.category, []):
        if cap not in caps:
            caps.append(cap)
    return caps, deal_label


def _t(s: str) -> time:
    """字符串转 time 对象，支持 'HH:MM' 和 'HH:MM:SS' 格式"""
    parts = s.split(":")
    h, m = int(parts[0]), int(parts[1])
    if h >= 24:
        h, m = 23, 59
    return time(h, m)


@functools.lru_cache(maxsize=1)
def load_all_pois() -> list:
    """加载所有 Mock POI 数据（结果已缓存，首次调用后不再重复构建）"""
    pois = []

    # ===== 亲子/家庭 =====
    pois.extend([
        POI(
            id="kids_001", name="奇乐儿儿童主题乐园", category="儿童乐园",
            rating=4.8, review_count=2300,
            location={"lat": 31.2304, "lng": 121.4737}, address="万达广场3楼",
            open_time=_t("10:00"), close_time=_t("21:00"), avg_duration=90,
            price_per_person=128, tags=["室内", "适合3-8岁", "有家长休息区", "防滑地板"],
            peak_hours=[(14, 16), (19, 21)], queue_factor=1.5, capacity=100,
            suitable_scenes=["family", "parent_child"],
            coupon_price=98, original_price=128,
            reviews=["孩子玩了2小时不肯走", "环境很干净，工作人员态度好", "周末人有点多，建议工作日去"],
        ),
        POI(
            id="kids_002", name="Meland Club", category="儿童乐园",
            rating=4.9, review_count=1800,
            location={"lat": 31.2320, "lng": 121.4750}, address="万象城2楼",
            open_time=_t("10:00"), close_time=_t("22:00"), avg_duration=90,
            price_per_person=198, tags=["室内", "适合2-10岁", "沉浸式体验", "拍照好看"],
            peak_hours=[(10, 12), (14, 17)], queue_factor=2.0, capacity=80,
            suitable_scenes=["family", "parent_child"],
            coupon_price=168, original_price=198,
            reviews=["颜值超高，拍照绝了", "价格小贵但值得", "遛娃天花板"],
        ),
        POI(
            id="kids_003", name="奈尔宝家庭中心", category="儿童乐园",
            rating=4.7, review_count=3200,
            location={"lat": 31.2350, "lng": 121.4780}, address="南翔印象城3楼",
            open_time=_t("10:00"), close_time=_t("21:30"), avg_duration=75,
            price_per_person=168, tags=["室内", "适合2-12岁", "绘本区", "手工DIY"],
            peak_hours=[(10, 12), (14, 17)], queue_factor=1.8, capacity=120,
            suitable_scenes=["family", "parent_child"],
            reviews=["绘本区很安静，适合小龄宝宝", "手工区要额外收费", "整体体验不错"],
        ),
    ])

    # ===== 餐饮 =====
    pois.extend([
        POI(
            id="rest_001", name="新元素餐厅", category="餐厅",
            rating=4.7, review_count=3100,
            location={"lat": 31.2310, "lng": 121.4740}, address="万达广场4楼",
            open_time=_t("11:00"), close_time=_t("22:00"), avg_duration=90,
            price_per_person=120, tags=["低卡", "轻食", "沙拉", "适合减肥", "宝宝椅", "浪漫", "约会", "西餐"],
            peak_hours=[(12, 14), (18, 20)], queue_factor=1.3, capacity=60,
            suitable_scenes=["family", "date"],
            coupon_price=99, original_price=120,
            reviews=["沙拉很新鲜，减肥党福音", "环境优雅适合约会", "服务态度很好"],
        ),
        POI(
            id="rest_002", name="海底捞火锅", category="餐厅",
            rating=4.6, review_count=5600,
            location={"lat": 31.2312, "lng": 121.4742}, address="万达广场5楼",
            open_time=_t("10:00"), close_time=_t("07:00"), avg_duration=90,
            price_per_person=150, tags=["火锅", "服务好", "有宝宝椅", "免费美甲", "聚会", "热闹", "惊喜"],
            peak_hours=[(18, 22), (23, 2)], queue_factor=2.5, capacity=100,
            suitable_scenes=["friends", "family"],
            coupon_price=128, original_price=150,
            reviews=["服务真的没话说", "等位时有小零食和美甲", "番茄锅底绝了"],
        ),
        POI(
            id="rest_003", name="wagas", category="餐厅",
            rating=4.5, review_count=1200,
            location={"lat": 31.2330, "lng": 121.4760}, address="万象城1楼",
            open_time=_t("08:00"), close_time=_t("21:00"), avg_duration=60,
            price_per_person=85, tags=["轻食", "低卡", "健康", "早餐", "办公友好", "约会", "浪漫"],
            peak_hours=[(8, 10), (12, 14)], queue_factor=1.2, capacity=40,
            suitable_scenes=["solo", "date"],
            reviews=["健身人士的食堂", "三明治和果汁都很棒", "适合一个人安静吃饭"],
        ),
        POI(
            id="rest_004", name="西贝莜面村", category="餐厅",
            rating=4.6, review_count=4200,
            location={"lat": 31.2308, "lng": 121.4735}, address="凯德晶萃广场3楼",
            open_time=_t("11:00"), close_time=_t("21:30"), avg_duration=90,
            price_per_person=110, tags=["西北菜", "亲子友好", "开放式厨房", "手工面食"],
            peak_hours=[(12, 14), (18, 20)], queue_factor=1.4, capacity=80,
            suitable_scenes=["family", "friends"],
            coupon_price=89, original_price=110,
            reviews=["莜面鱼鱼孩子超爱吃", "分量足，性价比高", "开放式厨房看着放心"],
        ),
        POI(
            id="rest_005", name="一兰拉面", category="餐厅",
            rating=4.7, review_count=2800,
            location={"lat": 31.2340, "lng": 121.4770}, address="南京东路步行街",
            open_time=_t("10:00"), close_time=_t("23:00"), avg_duration=45,
            price_per_person=75, tags=["日料", "拉面", "一人食", "快速"],
            peak_hours=[(12, 14), (18, 20)], queue_factor=2.0, capacity=30,
            suitable_scenes=["solo", "friends"],
            reviews=["豚骨汤底浓郁", "一人食的快乐", "排队半小时起步"],
        ),
        POI(
            id="rest_006", name="木屋烧烤", category="餐厅",
            rating=4.5, review_count=3500,
            location={"lat": 31.2355, "lng": 121.4785}, address="淮海中路",
            open_time=_t("16:00"), close_time=_t("02:00"), avg_duration=90,
            price_per_person=130, tags=["烧烤", "啤酒", "夜宵", "热闹"],
            peak_hours=[(18, 22)], queue_factor=1.8, capacity=80,
            suitable_scenes=["friends", "team_building"],
            coupon_price=108, original_price=130,
            reviews=["烤串配啤酒绝了", "适合朋友聚餐", "环境有点吵但氛围好"],
        ),
        POI(
            id="rest_007", name="素宿素食", category="餐厅",
            rating=4.6, review_count=800,
            location={"lat": 31.2325, "lng": 121.4755}, address="武康路",
            open_time=_t("11:00"), close_time=_t("21:00"), avg_duration=75,
            price_per_person=95, tags=["素食", "有机", "健康", "安静", "治愈", "浪漫", "约会"],
            peak_hours=[(12, 13)], queue_factor=1.0, capacity=30,
            suitable_scenes=["solo", "date"],
            reviews=["素食做得比肉还好吃", "环境很禅意", "适合约会"],
        ),
        POI(
            id="rest_008", name="外婆家", category="餐厅",
            rating=4.4, review_count=6800,
            location={"lat": 31.2315, "lng": 121.4745}, address="万达广场6楼",
            open_time=_t("11:00"), close_time=_t("21:00"), avg_duration=80,
            price_per_person=75, tags=["杭帮菜", "性价比高", "排队王", "宝宝椅"],
            peak_hours=[(11, 13), (17, 19)], queue_factor=2.2, capacity=120,
            suitable_scenes=["family", "friends"],
            coupon_price=59, original_price=75,
            reviews=["3块钱的麻婆豆腐yyds", "便宜又好吃", "排队1小时起步"],
        ),
    ])

    # ===== 娱乐 =====
    pois.extend([
        POI(
            id="escape_001", name="X先生密室", category="密室逃脱",
            rating=4.8, review_count=1500,
            location={"lat": 31.2340, "lng": 121.4770}, address="南京东路步行街",
            open_time=_t("10:00"), close_time=_t("23:00"), avg_duration=120,
            price_per_person=168, tags=["沉浸式", "真人NPC", "剧情向", "恐怖可选"],
            peak_hours=[(14, 17), (19, 22)], queue_factor=1.8, capacity=30,
            suitable_scenes=["friends", "team_building"],
            coupon_price=138, original_price=168,
            reviews=["NPC太敬业了，吓哭", "剧情很烧脑", "适合4-6人玩"],
        ),
        POI(
            id="escape_002", name="迷斯伍德密室", category="密室逃脱",
            rating=4.7, review_count=2100,
            location={"lat": 31.2360, "lng": 121.4790}, address="静安寺商圈",
            open_time=_t("10:00"), close_time=_t("24:00"), avg_duration=90,
            price_per_person=138, tags=["机械密室", "解谜", "适合新手", "团队合作"],
            peak_hours=[(14, 17), (19, 22)], queue_factor=1.5, capacity=24,
            suitable_scenes=["friends"],
            reviews=["机关设计很巧妙", "新手友好", "工作人员复盘很详细"],
        ),
        POI(
            id="ktv_001", name="纯K", category="KTV",
            rating=4.7, review_count=2800,
            location={"lat": 31.2350, "lng": 121.4780}, address="淮海中路",
            open_time=_t("12:00"), close_time=_t("06:00"), avg_duration=120,
            price_per_person=80, tags=["音响好", "小吃丰富", "大包间", "可带生日蛋糕"],
            peak_hours=[(19, 23)], queue_factor=2.0, capacity=50,
            suitable_scenes=["friends", "team_building"],
            coupon_price=58, original_price=80,
            reviews=["音响效果一流", "小吃拼盘很划算", "适合生日派对"],
        ),
        POI(
            id="cinema_001", name="万达影城IMAX", category="电影院",
            rating=4.5, review_count=6700,
            location={"lat": 31.2310, "lng": 121.4740}, address="万达广场6楼",
            open_time=_t("10:00"), close_time=_t("02:00"), avg_duration=120,
            price_per_person=80, tags=["IMAX", "杜比全景声", "情侣座", "爆米花套餐", "浪漫", "约会", "电影"],
            peak_hours=[(19, 22)], queue_factor=1.5, capacity=300,
            suitable_scenes=["date", "friends"],
            coupon_price=55, original_price=80,
            reviews=["IMAX效果震撼", "情侣座很私密", "爆米花套餐必点"],
        ),
        POI(
            id="script_001", name="迷雾剧本杀馆", category="剧本杀",
            rating=4.7, review_count=1100,
            location={"lat": 31.2410, "lng": 121.4630}, address="徐家汇",
            open_time=_t("12:00"), close_time=_t("24:00"), avg_duration=150,
            price_per_person=128, tags=["换装", "推理", "情感本", "恐怖本", "DM专业"],
            peak_hours=[(14, 17), (19, 22)], queue_factor=1.7, capacity=40,
            suitable_scenes=["friends"],
            reviews=["DM带本水平很高", "换装体验沉浸", "情感本哭了一桌"],
        ),
        POI(
            id="script_002", name="暗夜惊魂剧本馆", category="剧本杀",
            rating=4.7, review_count=890,
            location={"lat": 31.2220, "lng": 121.4680}, address="南京西路1789号",
            open_time=_t("13:00"), close_time=_t("23:30"), avg_duration=120,
            price_per_person=158, tags=["恐怖", "沉浸", "推理", "微恐", "惊悚"],
            peak_hours=[(14, 17), (19, 22)], queue_factor=1.3, capacity=30,
            suitable_scenes=["friends"],
            reviews=["真的被吓到了", "恐怖氛围拉满", "胆小慎入"],
        ),
        POI(
            id="script_003", name="时光慢递情感剧本馆", category="剧本杀",
            rating=4.9, review_count=650,
            location={"lat": 31.2350, "lng": 121.4820}, address="淮海中路999号",
            open_time=_t("12:00"), close_time=_t("22:00"), avg_duration=100,
            price_per_person=138, tags=["情感", "沉浸", "催泪", "治愈", "文艺"],
            peak_hours=[(14, 17), (19, 21)], queue_factor=1.1, capacity=24,
            suitable_scenes=["friends", "date"],
            reviews=["玩完哭了半小时", "剧情太感人了", "适合情侣一起玩"],
        ),
    ])

    # ===== 团建专用 =====
    pois.extend([
        POI(
            id="party_001", name="Party King 轰趴馆", category="轰趴馆",
            rating=4.6, review_count=890,
            location={"lat": 31.2360, "lng": 121.4790}, address="静安寺商圈",
            open_time=_t("10:00"), close_time=_t("24:00"), avg_duration=150,
            price_per_person=150, tags=["KTV", "桌游", "台球", "自助厨房", "投影"],
            peak_hours=[(14, 18), (19, 23)], queue_factor=1.5, capacity=50,
            equipment=["KTV", "桌游", "台球", "Switch", "投影", "自助厨房"],
            suitable_scenes=["team_building", "friends"],
            coupon_price=128, original_price=150,
            reviews=["团建首选", "设施齐全玩一天", "自助厨房可以自己做饭"],
        ),
        POI(
            id="meet_001", name="WeWork 联合办公", category="会议室",
            rating=4.5, review_count=600,
            location={"lat": 31.2370, "lng": 121.4800}, address="陆家嘴中心",
            open_time=_t("08:00"), close_time=_t("20:00"), avg_duration=120,
            price_per_person=80, tags=["商务", "投影", "白板", "高速WiFi", "咖啡"],
            peak_hours=[(9, 12), (14, 17)], queue_factor=1.0, capacity=30,
            equipment=["投影", "白板", "音响", "视频会议", "打印机"],
            suitable_scenes=["team_building"],
            reviews=["环境很专业", "WiFi速度快", "咖啡免费续杯"],
        ),
        POI(
            id="outdoor_001", name="勇者户外拓展基地", category="户外拓展",
            rating=4.7, review_count=450,
            location={"lat": 31.2100, "lng": 121.4500}, address="青浦区朱家角",
            open_time=_t("09:00"), close_time=_t("17:00"), avg_duration=180,
            price_per_person=200, tags=["攀岩", "真人CS", "烧烤", "篝火晚会", "团队合作"],
            peak_hours=[(10, 12), (14, 16)], queue_factor=1.3, capacity=100,
            suitable_scenes=["team_building"],
            reviews=["团建氛围拉满", "教练很专业", "篝火晚会太棒了"],
        ),
    ])

    # ===== 文化/休闲 =====
    pois.extend([
        POI(
            id="museum_001", name="上海自然博物馆", category="博物馆",
            rating=4.8, review_count=5600,
            location={"lat": 31.2380, "lng": 121.4600}, address="静安雕塑公园",
            open_time=_t("09:00"), close_time=_t("17:00"), avg_duration=90,
            price_per_person=30, tags=["亲子", "科普", "恐龙化石", "互动体验", "室内"],
            peak_hours=[(10, 12), (14, 16)], queue_factor=1.6, capacity=500,
            suitable_scenes=["family", "parent_child"],
            reviews=["恐龙展厅孩子超喜欢", "互动装置很多", "建议提前预约"],
        ),
        POI(
            id="book_001", name="钟书阁", category="书店",
            rating=4.7, review_count=2100,
            location={"lat": 31.2390, "lng": 121.4610}, address="泰晤士小镇",
            open_time=_t("10:00"), close_time=_t("21:00"), avg_duration=60,
            price_per_person=50, tags=["网红", "拍照", "安静", "咖啡", "阅读"],
            peak_hours=[(14, 17)], queue_factor=1.2, capacity=80,
            suitable_scenes=["solo", "date"],
            reviews=["最美书店不是浪得虚名", "拍照打卡圣地", "看书氛围很好"],
        ),
        POI(
            id="park_001", name="世纪公园", category="公园",
            rating=4.6, review_count=4300,
            location={"lat": 31.2150, "lng": 121.5400}, address="浦东新区",
            open_time=_t("06:00"), close_time=_t("18:00"), avg_duration=60,
            price_per_person=0, tags=["免费", "骑行", "野餐", "划船", "亲子", "跑步"],
            peak_hours=[(9, 11), (15, 17)], queue_factor=1.0, capacity=1000,
            suitable_scenes=["family", "date", "solo"],
            reviews=["免费遛娃好去处", "樱花季很美", "租个自行车骑一圈很舒服"],
        ),
    ])

    # ===== 花店/配送 =====
    pois.extend([
        POI(
            id="flower_001", name="花点时间", category="花店",
            rating=4.8, review_count=900,
            location={"lat": 31.2315, "lng": 121.4745}, address="万达广场1楼",
            open_time=_t("09:00"), close_time=_t("21:00"), avg_duration=20,
            price_per_person=150, tags=["鲜花", "即时配送", "定制花束", "生日", "浪漫", "惊喜", "约会", "求婚"],
            peak_hours=[(10, 12), (17, 19)], queue_factor=1.0, capacity=20,
            suitable_scenes=["date"],
            coupon_price=128, original_price=150,
            reviews=["花束包装精美", "配送准时", "女朋友很喜欢"],
        ),
        POI(
            id="flower_002", name="野兽派花店", category="花店",
            rating=4.7, review_count=420,
            location={"lat": 31.2280, "lng": 121.4750}, address="安福路322号",
            open_time=_t("10:00"), close_time=_t("21:00"), avg_duration=20,
            price_per_person=299, tags=["浪漫", "惊喜", "高端", "艺术"],
            peak_hours=[(10, 12), (17, 20)], queue_factor=1.0, capacity=15,
            suitable_scenes=["date"],
            reviews=["高端大气上档次", "送礼有面子", "价格偏贵但品质好"],
        ),
        POI(
            id="flower_003", name="花加FlowerPlus", category="花店",
            rating=4.5, review_count=380,
            location={"lat": 31.2190, "lng": 121.4620}, address="徐汇区天钥桥路",
            open_time=_t("09:00"), close_time=_t("20:00"), avg_duration=15,
            price_per_person=128, tags=["平价", "日常", "清新", "惊喜"],
            peak_hours=[(9, 11), (17, 19)], queue_factor=1.0, capacity=10,
            suitable_scenes=["date", "family"],
            reviews=["性价比高", "每周一花很治愈", "适合日常送"],
        ),
    ])

    # ===== 甜品店/奶茶店 =====
    pois.extend([
        POI(
            id="dessert_001", name="喜茶LAB店", category="甜品店",
            rating=4.6, review_count=1800,
            location={"lat": 31.2310, "lng": 121.4690}, address="新天地南里",
            open_time=_t("10:00"), close_time=_t("22:00"), avg_duration=30,
            price_per_person=38, tags=["奶茶", "甜品", "网红", "打卡", "约会"],
            peak_hours=[(14, 16), (19, 21)], queue_factor=1.5, capacity=50,
            suitable_scenes=["date", "friends", "family"],
            reviews=["多肉葡萄必点", "LAB店限定款好吃", "排队20分钟起步"],
        ),
        POI(
            id="dessert_002", name="Lady M 蛋糕精品店", category="甜品店",
            rating=4.8, review_count=960,
            location={"lat": 31.2250, "lng": 121.4770}, address="静安嘉里中心",
            open_time=_t("10:00"), close_time=_t("22:00"), avg_duration=40,
            price_per_person=88, tags=["蛋糕", "精致", "下午茶", "浪漫", "高端"],
            peak_hours=[(14, 17)], queue_factor=1.2, capacity=30,
            suitable_scenes=["date", "friends"],
            reviews=["千层蛋糕天花板", "环境优雅适合下午茶", "价格小贵但值得"],
        ),
        POI(
            id="dessert_003", name="Manner Coffee", category="甜品店",
            rating=4.5, review_count=2200,
            location={"lat": 31.2170, "lng": 121.4580}, address="徐汇区多店通用",
            open_time=_t("08:00"), close_time=_t("20:00"), avg_duration=20,
            price_per_person=25, tags=["咖啡", "平价", "日常", "外带"],
            peak_hours=[(8, 10), (14, 16)], queue_factor=1.0, capacity=20,
            suitable_scenes=["solo", "friends"],
            reviews=["15块钱的拿铁真香", "自带杯减5元", "打工人续命水"],
        ),
    ])

    # ===== 步行街/夜市 =====
    pois.extend([
        POI(
            id="nightmarket_001", name="南京路步行街", category="步行街",
            rating=4.4, review_count=3500,
            location={"lat": 31.2350, "lng": 121.4740}, address="南京东路",
            open_time=_t("00:00"), close_time=_t("23:59"), avg_duration=90,
            price_per_person=0, tags=["逛街", "夜景", "小吃", "热闹", "地标"],
            peak_hours=[(18, 22)], queue_factor=1.0, capacity=999,
            suitable_scenes=["friends", "family", "date"],
            reviews=["上海必打卡", "夜景很美", "人超级多"],
        ),
    ])

    # ===== 咖啡馆 =====
    pois.extend([
        POI(
            id="cafe_001", name="%Arabica", category="咖啡馆",
            rating=4.6, review_count=3400,
            location={"lat": 31.2400, "lng": 121.4620}, address="武康路",
            open_time=_t("08:00"), close_time=_t("20:00"), avg_duration=60,
            price_per_person=45, tags=["网红", "拍照", "手冲", "极简风", "街景", "浪漫", "约会"],
            peak_hours=[(10, 12), (14, 16)], queue_factor=1.8, capacity=30,
            suitable_scenes=["date", "solo"],
            reviews=["武康路最美咖啡馆", "西班牙拿铁必点", "拍照出片率高"],
        ),
        POI(
            id="cafe_002", name="星巴克臻选", category="咖啡馆",
            rating=4.5, review_count=4100,
            location={"lat": 31.2325, "lng": 121.4755}, address="南京西路",
            open_time=_t("07:00"), close_time=_t("23:00"), avg_duration=60,
            price_per_person=55, tags=["连锁", "稳定", "WiFi", "办公友好"],
            peak_hours=[(8, 10), (14, 16)], queue_factor=1.3, capacity=50,
            suitable_scenes=["solo", "friends"],
            reviews=["臻选店豆子品质好", "适合办公", "环境比普通星巴克好"],
        ),
    ])

    # ===== 小吃街 =====
    pois.extend([
        POI(
            id="snack_001", name="城隍庙小吃街", category="小吃街",
            rating=4.4, review_count=8900,
            location={"lat": 31.2250, "lng": 121.4900}, address="豫园商圈",
            open_time=_t("10:00"), close_time=_t("22:00"), avg_duration=90,
            price_per_person=60, tags=["老字号", "生煎", "小笼包", "蟹壳黄", "网红打卡"],
            peak_hours=[(12, 14), (18, 20)], queue_factor=2.2, capacity=200,
            suitable_scenes=["friends", "family"],
            reviews=["小笼包汤汁鲜美", "游客多但值得来", "南翔馒头店要排队"],
        ),
    ])

    # ===== SPA =====
    pois.extend([
        POI(
            id="spa_001", name="悦榕庄SPA", category="SPA",
            rating=4.8, review_count=1200,
            location={"lat": 31.2380, "lng": 121.4800}, address="外滩",
            open_time=_t("10:00"), close_time=_t("23:00"), avg_duration=60,
            price_per_person=388, tags=["放松", "治愈", "精油", "安静", "高端"],
            peak_hours=[(14, 17), (19, 21)], queue_factor=1.0, capacity=20,
            suitable_scenes=["date", "solo"],
            coupon_price=298, original_price=388,
            reviews=["做完整个人都放松了", "环境高端大气", "精油手法很专业"],
        ),
    ])

    # ===== 新品类：桌游/电竞 =====
    pois.extend([
        POI(
            id="boardgame_001", name="桌游吧·大冒险", category="桌游",
            rating=4.6, review_count=720,
            location={"lat": 31.2345, "lng": 121.4765}, address="淮海中路523号",
            open_time=_t("13:00"), close_time=_t("24:00"), avg_duration=120,
            price_per_person=58, tags=["桌游", "狼人杀", "剧本", "聚会", "新手友好"],
            peak_hours=[(14, 17), (19, 22)], queue_factor=1.2, capacity=40,
            suitable_scenes=["friends", "team_building"],
            coupon_price=45, original_price=58,
            reviews=["桌游种类超多", "店员会教规则", "适合朋友聚会"],
        ),
        POI(
            id="esports_001", name="电竞网咖·超神", category="电竞馆",
            rating=4.5, review_count=560,
            location={"lat": 31.2335, "lng": 121.4758}, address="徐家汇太平洋数码",
            open_time=_t("00:00"), close_time=_t("23:59"), avg_duration=120,
            price_per_person=35, tags=["电竞", "开黑", "高配电脑", "包间", "夜猫子"],
            peak_hours=[(19, 23)], queue_factor=1.0, capacity=80,
            suitable_scenes=["friends", "team_building"],
            reviews=["配置很高，吃鸡无压力", "包间隔音好", "通宵价格划算"],
        ),
    ])

    # ===== 新品类：射箭/保龄球 =====
    pois.extend([
        POI(
            id="archery_001", name="箭道射箭馆", category="射箭",
            rating=4.7, review_count=430,
            location={"lat": 31.2355, "lng": 121.4788}, address="静安寺愚园路",
            open_time=_t("10:00"), close_time=_t("22:00"), avg_duration=60,
            price_per_person=88, tags=["射箭", "解压", "新手教学", "拍照"],
            peak_hours=[(14, 17), (19, 21)], queue_factor=1.0, capacity=20,
            suitable_scenes=["friends", "date", "team_building"],
            coupon_price=68, original_price=88,
            reviews=["教练很耐心", "拍照很帅", "解压神器"],
        ),
        POI(
            id="bowling_001", name="保龄球馆·Strike", category="保龄球",
            rating=4.5, review_count=680,
            location={"lat": 31.2320, "lng": 121.4748}, address="虹口足球场",
            open_time=_t("10:00"), close_time=_t("23:00"), avg_duration=90,
            price_per_person=68, tags=["保龄球", "运动", "团建", "新手友好"],
            peak_hours=[(14, 17), (19, 22)], queue_factor=1.3, capacity=40,
            suitable_scenes=["friends", "team_building"],
            coupon_price=52, original_price=68,
            reviews=["环境干净设备新", "适合团建", "新手也能玩得开心"],
        ),
    ])

    # ===== 新品类：陶艺/手作 =====
    pois.extend([
        POI(
            id="pottery_001", name="陶语陶艺工坊", category="陶艺",
            rating=4.8, review_count=350,
            location={"lat": 31.2395, "lng": 121.4615}, address="田子坊内",
            open_time=_t("10:00"), close_time=_t("21:00"), avg_duration=90,
            price_per_person=128, tags=["陶艺", "手作", "约会", "文艺", "拍照"],
            peak_hours=[(14, 17)], queue_factor=1.0, capacity=15,
            suitable_scenes=["date", "friends"],
            coupon_price=99, original_price=128,
            reviews=["第一次做陶艺很有趣", "老师很耐心", "作品可以带走"],
        ),
    ])

    # ===== 新品类：猫咖/宠物 =====
    pois.extend([
        POI(
            id="catcafe_001", name="猫の天空之城", category="猫咖",
            rating=4.6, review_count=890,
            location={"lat": 31.2385, "lng": 121.4605}, address="泰晤士小镇",
            open_time=_t("10:00"), close_time=_t("21:00"), avg_duration=60,
            price_per_person=48, tags=["猫咖", "撸猫", "治愈", "拍照", "亲子"],
            peak_hours=[(14, 17)], queue_factor=1.2, capacity=25,
            suitable_scenes=["date", "friends", "family"],
            reviews=["猫咪都很亲人", "环境干净没异味", "适合猫奴"],
        ),
    ])

    # ===== 新品类：密室/逃脱（补充更多类型）=====
    pois.extend([
        POI(
            id="vr_001", name="VR 体验馆·未来空间", category="VR体验",
            rating=4.5, review_count=420,
            location={"lat": 31.2318, "lng": 121.4746}, address="万达广场B1",
            open_time=_t("10:00"), close_time=_t("22:00"), avg_duration=45,
            price_per_person=78, tags=["VR", "科技", "沉浸", "游戏", "新奇"],
            peak_hours=[(14, 17), (19, 21)], queue_factor=1.5, capacity=20,
            suitable_scenes=["friends", "date"],
            coupon_price=58, original_price=78,
            reviews=["VR过山车太刺激了", "设备很新", "适合科技爱好者"],
        ),
    ])

    # ===== 补充餐厅 =====
    pois.extend([
        POI(
            id="rest_009", name="鼎泰丰", category="餐厅",
            rating=4.8, review_count=4500,
            location={"lat": 31.2322, "lng": 121.4752}, address="新天地北里",
            open_time=_t("11:00"), close_time=_t("21:30"), avg_duration=60,
            price_per_person=130, tags=["小笼包", "台式", "精致", "排队王", "亲子友好"],
            peak_hours=[(11, 13), (17, 19)], queue_factor=2.5, capacity=80,
            suitable_scenes=["family", "date"],
            coupon_price=108, original_price=130,
            reviews=["小笼包汤汁鲜美", "蟹粉面必点", "服务一流"],
        ),
        POI(
            id="rest_010", name="泰廊 Thai Gallery", category="餐厅",
            rating=4.6, review_count=1800,
            location={"lat": 31.2345, "lng": 121.4775}, address="淮海中路",
            open_time=_t("11:30"), close_time=_t("22:00"), avg_duration=75,
            price_per_person=140, tags=["泰餐", "冬阴功", "咖喱", "约会", "异国风情"],
            peak_hours=[(12, 14), (18, 20)], queue_factor=1.3, capacity=50,
            suitable_scenes=["date", "friends"],
            reviews=["冬阴功汤很正宗", "环境有情调", "芒果糯米饭好吃"],
        ),
        POI(
            id="rest_011", name="潮汕牛肉火锅", category="餐厅",
            rating=4.7, review_count=3200,
            location={"lat": 31.2338, "lng": 121.4768}, address="打浦桥日月光",
            open_time=_t("11:00"), close_time=_t("22:00"), avg_duration=90,
            price_per_person=120, tags=["牛肉火锅", "鲜切", "沙茶酱", "聚餐"],
            peak_hours=[(12, 14), (18, 20)], queue_factor=1.8, capacity=60,
            suitable_scenes=["friends", "family"],
            coupon_price=99, original_price=120,
            reviews=["牛肉现切很新鲜", "沙茶酱绝了", "吊龙必点"],
        ),
        POI(
            id="rest_012", name="粤来记", category="餐厅",
            rating=4.5, review_count=2100,
            location={"lat": 31.2328, "lng": 121.4758}, address="南京西路",
            open_time=_t("07:00"), close_time=_t("22:00"), avg_duration=60,
            price_per_person=85, tags=["粤菜", "早茶", "虾饺", "烧鹅", "老字号"],
            peak_hours=[(7, 10), (12, 14)], queue_factor=1.5, capacity=100,
            suitable_scenes=["family", "friends"],
            reviews=["虾饺皇皮薄馅大", "早茶排队1小时", "烧鹅很正宗"],
        ),
    ])

    # ===== 补充咖啡馆 =====
    pois.extend([
        POI(
            id="cafe_003", name="Seesaw Coffee", category="咖啡馆",
            rating=4.6, review_count=1900,
            location={"lat": 31.2388, "lng": 121.4608}, address="愚园路",
            open_time=_t("08:00"), close_time=_t("20:00"), avg_duration=45,
            price_per_person=40, tags=["精品咖啡", "创意特调", "拍照", "文艺"],
            peak_hours=[(10, 12), (14, 16)], queue_factor=1.2, capacity=35,
            suitable_scenes=["solo", "date"],
            reviews=["创意特调很有意思", "环境适合办公", "豆子品质好"],
        ),
    ])

    # ===== 补充娱乐 =====
    pois.extend([
        POI(
            id="billiards_001", name="台球俱乐部·黑八", category="台球",
            rating=4.5, review_count=380,
            location={"lat": 31.2342, "lng": 121.4772}, address="淮海中路",
            open_time=_t("10:00"), close_time=_t("02:00"), avg_duration=90,
            price_per_person=45, tags=["台球", "斯诺克", "休闲", "朋友聚会"],
            peak_hours=[(14, 17), (19, 23)], queue_factor=1.0, capacity=30,
            suitable_scenes=["friends", "team_building"],
            reviews=["球台质量好", "环境干净", "适合朋友消遣"],
        ),
        POI(
            id="gym_001", name="超级猩猩健身", category="健身房",
            rating=4.7, review_count=2800,
            location={"lat": 31.2332, "lng": 121.4762}, address="iapm环贸",
            open_time=_t("07:00"), close_time=_t("23:00"), avg_duration=60,
            price_per_person=79, tags=["健身", "团课", "不办卡", "按次付费", "减肥"],
            peak_hours=[(12, 14), (18, 21)], queue_factor=1.0, capacity=40,
            suitable_scenes=["solo", "friends"],
            reviews=["不办卡按次付费太良心", "团课氛围好", "器械很新"],
        ),
    ])

    # ===== 补充亲子 =====
    pois.extend([
        POI(
            id="aquarium_001", name="上海海洋水族馆", category="水族馆",
            rating=4.7, review_count=5200,
            location={"lat": 31.2400, "lng": 121.4950}, address="陆家嘴环路",
            open_time=_t("09:00"), close_time=_t("18:00"), avg_duration=120,
            price_per_person=160, tags=["亲子", "海洋生物", "海底隧道", "科普", "室内"],
            peak_hours=[(10, 12), (14, 16)], queue_factor=1.8, capacity=500,
            suitable_scenes=["family", "parent_child"],
            coupon_price=138, original_price=160,
            reviews=["海底隧道很震撼", "孩子看鲨鱼看呆了", "建议避开周末"],
        ),
        POI(
            id="zoo_001", name="上海动物园", category="动物园",
            rating=4.6, review_count=6100,
            location={"lat": 31.1900, "lng": 121.3600}, address="虹桥路",
            open_time=_t("08:00"), close_time=_t("17:30"), avg_duration=150,
            price_per_person=40, tags=["亲子", "动物", "大熊猫", "户外", "科普"],
            peak_hours=[(9, 11), (14, 16)], queue_factor=1.3, capacity=2000,
            suitable_scenes=["family", "parent_child"],
            reviews=["大熊猫超可爱", "园区很大要穿舒服的鞋", "性价比很高"],
        ),
    ])

    # ===== 补充甜品/饮品 =====
    pois.extend([
        POI(
            id="dessert_004", name="奈雪的茶", category="甜品店",
            rating=4.4, review_count=3200,
            location={"lat": 31.2316, "lng": 121.4744}, address="万达广场1楼",
            open_time=_t("10:00"), close_time=_t("22:00"), avg_duration=25,
            price_per_person=32, tags=["奶茶", "欧包", "水果茶", "打卡"],
            peak_hours=[(14, 16), (19, 21)], queue_factor=1.3, capacity=40,
            suitable_scenes=["friends", "family"],
            reviews=["霸气芝士草莓必点", "欧包也很棒", "比喜茶排队少"],
        ),
    ])

    # ===== 酒店/住宿 =====
    pois.extend([
        POI(
            id="hotel_001", name="全季酒店(外滩店)", category="酒店",
            rating=4.5, review_count=3200,
            location={"lat": 31.2365, "lng": 121.4810}, address="黄浦区中山东一路",
            open_time=_t("00:00"), close_time=_t("23:59"), avg_duration=0,
            price_per_person=280, tags=["经济型", "干净", "地铁口", "外滩景观"],
            peak_hours=[], queue_factor=1.0, capacity=120,
            suitable_scenes=["family", "friends", "date", "solo"],
            coupon_price=238, original_price=280,
            reviews=["位置绝佳步行到外滩5分钟", "房间干净整洁", "性价比很高"],
        ),
        POI(
            id="hotel_002", name="亚朵酒店(南京路店)", category="酒店",
            rating=4.7, review_count=2800,
            location={"lat": 31.2345, "lng": 121.4750}, address="黄浦区南京东路",
            open_time=_t("00:00"), close_time=_t("23:59"), avg_duration=0,
            price_per_person=420, tags=["中端", "书香", "文艺", "免费洗衣", "夜宵"],
            peak_hours=[], queue_factor=1.0, capacity=150,
            suitable_scenes=["family", "friends", "date", "solo"],
            coupon_price=358, original_price=420,
            reviews=["大堂有免费咖啡和书吧", "床品舒适度很高", "深夜食堂的粥很好喝"],
        ),
        POI(
            id="hotel_003", name="桔子水晶(淮海路店)", category="酒店",
            rating=4.6, review_count=1900,
            location={"lat": 31.2340, "lng": 121.4765}, address="黄浦区淮海中路",
            open_time=_t("00:00"), close_time=_t("23:59"), avg_duration=0,
            price_per_person=380, tags=["设计感", "智能马桶", "蓝牙音箱", "潮流"],
            peak_hours=[], queue_factor=1.0, capacity=100,
            suitable_scenes=["date", "friends", "solo"],
            coupon_price=328, original_price=380,
            reviews=["房间设计感很强", "智能设备体验好", "适合年轻人"],
        ),
    ])

    # Enrich every POI with capability_tags + deal_label (P5 Meituan flavor).
    for poi in pois:
        if not poi.capability_tags:
            caps, label = _derive_capabilities(poi)
            poi.capability_tags = caps
            if label:
                poi.deal_label = label
    return pois
