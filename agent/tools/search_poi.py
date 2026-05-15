"""
搜索兴趣点工具
模拟美团 POI 搜索 API
"""

from typing import Dict, Any
from .base import BaseTool, ToolResult


class SearchPOITool(BaseTool):
    """
    搜索兴趣点工具
    模拟美团搜索 API，返回符合条件的商户列表
    """

    name = "search_poi"
    description = "搜索附近的兴趣点（餐厅、娱乐场所、景点等）"
    parameters_schema = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "类别，如：餐厅、儿童乐园、电影院、密室逃脱"
            },
            "location": {
                "type": "string",
                "description": "位置，如：商场名称、商圈、地址"
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "关键词筛选，如：低卡、亲子、适合儿童"
            },
            "rating_min": {
                "type": "number",
                "description": "最低评分要求"
            },
            "distance_max": {
                "type": "number",
                "description": "最大距离（米）"
            }
        },
        "required": ["category"]
    }

    # Mock 数据（16 品类，50+ 条）
    MOCK_DATA = {
        # ===== 亲子/家庭 =====
        "儿童乐园": [
            {"id": "kids_001", "name": "奇乐儿儿童主题乐园", "category": "儿童乐园", "rating": 4.8,
             "address": "万达广场3楼", "distance": 120, "price_range": "88-168元",
             "features": ["室内", "适合3-8岁", "有家长休息区", "防滑地板"], "queue_count": 5, "open_time": "10:00-21:00"},
            {"id": "kids_002", "name": "Meland Club", "category": "儿童乐园", "rating": 4.9,
             "address": "万象城2楼", "distance": 350, "price_range": "128-258元",
             "features": ["室内", "适合2-10岁", "沉浸式体验", "拍照好看"], "queue_count": 12, "open_time": "10:00-22:00"},
            {"id": "kids_003", "name": "奈尔宝家庭中心", "category": "儿童乐园", "rating": 4.7,
             "address": "南翔印象城3楼", "distance": 800, "price_range": "128-198元",
             "features": ["室内", "适合2-12岁", "绘本区", "手工DIY"], "queue_count": 8, "open_time": "10:00-21:30"},
            {"id": "kids_004", "name": "Mini Mars 亲子乐园", "category": "儿童乐园", "rating": 4.6,
             "address": "虹桥天地2楼", "distance": 1200, "price_range": "138-228元",
             "features": ["室内", "适合1-8岁", "沙池", "角色扮演"], "queue_count": 6, "open_time": "10:00-21:00"},
            {"id": "kids_005", "name": "卡通尼乐园", "category": "儿童乐园", "rating": 4.5,
             "address": "大悦城3楼", "distance": 500, "price_range": "68-158元",
             "features": ["室内", "适合3-10岁", "电玩", "碰碰车"], "queue_count": 4, "open_time": "10:00-22:00"},
        ],
        # ===== 餐饮 =====
        "餐厅": [
            {"id": "rest_001", "name": "新元素餐厅", "category": "餐厅", "rating": 4.7,
             "address": "万达广场4楼", "distance": 150, "price_range": "人均120元",
             "features": ["低卡", "轻食", "沙拉", "适合减肥", "浪漫", "约会", "西餐", "宝宝椅"],
             "queue_count": 8, "open_time": "11:00-22:00"},
            {"id": "rest_002", "name": "海底捞火锅", "category": "餐厅", "rating": 4.6,
             "address": "万达广场5楼", "distance": 160, "price_range": "人均150元",
             "features": ["火锅", "有宝宝椅", "服务好", "聚会", "热闹", "惊喜"],
             "queue_count": 25, "open_time": "10:00-次日07:00"},
            {"id": "rest_003", "name": "wagas", "category": "餐厅", "rating": 4.5,
             "address": "万象城1楼", "distance": 320, "price_range": "人均90元",
             "features": ["轻食", "低卡", "健康", "沙拉", "约会", "浪漫"],
             "queue_count": 3, "open_time": "08:00-21:00"},
            {"id": "rest_004", "name": "西贝莜面村", "category": "餐厅", "rating": 4.6,
             "address": "凯德晶萃广场3楼", "distance": 280, "price_range": "人均110元",
             "features": ["西北菜", "亲子友好", "开放式厨房", "手工面食", "宝宝椅"],
             "queue_count": 12, "open_time": "11:00-21:30"},
            {"id": "rest_005", "name": "一兰拉面", "category": "餐厅", "rating": 4.7,
             "address": "南京东路步行街", "distance": 250, "price_range": "人均75元",
             "features": ["日料", "拉面", "一人食", "快速"],
             "queue_count": 18, "open_time": "10:00-23:00"},
            {"id": "rest_006", "name": "木屋烧烤", "category": "餐厅", "rating": 4.5,
             "address": "淮海中路", "distance": 400, "price_range": "人均130元",
             "features": ["烧烤", "啤酒", "夜宵", "热闹", "聚会"],
             "queue_count": 10, "open_time": "16:00-次日02:00"},
            {"id": "rest_007", "name": "素宿素食", "category": "餐厅", "rating": 4.6,
             "address": "武康路", "distance": 220, "price_range": "人均95元",
             "features": ["素食", "有机", "健康", "安静", "治愈", "浪漫", "约会"],
             "queue_count": 2, "open_time": "11:00-21:00"},
            {"id": "rest_008", "name": "外婆家", "category": "餐厅", "rating": 4.4,
             "address": "万达广场6楼", "distance": 155, "price_range": "人均75元",
             "features": ["杭帮菜", "性价比高", "排队王", "宝宝椅"],
             "queue_count": 30, "open_time": "11:00-21:00"},
            {"id": "rest_009", "name": "鼎泰丰", "category": "餐厅", "rating": 4.8,
             "address": "新天地", "distance": 350, "price_range": "人均160元",
             "features": ["小笼包", "台菜", "精致", "约会", "排队"],
             "queue_count": 20, "open_time": "11:00-21:30"},
            {"id": "rest_010", "name": "太二酸菜鱼", "category": "餐厅", "rating": 4.5,
             "address": "来福士广场4楼", "distance": 300, "price_range": "人均90元",
             "features": ["酸菜鱼", "川菜", "网红", "聚会"],
             "queue_count": 15, "open_time": "11:00-21:30"},
        ],
        # ===== 花店 =====
        "花店": [
            {"id": "flower_001", "name": "花点时间", "category": "花店", "rating": 4.8,
             "address": "万达广场1楼", "distance": 100, "price_range": "99-399元",
             "features": ["即时配送", "定时送达", "精美包装", "浪漫", "惊喜", "约会", "求婚"],
             "queue_count": 0, "open_time": "09:00-21:00"},
            {"id": "flower_002", "name": "野兽派", "category": "花店", "rating": 4.7,
             "address": "安福路", "distance": 280, "price_range": "199-999元",
             "features": ["高端", "设计师款", "永生花", "香氛", "浪漫", "礼物"],
             "queue_count": 2, "open_time": "10:00-21:00"},
            {"id": "flower_003", "name": "Roseonly", "category": "花店", "rating": 4.6,
             "address": "新天地", "distance": 350, "price_range": "299-1314元",
             "features": ["高端玫瑰", "一生只送一人", "求婚", "纪念日", "浪漫"],
             "queue_count": 1, "open_time": "10:00-21:00"},
        ],
        # ===== 电影院 =====
        "电影院": [
            {"id": "cinema_001", "name": "万达影城IMAX", "category": "电影院", "rating": 4.5,
             "address": "万达广场6楼", "distance": 150, "price_range": "60-120元",
             "features": ["IMAX", "杜比全景声", "情侣座", "浪漫", "约会", "爆米花套餐"],
             "queue_count": 15, "open_time": "10:00-02:00"},
            {"id": "cinema_002", "name": "百丽宫影城", "category": "电影院", "rating": 4.6,
             "address": "环贸iapm5楼", "distance": 350, "price_range": "80-150元",
             "features": ["杜比全景声", "VIP厅", "情侣座", "安静"],
             "queue_count": 8, "open_time": "10:00-01:00"},
            {"id": "cinema_003", "name": "CGV影城", "category": "电影院", "rating": 4.4,
             "address": "莘庄仲盛世界商城4楼", "distance": 600, "price_range": "45-90元",
             "features": ["4DX", "亲子厅", "性价比高", "停车方便"],
             "queue_count": 6, "open_time": "09:30-24:00"},
        ],
        # ===== 咖啡馆 =====
        "咖啡馆": [
            {"id": "cafe_001", "name": "%Arabica", "category": "咖啡馆", "rating": 4.6,
             "address": "武康路", "distance": 200, "price_range": "人均45元",
             "features": ["网红", "拍照", "手冲", "浪漫", "约会", "街景"],
             "queue_count": 8, "open_time": "08:00-20:00"},
            {"id": "cafe_002", "name": "星巴克臻选", "category": "咖啡馆", "rating": 4.5,
             "address": "南京西路", "distance": 180, "price_range": "人均55元",
             "features": ["连锁", "稳定", "WiFi", "办公友好"],
             "queue_count": 5, "open_time": "07:00-23:00"},
            {"id": "cafe_003", "name": "Manner Coffee", "category": "咖啡馆", "rating": 4.7,
             "address": "淮海中路", "distance": 250, "price_range": "人均25元",
             "features": ["性价比", "自带杯减5元", "快速", "好喝"],
             "queue_count": 3, "open_time": "08:00-20:00"},
        ],
        # ===== 密室逃脱 =====
        "密室逃脱": [
            {"id": "escape_001", "name": "X先生密室", "category": "密室逃脱", "rating": 4.8,
             "address": "南京东路步行街", "distance": 250, "price_range": "人均168元",
             "features": ["沉浸式", "真人NPC", "剧情向", "恐怖可选", "惊喜"],
             "queue_count": 6, "open_time": "10:00-23:00"},
            {"id": "escape_002", "name": "迷斯伍德密室", "category": "密室逃脱", "rating": 4.7,
             "address": "静安寺商圈", "distance": 380, "price_range": "人均138元",
             "features": ["机械密室", "解谜", "适合新手", "团队合作"],
             "queue_count": 4, "open_time": "10:00-24:00"},
            {"id": "escape_003", "name": "奥秘之家", "category": "密室逃脱", "rating": 4.6,
             "address": "人民广场", "distance": 450, "price_range": "人均128元",
             "features": ["剧情向", "多主题", "适合4-8人", "新手友好"],
             "queue_count": 3, "open_time": "10:00-22:30"},
        ],
        # ===== 剧本杀 =====
        "剧本杀": [
            {"id": "script_001", "name": "迷雾剧本杀馆", "category": "剧本杀", "rating": 4.7,
             "address": "徐家汇", "distance": 300, "price_range": "人均128元",
             "features": ["换装", "推理", "情感本", "恐怖本", "DM专业", "剧情向"],
             "queue_count": 4, "open_time": "12:00-24:00"},
            {"id": "script_002", "name": "戏精剧本杀", "category": "剧本杀", "rating": 4.5,
             "address": "五角场", "distance": 600, "price_range": "人均98元",
             "features": ["欢乐本", "新手友好", "换装", "拍照"],
             "queue_count": 2, "open_time": "13:00-24:00"},
            {"id": "script_003", "name": "叁千世界剧本杀", "category": "剧本杀", "rating": 4.6,
             "address": "虹口龙之梦", "distance": 450, "price_range": "人均108元",
             "features": ["沉浸式", "恐怖本", "情感本", "硬核推理", "专业DM"],
             "queue_count": 3, "open_time": "14:00-次日02:00"},
        ],
        # ===== KTV =====
        "KTV": [
            {"id": "ktv_001", "name": "纯K", "category": "KTV", "rating": 4.7,
             "address": "淮海中路", "distance": 300, "price_range": "人均80元",
             "features": ["音响好", "小吃丰富", "大包间", "可带生日蛋糕"],
             "queue_count": 10, "open_time": "12:00-次日06:00"},
            {"id": "ktv_002", "name": "唱吧麦颂", "category": "KTV", "rating": 4.4,
             "address": "中山公园", "distance": 450, "price_range": "人均60元",
             "features": ["性价比", "曲库全", "小包间", "零食多"],
             "queue_count": 5, "open_time": "12:00-次日06:00"},
            {"id": "ktv_003", "name": "好乐迪", "category": "KTV", "rating": 4.3,
             "address": "徐家汇", "distance": 350, "price_range": "人均70元",
             "features": ["连锁品牌", "音响好", "自助餐", "生日派对"],
             "queue_count": 8, "open_time": "11:00-次日06:00"},
        ],
        # ===== SPA =====
        "SPA": [
            {"id": "spa_001", "name": "悦榕庄SPA", "category": "SPA", "rating": 4.8,
             "address": "外滩", "distance": 500, "price_range": "人均388元",
             "features": ["放松", "治愈", "精油", "安静", "高端"],
             "queue_count": 1, "open_time": "10:00-23:00"},
            {"id": "spa_002", "name": "泰美好泰式按摩", "category": "SPA", "rating": 4.5,
             "address": "南京西路", "distance": 280, "price_range": "人均198元",
             "features": ["泰式", "放松", "肩颈", "性价比"],
             "queue_count": 3, "open_time": "11:00-次日01:00"},
            {"id": "spa_003", "name": "大桶大足道", "category": "SPA", "rating": 4.3,
             "address": "长寿路", "distance": 320, "price_range": "人均128元",
             "features": ["足疗", "肩颈", "性价比", "24小时", "中式"],
             "queue_count": 2, "open_time": "00:00-24:00"},
        ],
        # ===== 小吃街 =====
        "小吃街": [
            {"id": "snack_001", "name": "城隍庙小吃街", "category": "小吃街", "rating": 4.4,
             "address": "豫园商圈", "distance": 600, "price_range": "人均60元",
             "features": ["老字号", "生煎", "小笼包", "蟹壳黄", "网红打卡"],
             "queue_count": 20, "open_time": "10:00-22:00"},
            {"id": "snack_002", "name": "吴江路小吃街", "category": "小吃街", "rating": 4.3,
             "address": "吴江路", "distance": 200, "price_range": "人均50元",
             "features": ["网红", "奶茶", "烧烤", "臭豆腐", "逛吃"],
             "queue_count": 15, "open_time": "10:00-22:00"},
        ],
        # ===== 博物馆 =====
        "博物馆": [
            {"id": "museum_001", "name": "上海自然博物馆", "category": "博物馆", "rating": 4.8,
             "address": "静安雕塑公园", "distance": 400, "price_range": "30元",
             "features": ["亲子", "科普", "恐龙化石", "互动体验", "室内"],
             "queue_count": 10, "open_time": "09:00-17:00"},
            {"id": "museum_002", "name": "上海科技馆", "category": "博物馆", "rating": 4.7,
             "address": "浦东新区", "distance": 2000, "price_range": "45元",
             "features": ["亲子", "科技", "IMAX影院", "机器人", "适合5岁以上"],
             "queue_count": 8, "open_time": "09:00-17:15"},
        ],
        # ===== 书店 =====
        "书店": [
            {"id": "book_001", "name": "钟书阁", "category": "书店", "rating": 4.7,
             "address": "泰晤士小镇", "distance": 800, "price_range": "人均50元",
             "features": ["网红", "拍照", "安静", "咖啡", "阅读"],
             "queue_count": 5, "open_time": "10:00-21:00"},
            {"id": "book_002", "name": "西西弗书店", "category": "书店", "rating": 4.5,
             "address": "环球港B1", "distance": 350, "price_range": "人均40元",
             "features": ["连锁", "儿童区", "咖啡", "安静"],
             "queue_count": 2, "open_time": "10:00-22:00"},
        ],
        # ===== 公园 =====
        "公园": [
            {"id": "park_001", "name": "世纪公园", "category": "公园", "rating": 4.6,
             "address": "浦东新区", "distance": 2000, "price_range": "免费",
             "features": ["免费", "骑行", "野餐", "划船", "亲子", "跑步"],
             "queue_count": 0, "open_time": "06:00-18:00"},
            {"id": "park_002", "name": "静安雕塑公园", "category": "公园", "rating": 4.5,
             "address": "静安区", "distance": 380, "price_range": "免费",
             "features": ["免费", "雕塑", "拍照", "安静", "遛狗"],
             "queue_count": 0, "open_time": "00:00-24:00"},
        ],
        # ===== 轰趴馆 =====
        "轰趴馆": [
            {"id": "party_001", "name": "Party King 轰趴馆", "category": "轰趴馆", "rating": 4.6,
             "address": "静安寺商圈", "distance": 380, "price_range": "人均150元",
             "features": ["KTV", "桌游", "台球", "自助厨房", "投影"],
             "queue_count": 3, "open_time": "10:00-24:00"},
            {"id": "party_002", "name": "嘿店轰趴馆", "category": "轰趴馆", "rating": 4.4,
             "address": "徐家汇", "distance": 300, "price_range": "人均120元",
             "features": ["Switch", "桌游", "KTV", "火锅", "电影"],
             "queue_count": 2, "open_time": "10:00-24:00"},
        ],
        # ===== 会议室 =====
        "会议室": [
            {"id": "meet_001", "name": "WeWork 联合办公", "category": "会议室", "rating": 4.5,
             "address": "陆家嘴中心", "distance": 500, "price_range": "200元/小时",
             "features": ["投影", "白板", "高速WiFi", "咖啡", "商务"],
             "queue_count": 1, "open_time": "08:00-20:00"},
            {"id": "meet_002", "name": "氪空间", "category": "会议室", "rating": 4.4,
             "address": "南京西路", "distance": 280, "price_range": "150元/小时",
             "features": ["投影", "白板", "视频会议", "茶水"],
             "queue_count": 0, "open_time": "09:00-21:00"},
        ],
        # ===== 户外拓展 =====
        "户外拓展": [
            {"id": "outdoor_001", "name": "勇者户外拓展基地", "category": "户外拓展", "rating": 4.7,
             "address": "青浦区朱家角", "distance": 5000, "price_range": "人均200元",
             "features": ["攀岩", "真人CS", "烧烤", "篝火晚会", "团队合作"],
             "queue_count": 0, "open_time": "09:00-17:00"},
            {"id": "outdoor_002", "name": "橙果拓展", "category": "户外拓展", "rating": 4.5,
             "address": "松江区佘山", "distance": 3500, "price_range": "人均180元",
             "features": ["高空项目", "定向越野", "皮划艇", "团建定制"],
             "queue_count": 0, "open_time": "09:00-17:30"},
        ],
    }

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        category = params.get("category", "")
        keywords = params.get("keywords", [])
        rating_min = params.get("rating_min", 0)
        distance_max = params.get("distance_max", float("inf"))

        # 获取对应类别的数据
        results = self.MOCK_DATA.get(category, [])

        # 筛选
        filtered = []
        for item in results:
            # 评分筛选
            if item["rating"] < rating_min:
                continue

            # 距离筛选
            if item["distance"] > distance_max:
                continue

            # 关键词筛选（模糊匹配：关键词出现在名称、特征、地址中任意一项即可）
            if keywords:
                searchable = " ".join([
                    item.get("name", ""),
                    " ".join(item.get("features", [])),
                    item.get("address", ""),
                ]).lower()
                if not any(kw.lower() in searchable for kw in keywords):
                    continue

            filtered.append(item)

        # 兜底：关键词筛选无结果时，返回该品类全部结果（忽略关键词）
        if not filtered and keywords and results:
            filtered = [
                item for item in results
                if item["rating"] >= rating_min and item["distance"] <= distance_max
            ]

        if not filtered:
            return ToolResult(
                success=True,
                data={"results": [], "total": 0, "message": "未找到符合条件的结果"},
            )

        return ToolResult(
            success=True,
            data={
                "results": filtered,
                "total": len(filtered),
            },
        )
