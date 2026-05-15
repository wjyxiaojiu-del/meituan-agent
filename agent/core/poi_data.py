"""
POI Mock 数据
覆盖 15+ 品类，50+ 条数据
"""

from datetime import time
from .route_planner import POI


def _t(s: str) -> time:
    """字符串转 time 对象，支持 'HH:MM' 和 'HH:MM:SS' 格式"""
    parts = s.split(":")
    h, m = int(parts[0]), int(parts[1])
    # 24:00 等价于 23:59（Python time 不支持 24:00）
    if h >= 24:
        h, m = 23, 59
    return time(h, m)


def load_all_pois() -> list:
    """加载所有 Mock POI 数据"""
    pois = []

    # ===== 亲子/家庭 =====
    pois.extend([
        POI(
            id="kids_001", name="奇乐儿儿童主题乐园", category="儿童乐园",
            rating=4.8, review_count=2300,
            location={"lat": 31.2304, "lng": 121.4737}, address="万达广场3楼",
            open_time=_t("10:00"), close_time=_t("21:00"), avg_duration=150,
            price_per_person=128, tags=["室内", "适合3-8岁", "有家长休息区", "防滑地板"],
            peak_hours=[(14, 16), (19, 21)], queue_factor=1.5, capacity=100,
            suitable_scenes=["family", "parent_child"],
        ),
        POI(
            id="kids_002", name="Meland Club", category="儿童乐园",
            rating=4.9, review_count=1800,
            location={"lat": 31.2320, "lng": 121.4750}, address="万象城2楼",
            open_time=_t("10:00"), close_time=_t("22:00"), avg_duration=180,
            price_per_person=198, tags=["室内", "适合2-10岁", "沉浸式体验", "拍照好看"],
            peak_hours=[(10, 12), (14, 17)], queue_factor=2.0, capacity=80,
            suitable_scenes=["family", "parent_child"],
        ),
        POI(
            id="kids_003", name="奈尔宝家庭中心", category="儿童乐园",
            rating=4.7, review_count=3200,
            location={"lat": 31.2350, "lng": 121.4780}, address="南翔印象城3楼",
            open_time=_t("10:00"), close_time=_t("21:30"), avg_duration=200,
            price_per_person=168, tags=["室内", "适合2-12岁", "绘本区", "手工DIY"],
            peak_hours=[(10, 12), (14, 17)], queue_factor=1.8, capacity=120,
            suitable_scenes=["family", "parent_child"],
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
        ),
        POI(
            id="rest_002", name="海底捞火锅", category="餐厅",
            rating=4.6, review_count=5600,
            location={"lat": 31.2312, "lng": 121.4742}, address="万达广场5楼",
            open_time=_t("10:00"), close_time=_t("07:00"), avg_duration=120,
            price_per_person=150, tags=["火锅", "服务好", "有宝宝椅", "免费美甲", "聚会", "热闹", "惊喜"],
            peak_hours=[(18, 22), (23, 2)], queue_factor=2.5, capacity=100,
            suitable_scenes=["friends", "family"],
        ),
        POI(
            id="rest_003", name="wagas", category="餐厅",
            rating=4.5, review_count=1200,
            location={"lat": 31.2330, "lng": 121.4760}, address="万象城1楼",
            open_time=_t("08:00"), close_time=_t("21:00"), avg_duration=60,
            price_per_person=85, tags=["轻食", "低卡", "健康", "早餐", "办公友好", "约会", "浪漫"],
            peak_hours=[(8, 10), (12, 14)], queue_factor=1.2, capacity=40,
            suitable_scenes=["solo", "date"],
        ),
        POI(
            id="rest_004", name="西贝莜面村", category="餐厅",
            rating=4.6, review_count=4200,
            location={"lat": 31.2308, "lng": 121.4735}, address="凯德晶萃广场3楼",
            open_time=_t("11:00"), close_time=_t("21:30"), avg_duration=90,
            price_per_person=110, tags=["西北菜", "亲子友好", "开放式厨房", "手工面食"],
            peak_hours=[(12, 14), (18, 20)], queue_factor=1.4, capacity=80,
            suitable_scenes=["family", "friends"],
        ),
        POI(
            id="rest_005", name="一兰拉面", category="餐厅",
            rating=4.7, review_count=2800,
            location={"lat": 31.2340, "lng": 121.4770}, address="南京东路步行街",
            open_time=_t("10:00"), close_time=_t("23:00"), avg_duration=45,
            price_per_person=75, tags=["日料", "拉面", "一人食", "快速"],
            peak_hours=[(12, 14), (18, 20)], queue_factor=2.0, capacity=30,
            suitable_scenes=["solo", "friends"],
        ),
        POI(
            id="rest_006", name="木屋烧烤", category="餐厅",
            rating=4.5, review_count=3500,
            location={"lat": 31.2355, "lng": 121.4785}, address="淮海中路",
            open_time=_t("16:00"), close_time=_t("02:00"), avg_duration=120,
            price_per_person=130, tags=["烧烤", "啤酒", "夜宵", "热闹"],
            peak_hours=[(18, 22)], queue_factor=1.8, capacity=80,
            suitable_scenes=["friends", "team_building"],
        ),
        POI(
            id="rest_007", name="素宿素食", category="餐厅",
            rating=4.6, review_count=800,
            location={"lat": 31.2325, "lng": 121.4755}, address="武康路",
            open_time=_t("11:00"), close_time=_t("21:00"), avg_duration=75,
            price_per_person=95, tags=["素食", "有机", "健康", "安静", "治愈", "浪漫", "约会"],
            peak_hours=[(12, 13)], queue_factor=1.0, capacity=30,
            suitable_scenes=["solo", "date"],
        ),
        POI(
            id="rest_008", name="外婆家", category="餐厅",
            rating=4.4, review_count=6800,
            location={"lat": 31.2315, "lng": 121.4745}, address="万达广场6楼",
            open_time=_t("11:00"), close_time=_t("21:00"), avg_duration=80,
            price_per_person=75, tags=["杭帮菜", "性价比高", "排队王", "宝宝椅"],
            peak_hours=[(11, 13), (17, 19)], queue_factor=2.2, capacity=120,
            suitable_scenes=["family", "friends"],
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
        ),
        POI(
            id="escape_002", name="迷斯伍德密室", category="密室逃脱",
            rating=4.7, review_count=2100,
            location={"lat": 31.2360, "lng": 121.4790}, address="静安寺商圈",
            open_time=_t("10:00"), close_time=_t("24:00"), avg_duration=90,
            price_per_person=138, tags=["机械密室", "解谜", "适合新手", "团队合作"],
            peak_hours=[(14, 17), (19, 22)], queue_factor=1.5, capacity=24,
            suitable_scenes=["friends"],
        ),
        POI(
            id="ktv_001", name="纯K", category="KTV",
            rating=4.7, review_count=2800,
            location={"lat": 31.2350, "lng": 121.4780}, address="淮海中路",
            open_time=_t("12:00"), close_time=_t("06:00"), avg_duration=180,
            price_per_person=80, tags=["音响好", "小吃丰富", "大包间", "可带生日蛋糕"],
            peak_hours=[(19, 23)], queue_factor=2.0, capacity=50,
            suitable_scenes=["friends", "team_building"],
        ),
        POI(
            id="cinema_001", name="万达影城IMAX", category="电影院",
            rating=4.5, review_count=6700,
            location={"lat": 31.2310, "lng": 121.4740}, address="万达广场6楼",
            open_time=_t("10:00"), close_time=_t("02:00"), avg_duration=150,
            price_per_person=80, tags=["IMAX", "杜比全景声", "情侣座", "爆米花套餐", "浪漫", "约会", "电影"],
            peak_hours=[(19, 22)], queue_factor=1.5, capacity=300,
            suitable_scenes=["date", "friends"],
        ),
        POI(
            id="script_001", name="迷雾剧本杀馆", category="剧本杀",
            rating=4.7, review_count=1100,
            location={"lat": 31.2410, "lng": 121.4630}, address="徐家汇",
            open_time=_t("12:00"), close_time=_t("24:00"), avg_duration=240,
            price_per_person=128, tags=["换装", "推理", "情感本", "恐怖本", "DM专业"],
            peak_hours=[(14, 17), (19, 22)], queue_factor=1.7, capacity=40,
            suitable_scenes=["friends"],
        ),
    ])

    # ===== 团建专用 =====
    pois.extend([
        POI(
            id="party_001", name="Party King 轰趴馆", category="轰趴馆",
            rating=4.6, review_count=890,
            location={"lat": 31.2360, "lng": 121.4790}, address="静安寺商圈",
            open_time=_t("10:00"), close_time=_t("24:00"), avg_duration=300,
            price_per_person=150, tags=["KTV", "桌游", "台球", "自助厨房", "投影"],
            peak_hours=[(14, 18), (19, 23)], queue_factor=1.5, capacity=50,
            equipment=["KTV", "桌游", "台球", "Switch", "投影", "自助厨房"],
            suitable_scenes=["team_building", "friends"],
        ),
        POI(
            id="meet_001", name="WeWork 联合办公", category="会议室",
            rating=4.5, review_count=600,
            location={"lat": 31.2370, "lng": 121.4800}, address="陆家嘴中心",
            open_time=_t("08:00"), close_time=_t("20:00"), avg_duration=240,
            price_per_person=80, tags=["商务", "投影", "白板", "高速WiFi", "咖啡"],
            peak_hours=[(9, 12), (14, 17)], queue_factor=1.0, capacity=30,
            equipment=["投影", "白板", "音响", "视频会议", "打印机"],
            suitable_scenes=["team_building"],
        ),
        POI(
            id="outdoor_001", name="勇者户外拓展基地", category="户外拓展",
            rating=4.7, review_count=450,
            location={"lat": 31.2100, "lng": 121.4500}, address="青浦区朱家角",
            open_time=_t("09:00"), close_time=_t("17:00"), avg_duration=360,
            price_per_person=200, tags=["攀岩", "真人CS", "烧烤", "篝火晚会", "团队合作"],
            peak_hours=[(10, 12), (14, 16)], queue_factor=1.3, capacity=100,
            suitable_scenes=["team_building"],
        ),
    ])

    # ===== 文化/休闲 =====
    pois.extend([
        POI(
            id="museum_001", name="上海自然博物馆", category="博物馆",
            rating=4.8, review_count=5600,
            location={"lat": 31.2380, "lng": 121.4600}, address="静安雕塑公园",
            open_time=_t("09:00"), close_time=_t("17:00"), avg_duration=180,
            price_per_person=30, tags=["亲子", "科普", "恐龙化石", "互动体验", "室内"],
            peak_hours=[(10, 12), (14, 16)], queue_factor=1.6, capacity=500,
            suitable_scenes=["family", "parent_child"],
        ),
        POI(
            id="book_001", name="钟书阁", category="书店",
            rating=4.7, review_count=2100,
            location={"lat": 31.2390, "lng": 121.4610}, address="泰晤士小镇",
            open_time=_t("10:00"), close_time=_t("21:00"), avg_duration=120,
            price_per_person=50, tags=["网红", "拍照", "安静", "咖啡", "阅读"],
            peak_hours=[(14, 17)], queue_factor=1.2, capacity=80,
            suitable_scenes=["solo", "date"],
        ),
        POI(
            id="park_001", name="世纪公园", category="公园",
            rating=4.6, review_count=4300,
            location={"lat": 31.2150, "lng": 121.5400}, address="浦东新区",
            open_time=_t("06:00"), close_time=_t("18:00"), avg_duration=180,
            price_per_person=0, tags=["免费", "骑行", "野餐", "划船", "亲子", "跑步"],
            peak_hours=[(9, 11), (15, 17)], queue_factor=1.0, capacity=1000,
            suitable_scenes=["family", "date", "solo"],
        ),
    ])

    # ===== 其他 =====
    pois.extend([
        POI(
            id="flower_001", name="花点时间", category="花店",
            rating=4.8, review_count=900,
            location={"lat": 31.2315, "lng": 121.4745}, address="万达广场1楼",
            open_time=_t("09:00"), close_time=_t("21:00"), avg_duration=20,
            price_per_person=150, tags=["鲜花", "即时配送", "定制花束", "生日", "浪漫", "惊喜", "约会", "求婚"],
            peak_hours=[(10, 12), (17, 19)], queue_factor=1.0, capacity=20,
            suitable_scenes=["date"],
        ),
        POI(
            id="cafe_001", name="%Arabica", category="咖啡馆",
            rating=4.6, review_count=3400,
            location={"lat": 31.2400, "lng": 121.4620}, address="武康路",
            open_time=_t("08:00"), close_time=_t("20:00"), avg_duration=60,
            price_per_person=45, tags=["网红", "拍照", "手冲", "极简风", "街景", "浪漫", "约会"],
            peak_hours=[(10, 12), (14, 16)], queue_factor=1.8, capacity=30,
            suitable_scenes=["date", "solo"],
        ),
        POI(
            id="cafe_002", name="星巴克臻选", category="咖啡馆",
            rating=4.5, review_count=4100,
            location={"lat": 31.2325, "lng": 121.4755}, address="南京西路",
            open_time=_t("07:00"), close_time=_t("23:00"), avg_duration=60,
            price_per_person=55, tags=["连锁", "稳定", "WiFi", "办公友好"],
            peak_hours=[(8, 10), (14, 16)], queue_factor=1.3, capacity=50,
            suitable_scenes=["solo", "friends"],
        ),
        POI(
            id="snack_001", name="城隍庙小吃街", category="小吃街",
            rating=4.4, review_count=8900,
            location={"lat": 31.2250, "lng": 121.4900}, address="豫园商圈",
            open_time=_t("10:00"), close_time=_t("22:00"), avg_duration=90,
            price_per_person=60, tags=["老字号", "生煎", "小笼包", "蟹壳黄", "网红打卡"],
            peak_hours=[(12, 14), (18, 20)], queue_factor=2.2, capacity=200,
            suitable_scenes=["friends", "family"],
        ),
        POI(
            id="spa_001", name="悦榕庄SPA", category="SPA",
            rating=4.8, review_count=1200,
            location={"lat": 31.2380, "lng": 121.4800}, address="外滩",
            open_time=_t("10:00"), close_time=_t("23:00"), avg_duration=120,
            price_per_person=388, tags=["放松", "治愈", "精油", "安静", "高端"],
            peak_hours=[(14, 17), (19, 21)], queue_factor=1.0, capacity=20,
            suitable_scenes=["date", "solo"],
        ),
    ])

    # ===== 剧本杀（补充恐怖本、情感本） =====
    pois.extend([
        POI(
            id="script_002", name="暗夜惊魂剧本馆", category="剧本杀",
            rating=4.7, review_count=890,
            location={"lat": 31.2220, "lng": 121.4680}, address="南京西路1789号",
            open_time=_t("13:00"), close_time=_t("23:30"), avg_duration=180,
            price_per_person=158, tags=["恐怖", "沉浸", "推理", "微恐", "惊悚"],
            peak_hours=[(14, 17), (19, 22)], queue_factor=1.3, capacity=30,
            suitable_scenes=["friends"],
        ),
        POI(
            id="script_003", name="时光慢递情感剧本馆", category="剧本杀",
            rating=4.9, review_count=650,
            location={"lat": 31.2350, "lng": 121.4820}, address="淮海中路999号",
            open_time=_t("12:00"), close_time=_t("22:00"), avg_duration=150,
            price_per_person=138, tags=["情感", "沉浸", "催泪", "治愈", "文艺"],
            peak_hours=[(14, 17), (19, 21)], queue_factor=1.1, capacity=24,
            suitable_scenes=["friends", "date"],
        ),
    ])

    # ===== 花店（补充） =====
    pois.extend([
        POI(
            id="flower_002", name="野兽派花店", category="花店",
            rating=4.7, review_count=420,
            location={"lat": 31.2280, "lng": 121.4750}, address="安福路322号",
            open_time=_t("10:00"), close_time=_t("21:00"), avg_duration=20,
            price_per_person=299, tags=["浪漫", "惊喜", "高端", "艺术"],
            peak_hours=[(10, 12), (17, 20)], queue_factor=1.0, capacity=15,
            suitable_scenes=["date"],
        ),
        POI(
            id="flower_003", name="花加FlowerPlus", category="花店",
            rating=4.5, review_count=380,
            location={"lat": 31.2190, "lng": 121.4620}, address="徐汇区天钥桥路",
            open_time=_t("09:00"), close_time=_t("20:00"), avg_duration=15,
            price_per_person=128, tags=["平价", "日常", "清新", "惊喜"],
            peak_hours=[(9, 11), (17, 19)], queue_factor=1.0, capacity=10,
            suitable_scenes=["date", "family"],
        ),
    ])

    # ===== 甜品店/奶茶店（新品类） =====
    pois.extend([
        POI(
            id="dessert_001", name="喜茶LAB店", category="甜品店",
            rating=4.6, review_count=1800,
            location={"lat": 31.2310, "lng": 121.4690}, address="新天地南里",
            open_time=_t("10:00"), close_time=_t("22:00"), avg_duration=30,
            price_per_person=38, tags=["奶茶", "甜品", "网红", "打卡", "约会"],
            peak_hours=[(14, 16), (19, 21)], queue_factor=1.5, capacity=50,
            suitable_scenes=["date", "friends", "family"],
        ),
        POI(
            id="dessert_002", name="Lady M 蛋糕精品店", category="甜品店",
            rating=4.8, review_count=960,
            location={"lat": 31.2250, "lng": 121.4770}, address="静安嘉里中心",
            open_time=_t("10:00"), close_time=_t("22:00"), avg_duration=40,
            price_per_person=88, tags=["蛋糕", "精致", "下午茶", "浪漫", "高端"],
            peak_hours=[(14, 17)], queue_factor=1.2, capacity=30,
            suitable_scenes=["date", "friends"],
        ),
        POI(
            id="dessert_003", name="Manner Coffee", category="甜品店",
            rating=4.5, review_count=2200,
            location={"lat": 31.2170, "lng": 121.4580}, address="徐汇区多店通用",
            open_time=_t("08:00"), close_time=_t("20:00"), avg_duration=20,
            price_per_person=25, tags=["咖啡", "平价", "日常", "外带"],
            peak_hours=[(8, 10), (14, 16)], queue_factor=1.0, capacity=20,
            suitable_scenes=["solo", "friends"],
        ),
    ])

    # ===== 夜市/步行街（新品类） =====
    pois.extend([
        POI(
            id="nightmarket_001", name="南京路步行街", category="步行街",
            rating=4.4, review_count=3500,
            location={"lat": 31.2350, "lng": 121.4740}, address="南京东路",
            open_time=_t("00:00"), close_time=_t("23:59"), avg_duration=90,
            price_per_person=0, tags=["逛街", "夜景", "小吃", "热闹", "地标"],
            peak_hours=[(18, 22)], queue_factor=1.0, capacity=999,
            suitable_scenes=["friends", "family", "date"],
        ),
    ])

    return pois
