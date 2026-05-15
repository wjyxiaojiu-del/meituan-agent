"""
剧本杀叙事引擎
将普通 Citywalk 转化为沉浸式剧情冒险
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class StoryCheckpoint:
    """剧情节点"""
    poi_id: str
    poi_name: str
    narrative: str
    task: str
    hint: str
    reward: str
    unlocks_next: bool = True


@dataclass
class StoryRoute:
    """剧情路线"""
    title: str
    theme: str
    description: str
    checkpoints: List[StoryCheckpoint]
    total_duration: int
    difficulty: str


STORY_TEMPLATES = {
    "美食侦探": {
        "title": "《消失的味道：老字号秘方之谜》",
        "theme": "侦探解谜",
        "description": "一家百年老字号的祖传秘方神秘消失，线索散落在这座城市的美食角落……",
        "difficulty": "medium",
        "checkpoints": [
            {
                "narrative": "你收到一封匿名信：'想知道秘方去哪了吗？先去那家最老的茶楼找老板聊聊。'",
                "task": "找到茶楼老板，对他说暗号'今天的龙井真香'",
                "hint": "看哪家茶楼历史最久",
                "reward": "获得第一个线索碎片 + 茶楼8折券",
            },
            {
                "narrative": "茶楼老板压低声音：'秘方可能被带到了小吃街，去找那个排队最长的摊位……'",
                "task": "在小吃街找到排队最长的摊位，买一份招牌小吃并拍照",
                "hint": "下午2-4点排队最长",
                "reward": "获得第二个线索碎片 + 小吃买一送一",
            },
            {
                "narrative": "小吃摊主悄悄告诉你：'最后有人看到秘方是在那家需要预订的私房菜馆……'",
                "task": "到达私房菜馆，向服务员出示前两个线索碎片",
                "hint": "需要提前预订",
                "reward": "解锁隐藏菜单 + 解锁最终剧情",
            },
        ],
    },
    "浪漫逃亡": {
        "title": "《城市恋人：24小时心动挑战》",
        "theme": "浪漫冒险",
        "description": "你和TA被'困'在这座城市，需要完成5个心动挑战才能解锁最终惊喜……",
        "difficulty": "easy",
        "checkpoints": [
            {
                "narrative": "挑战1：为对方选一束花，花语要代表你们的故事",
                "task": "在花店买一束花，送给TA",
                "hint": "玫瑰太普通，试试满天星或向日葵",
                "reward": "解锁挑战2",
            },
            {
                "narrative": "挑战2：一起完成一杯拉花咖啡，图案由你们决定",
                "task": "在咖啡馆合作完成一杯拉花",
                "hint": "可以请咖啡师指导",
                "reward": "解锁挑战3 + 咖啡师拍立得一张",
            },
            {
                "narrative": "挑战3：找到这座城市最高的观景位，一起看日落",
                "task": "到达观景餐厅/天台，拍摄日落合照",
                "hint": "提前预订景观位",
                "reward": "解锁最终晚餐",
            },
        ],
    },
    "团建大作战": {
        "title": "《最强团队：密室逃脱 + 美食争霸》",
        "theme": "团队协作",
        "description": "公司团建，但老板说要有点挑战性。先解谜，再做饭，最后评比！",
        "difficulty": "hard",
        "checkpoints": [
            {
                "narrative": "第一关：密室逃脱。60分钟内逃出，考验团队配合",
                "task": "完成密室逃脱挑战",
                "hint": "分工合作，有人负责找线索，有人负责解谜",
                "reward": "根据逃脱时间获得不同数量的'美食基金'",
            },
            {
                "narrative": "第二关：美食争霸。用密室赢得的基金，在超市采购食材",
                "task": "在限定预算内采购晚餐食材",
                "hint": "提前分工：有人负责肉类，有人负责蔬菜",
                "reward": "食材 + 烹饪场地",
            },
            {
                "narrative": "第三关：厨艺大比拼。各组用采购的食材做晚餐",
                "task": "小组合作完成一道菜",
                "hint": "可以提前查好菜谱",
                "reward": "最佳菜品奖状 + 全员聚餐",
            },
        ],
    },
    "亲子冒险": {
        "title": "《小小探险家：城市宝藏猎人》",
        "theme": "亲子冒险",
        "description": "宝贝，城市的每个角落都藏着宝藏，和爸爸妈妈一起出发寻找吧！",
        "difficulty": "easy",
        "checkpoints": [
            {
                "narrative": "第一站：去儿童乐园收集'快乐能量'！完成3个游乐项目就算过关",
                "task": "带孩子玩3个游乐项目，拍下开心瞬间",
                "hint": "选适合年龄的项目",
                "reward": "获得'快乐徽章' + 冰淇淋兑换券",
            },
            {
                "narrative": "第二站：去博物馆寻找'知识宝藏'！找到3件指定展品",
                "task": "在博物馆找到恐龙化石、蝴蝶标本和矿石展厅",
                "hint": "可以问工作人员",
                "reward": "获得'知识徽章' + 博物馆纪念品",
            },
            {
                "narrative": "最终站：用收集到的徽章，在餐厅兑换'宝藏大餐'！",
                "task": "到达餐厅，出示徽章兑换特别套餐",
                "hint": "记得提前预订宝宝椅",
                "reward": "全家福 + '小小探险家'证书",
            },
        ],
    },
}


class StoryEngine:
    """叙事引擎"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def detect_story_preference(self, user_input: str) -> bool:
        """从用户输入中识别是否偏好剧本杀模式"""
        story_keywords = [
            "好玩", "不一样", "剧情", "挑战", "游戏", "闯关",
            "探险", "冒险", "密室", "剧本杀", "解谜", "有趣",
            "刺激", "互动", "任务", "打卡", "收集", "故事",
        ]
        return any(kw in user_input for kw in story_keywords)

    def select_template(self, intent: Dict) -> str:
        """根据意图选择最合适的剧情模板"""
        people = intent.get("people", [])
        user_input = intent.get("raw_input", "")

        has_child = any(p.get("role") == "child" for p in people)
        has_partner = any(
            p.get("role") in ("wife", "husband", "girlfriend", "boyfriend")
            for p in people
        )
        is_team = any(
            kw in user_input for kw in ["团建", "公司", "同事", "部门"]
        )

        if is_team:
            return "团建大作战"
        if has_child:
            return "亲子冒险"
        if has_partner and intent.get("surprise"):
            return "浪漫逃亡"
        return "美食侦探"

    async def generate_story_route(
        self,
        intent: Dict,
        route: list,
    ) -> StoryRoute:
        """为已有路线披上剧情外衣"""
        template_name = self.select_template(intent)
        template = STORY_TEMPLATES[template_name]

        checkpoints = []
        for i, node in enumerate(route):
            if i < len(template["checkpoints"]):
                cp_data = template["checkpoints"][i]
                checkpoints.append(StoryCheckpoint(
                    poi_id=node.poi.id,
                    poi_name=node.poi.name,
                    narrative=cp_data["narrative"],
                    task=cp_data["task"],
                    hint=cp_data["hint"],
                    reward=cp_data["reward"],
                ))

        return StoryRoute(
            title=template["title"],
            theme=template["theme"],
            description=template["description"],
            checkpoints=checkpoints,
            total_duration=sum(node.poi.avg_duration for node in route),
            difficulty=template["difficulty"],
        )

    async def generate_dynamic_narrative(
        self,
        checkpoint: StoryCheckpoint,
        user_progress: int,
        context: str,
    ) -> str:
        """用 LLM 生成动态剧情文本"""
        if not self.llm_client or not self.llm_client._client:
            return checkpoint.narrative

        prompt = f"""你是剧本杀 DM。当前剧情节点：
地点：{checkpoint.poi_name}
基础剧情：{checkpoint.narrative}
用户进度：已完成 {user_progress} 个任务
额外背景：{context}

请用 100 字以内，以 DM 的口吻重新讲述这段剧情，要有悬念感和代入感。"""

        try:
            return await self.llm_client.chat([{"role": "user", "content": prompt}])
        except Exception:
            return checkpoint.narrative

    def format_story_for_display(self, story: StoryRoute) -> str:
        """格式化剧情路线供展示"""
        difficulty_stars = "⭐" * (3 if story.difficulty == "hard" else 2 if story.difficulty == "medium" else 1)
        lines = [
            f"🎭 {story.title}",
            f"主题：{story.theme} | 难度：{difficulty_stars}",
            f"\n{story.description}\n",
            "📍 任务节点：",
        ]

        for i, cp in enumerate(story.checkpoints, 1):
            lines.extend([
                f"\n🔍 第{i}关：{cp.poi_name}",
                f"   📖 {cp.narrative}",
                f"   🎯 任务：{cp.task}",
                f"   💡 提示：{cp.hint}",
                f"   🎁 奖励：{cp.reward}",
            ])

        return "\n".join(lines)
