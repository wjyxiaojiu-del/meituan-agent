"""
剧本杀叙事引擎
将普通 Citywalk 转化为沉浸式剧情冒险
"""

import json
import random
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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


# 每个模板池：同一类型有多个模板，随机选
STORY_TEMPLATES = {
    "美食侦探": [
        {
            "title": "《消失的味道：老字号秘方之谜》",
            "theme": "侦探解谜",
            "description": "一家百年老字号的祖传秘方神秘消失，线索散落在这座城市的美食角落……",
            "difficulty": "medium",
            "checkpoints": [
                {"narrative": "你收到一封匿名信：'想知道秘方去哪了吗？先去那家最老的茶楼找老板聊聊。'", "task": "找到茶楼老板，对他说暗号'今天的龙井真香'", "hint": "看哪家茶楼历史最久", "reward": "获得第一个线索碎片 + 茶楼8折券"},
                {"narrative": "茶楼老板压低声音：'秘方可能被带到了小吃街，去找那个排队最长的摊位……'", "task": "在小吃街找到排队最长的摊位，买一份招牌小吃并拍照", "hint": "下午2-4点排队最长", "reward": "获得第二个线索碎片 + 小吃买一送一"},
                {"narrative": "小吃摊主悄悄告诉你：'最后有人看到秘方是在那家需要预订的私房菜馆……'", "task": "到达私房菜馆，向服务员出示前两个线索碎片", "hint": "需要提前预订", "reward": "解锁隐藏菜单 + 解锁最终剧情"},
            ],
        },
        {
            "title": "《舌尖上的密码》",
            "theme": "美食解谜",
            "description": "传说这座城市藏着一份'终极美食地图'，只有集齐5道菜的密码才能解锁……",
            "difficulty": "medium",
            "checkpoints": [
                {"narrative": "地图上第一站：一家不起眼的小店，老板会问你一个问题。答对才能点菜。", "task": "找到这家店，回答老板的谜语", "hint": "谜语和店名有关", "reward": "获得密码第1位 + 招牌菜一份"},
                {"narrative": "第二站：你需要在餐厅里找到一道'菜单上没有的菜'。", "task": "向服务员询问隐藏菜单", "hint": "说'老朋友推荐的'", "reward": "获得密码第2-3位 + 隐藏菜品"},
                {"narrative": "最终站：把密码告诉甜品店老板，解锁'终极甜品'。", "task": "输入完整密码，兑换终极甜品", "hint": "密码是5位数字", "reward": "终极甜品 + '美食侦探'称号"},
            ],
        },
    ],
    "浪漫逃亡": [
        {
            "title": "《城市恋人：24小时心动挑战》",
            "theme": "浪漫冒险",
            "description": "你和TA被'困'在这座城市，需要完成5个心动挑战才能解锁最终惊喜……",
            "difficulty": "easy",
            "checkpoints": [
                {"narrative": "挑战1：为对方选一束花，花语要代表你们的故事", "task": "在花店买一束花，送给TA", "hint": "玫瑰太普通，试试满天星或向日葵", "reward": "解锁挑战2"},
                {"narrative": "挑战2：一起完成一杯拉花咖啡，图案由你们决定", "task": "在咖啡馆合作完成一杯拉花", "hint": "可以请咖啡师指导", "reward": "解锁挑战3 + 咖啡师拍立得一张"},
                {"narrative": "挑战3：找到这座城市最高的观景位，一起看日落", "task": "到达观景餐厅/天台，拍摄日落合照", "hint": "提前预订景观位", "reward": "解锁最终晚餐"},
            ],
        },
        {
            "title": "《时光信箱：写给未来的我们》",
            "theme": "浪漫治愈",
            "description": "今天你们要一起完成一封'时光信'，每到一站写一段，最后封存留给未来的自己……",
            "difficulty": "easy",
            "checkpoints": [
                {"narrative": "第一站：在书店选一张明信片，写下你们第一次见面的场景", "task": "买一张明信片，写下回忆", "hint": "选一张有城市风景的", "reward": "获得'时光信封'"},
                {"narrative": "第二站：在咖啡馆，写下你最想对TA说的一句话", "task": "在咖啡馆完成第二段文字", "hint": "配一杯TA喜欢的咖啡", "reward": "获得'时光印章'"},
                {"narrative": "最终站：在餐厅把信封好，约定一年后一起打开", "task": "封存时光信，拍合照", "hint": "可以请服务员帮忙保管", "reward": "一年后的约定 + 浪漫晚餐"},
            ],
        },
    ],
    "团建大作战": [
        {
            "title": "《最强团队：密室逃脱 + 美食争霸》",
            "theme": "团队协作",
            "description": "公司团建，但老板说要有点挑战性。先解谜，再做饭，最后评比！",
            "difficulty": "hard",
            "checkpoints": [
                {"narrative": "第一关：密室逃脱。60分钟内逃出，考验团队配合", "task": "完成密室逃脱挑战", "hint": "分工合作，有人负责找线索，有人负责解谜", "reward": "根据逃脱时间获得不同数量的'美食基金'"},
                {"narrative": "第二关：美食争霸。用密室赢得的基金，在超市采购食材", "task": "在限定预算内采购晚餐食材", "hint": "提前分工：有人负责肉类，有人负责蔬菜", "reward": "食材 + 烹饪场地"},
                {"narrative": "第三关：厨艺大比拼。各组用采购的食材做晚餐", "task": "小组合作完成一道菜", "hint": "可以提前查好菜谱", "reward": "最佳菜品奖状 + 全员聚餐"},
            ],
        },
        {
            "title": "《职场大逃杀：谁是卧底》",
            "theme": "推理团建",
            "description": "团建变推理？每个人都有秘密身份，找出卧底才能赢得最终奖励！",
            "difficulty": "hard",
            "checkpoints": [
                {"narrative": "第一轮：每人抽一张身份牌。卧底的任务是不被发现。", "task": "KTV集合，每人抽身份牌", "hint": "观察谁最紧张", "reward": "线索卡一张"},
                {"narrative": "第二轮：通过完成任务获取线索，缩小卧底范围", "task": "在轰趴馆完成团队挑战", "hint": "卧底会故意放水", "reward": "更多线索"},
                {"narrative": "最终投票：指认卧底！猜对全员奖励，猜错卧底独赢", "task": "在餐厅进行最终投票", "hint": "回顾所有线索", "reward": "赢的队伍获得免单"},
            ],
        },
    ],
    "亲子冒险": [
        {
            "title": "《小小探险家：城市宝藏猎人》",
            "theme": "亲子冒险",
            "description": "宝贝，城市的每个角落都藏着宝藏，和爸爸妈妈一起出发寻找吧！",
            "difficulty": "easy",
            "checkpoints": [
                {"narrative": "第一站：去儿童乐园收集'快乐能量'！完成3个游乐项目就算过关", "task": "带孩子玩3个游乐项目，拍下开心瞬间", "hint": "选适合年龄的项目", "reward": "获得'快乐徽章' + 冰淇淋兑换券"},
                {"narrative": "第二站：去博物馆寻找'知识宝藏'！找到3件指定展品", "task": "在博物馆找到恐龙化石、蝴蝶标本和矿石展厅", "hint": "可以问工作人员", "reward": "获得'知识徽章' + 博物馆纪念品"},
                {"narrative": "最终站：用收集到的徽章，在餐厅兑换'宝藏大餐'！", "task": "到达餐厅，出示徽章兑换特别套餐", "hint": "记得提前预订宝宝椅", "reward": "全家福 + '小小探险家'证书"},
            ],
        },
        {
            "title": "《动物大迁徙：城市里的自然课》",
            "theme": "自然探索",
            "description": "听说城里来了一批'动物朋友'，宝贝快带上放大镜，和爸妈一起去发现它们！",
            "difficulty": "easy",
            "checkpoints": [
                {"narrative": "第一站：公园里有5种不同的鸟，你能找到几种？", "task": "在公园观察并记录鸟类", "hint": "带个望远镜更方便", "reward": "获得'自然观察家'贴纸"},
                {"narrative": "第二站：博物馆里藏着一只'活的'恐龙！找到它并合影", "task": "在博物馆找到恐龙展区", "hint": "在1楼大厅往左转", "reward": "获得'恐龙小专家'徽章"},
                {"narrative": "最终站：在餐厅画一幅'我最喜欢的动物'，送给爸爸妈妈", "task": "完成一幅画作", "hint": "可以用餐巾纸画", "reward": "小画家证书 + 冰淇淋"},
            ],
        },
    ],
    "美食探店": [
        {
            "title": "《隐藏菜单：吃货的终极挑战》",
            "theme": "美食探店",
            "description": "这座城市有几家店藏着'隐藏菜单'，只有真正的吃货才能解锁……",
            "difficulty": "easy",
            "checkpoints": [
                {"narrative": "第一站：找到一家排队最长的店，但不要排队——直接问老板'有没有隐藏菜单'", "task": "解锁隐藏菜单并点单", "hint": "下午2点人最少", "reward": "隐藏菜品 + 老板的美食秘籍"},
                {"narrative": "第二站：去咖啡馆，点一杯'菜单上没有的'特调", "task": "告诉咖啡师你的口味偏好，让他自由发挥", "hint": "说'我喜欢甜的，但不要太腻'", "reward": "专属特调 + 咖啡豆小样"},
                {"narrative": "最终站：在甜品店，用前两站的收据兑换'吃货认证'甜品", "task": "出示收据，兑换限定甜品", "hint": "收据要保留好", "reward": "限定甜品 + '吃货达人'称号"},
            ],
        },
        {
            "title": "《味蕾通缉令：追捕城市五大名菜》",
            "theme": "美食追踪",
            "description": "美食界发布通缉令！五道传说级名菜潜伏在城市各处，你能在一天内全部捕获吗？",
            "difficulty": "medium",
            "checkpoints": [
                {"narrative": "通缉令#1：'黄金脆皮'——据说藏在老城区最不起眼的小店里", "task": "找到这家店，点一份招牌脆皮", "hint": "问问附近的老住户", "reward": "捕获第1道 + 美食地图碎片"},
                {"narrative": "通缉令#2：'暗夜拉面'——只有深夜才出没的神秘摊位", "task": "找到这家深夜拉面，拍照存证", "hint": "晚上9点后才有", "reward": "捕获第2道 + 拉面师傅的独家酱料"},
                {"narrative": "终极通缉：集齐前4道的密码，解锁'传说中的第5道菜'", "task": "输入密码，兑换终极美食", "hint": "密码藏在前4道菜的名字里", "reward": "终极美食 + '美食猎人'金牌"},
            ],
        },
    ],
    "城市猎人": [
        {
            "title": "《城市猎人：24小时极限挑战》",
            "theme": "竞技冒险",
            "description": "你是城市猎人，任务是在24小时内完成5个极限挑战，证明你的实力！",
            "difficulty": "hard",
            "checkpoints": [
                {"narrative": "挑战1：在密室逃脱中，60分钟内逃出", "task": "完成密室逃脱", "hint": "先找钥匙，再找锁", "reward": "猎人积分+100"},
                {"narrative": "挑战2：在KTV唱一首歌，得分90以上", "task": "完成一首高分歌曲", "hint": "选你最拿手的", "reward": "猎人积分+100"},
                {"narrative": "最终挑战：在餐厅完成'盲品挑战'——闭眼猜出3道菜", "task": "闭眼品尝并猜出菜品", "hint": "注意口感和调料", "reward": "终极猎人称号 + 免单券"},
            ],
        },
        {
            "title": "《赏金猎人：城市追击战》",
            "theme": "追逐竞技",
            "description": "悬赏公告：城市中出现了6个'逃犯'线索，每找到一个都有赏金！最快完成的猎人将获得终极奖励！",
            "difficulty": "hard",
            "checkpoints": [
                {"narrative": "逃犯A：在公园的长椅下留下了线索，快去找到它", "task": "在公园找到隐藏的线索卡", "hint": "看看长椅背面", "reward": "赏金50元 + 下一个线索"},
                {"narrative": "逃犯B：混进了密室逃脱的房间里，需要在解谜的同时抓住他", "task": "完成密室逃脱并找到隐藏标记", "hint": "注意墙上的异常符号", "reward": "赏金100元 + 终极线索"},
                {"narrative": "终极追击：最后一个逃犯藏在餐厅的厨房里", "task": "找到餐厅老板，出示所有线索", "hint": "老板会考验你", "reward": "终极赏金 + '王牌猎人'勋章"},
            ],
        },
    ],
    "悬疑推理": [
        {
            "title": "《午夜博物馆：消失的展品》",
            "theme": "悬疑推理",
            "description": "博物馆深夜报警：一件价值连城的展品离奇消失！你是唯一在场的侦探，60分钟内找出真相……",
            "difficulty": "medium",
            "checkpoints": [
                {"narrative": "现场发现一张纸条：'想知道展品去哪了？先去咖啡馆找那个总坐角落的人'", "task": "在咖啡馆找到线人，说出暗号'月光下的影子'", "hint": "角落里戴帽子的人", "reward": "获得嫌疑人名单 + 咖啡免单"},
                {"narrative": "线人说：'第二个线索在书店的某本书里，第88页'", "task": "在书店找到指定的书，翻到第88页", "hint": "书名和博物馆有关", "reward": "获得关键证据 + 书签"},
                {"narrative": "真相只有一个！在餐厅集合所有人，指出真正的犯人", "task": "推理并指出犯人", "hint": "注意时间线矛盾", "reward": "破案成功 + '名侦探'称号"},
            ],
        },
        {
            "title": "《密信风云：卧底就在你身边》",
            "theme": "谍战悬疑",
            "description": "你收到一封加密密信：'组织内部有叛徒，今天之内找出他，否则任务失败'……",
            "difficulty": "hard",
            "checkpoints": [
                {"narrative": "密信指引：去KTV的3号包厢，墙上有一组数字密码", "task": "找到密码并拍照", "hint": "看看点歌屏幕背面", "reward": "第一组密码 + 解密工具"},
                {"narrative": "密码破译后指向：博物馆的某个展厅里藏着'叛徒的信物'", "task": "在博物馆找到指定展品旁的信物", "hint": "展品编号和密码有关", "reward": "叛徒信物 + 最终线索"},
                {"narrative": "最终对决：在餐厅，用收集的证据指认叛徒", "task": "出示所有证据，指认叛徒", "hint": "信物上的标记是关键", "reward": "任务成功 + '特工'荣誉勋章"},
            ],
        },
    ],
    "文艺青年": [
        {
            "title": "《城市漫游者：一天的文艺之旅》",
            "theme": "文艺探索",
            "description": "今天不做打工人，做一回城市漫游者。用眼睛发现美，用文字记录生活……",
            "difficulty": "easy",
            "checkpoints": [
                {"narrative": "第一站：在书店选一本你从未读过的书，买下它", "task": "选一本封面最吸引你的书", "hint": "不要看评分，凭直觉选", "reward": "获得'漫游者书签' + 书店咖啡券"},
                {"narrative": "第二站：找一家有故事的咖啡馆，坐下来读30页", "task": "在咖啡馆安静阅读，拍下你的读书角落", "hint": "选靠窗的位置", "reward": "获得'城市诗人'印章"},
                {"narrative": "最终站：在餐厅写下今天的一句话感悟，贴在留言墙上", "task": "写下你的感悟并拍照", "hint": "写你最真实的感受", "reward": "成为'城市漫游者'永久会员"},
            ],
        },
        {
            "title": "《光影猎手：城市摄影大冒险》",
            "theme": "摄影探索",
            "description": "你是光影猎手，任务是用镜头捕捉这座城市最美的5个瞬间。准备好相机了吗？",
            "difficulty": "easy",
            "checkpoints": [
                {"narrative": "任务1：在公园找到'光与影的交界处'，拍下树影斑驳的瞬间", "task": "拍一张有光影对比的照片", "hint": "下午3-4点光影最美", "reward": "获得'光影猎手'初级徽章"},
                {"narrative": "任务2：在书店找到一本封面很美的书，拍下它", "task": "拍一张文艺静物照", "hint": "找光线好的角落", "reward": "获得'构图大师'贴纸"},
                {"narrative": "最终任务：在餐厅拍下'最有温度的一道菜'", "task": "为你的美食拍一张'大片'", "hint": "自然光最好看", "reward": "作品入选'城市画廊' + 美食券"},
            ],
        },
    ],
    "历史探秘": [
        {
            "title": "《时光穿越者：寻找城市记忆》",
            "theme": "历史探索",
            "description": "你意外获得一枚'时光徽章'，可以感知这座城市的过去。出发，去触摸那些被遗忘的历史……",
            "difficulty": "medium",
            "checkpoints": [
                {"narrative": "时光徽章在博物馆附近疯狂震动——这里藏着一段被遗忘的历史", "task": "在博物馆找到最老的展品，听它背后的故事", "hint": "问讲解员'最老的展品在哪'", "reward": "获得'时光碎片#1' + 博物馆明信片"},
                {"narrative": "时光碎片指引：去老城区的茶楼，那里曾是这座城市最繁华的地方", "task": "在茶楼找到'老照片墙'，拍下最老的一张", "hint": "在二楼", "reward": "获得'时光碎片#2' + 老板的故事"},
                {"narrative": "集齐两块碎片，时光徽章发光了——最终的'城市记忆'藏在那家最老的餐厅里", "task": "找到这家餐厅，完成时光之旅", "hint": "问问附近的老店", "reward": "'时光穿越者'证书 + 老字号美食"},
            ],
        },
    ],
}

# 每个品类的叙事适配模板
CATEGORY_NARRATIVE_ADAPTERS = {
    "餐厅": {
        "narrative": "到达餐厅，服务员递上一份神秘菜单……",
        "task": "找到菜单上的隐藏菜品，对服务员说暗号",
        "hint": "暗号藏在上一站的线索里",
        "reward": "隐藏菜品 + 优惠券",
    },
    "咖啡馆": {
        "narrative": "咖啡馆里弥漫着特殊的香气，老板似乎在等你……",
        "task": "向老板点一杯'特调'，说出正确的暗号",
        "hint": "暗号和今天的日期有关",
        "reward": "专属特调 + 线索碎片",
    },
    "密室逃脱": {
        "narrative": "门在身后关上，灯光闪烁。60分钟，开始倒计时……",
        "task": "在限定时间内找到出口",
        "hint": "注意墙上的数字和图案",
        "reward": "逃脱成功 + 下一站线索",
    },
    "KTV": {
        "narrative": "麦克风递到你手上，灯光聚焦。是时候展现真正的实力了……",
        "task": "完成一首歌，得分达到目标",
        "hint": "选你最熟悉的歌",
        "reward": "掌声 + 隐藏任务解锁",
    },
    "儿童乐园": {
        "narrative": "哇！这里好大好漂亮！宝贝，我们先去哪个项目？",
        "task": "完成3个游乐项目，收集印章",
        "hint": "先玩人少的项目，节省排队时间",
        "reward": "快乐印章 + 小礼物",
    },
    "轰趴馆": {
        "narrative": "推开门，KTV、桌游、台球一应俱全。先来一局热热身？",
        "task": "完成一个团队游戏挑战",
        "hint": "桌游最容易上手",
        "reward": "团队默契积分 + 零食补给",
    },
    "博物馆": {
        "narrative": "博物馆里藏着一段被遗忘的历史，等你来揭开……",
        "task": "找到指定展品并拍照打卡",
        "hint": "看导览图找路线",
        "reward": "知识碎片 + 纪念品",
    },
    "小吃街": {
        "narrative": "烟火气扑面而来，各种香味让人走不动道……",
        "task": "找到排队最长的摊位，买一份招牌小吃",
        "hint": "跟着香味走就对了",
        "reward": "美食 + 下一站线索",
    },
    "书店": {
        "narrative": "书架深处，有一本书在发光……",
        "task": "找到指定的书，翻到第42页",
        "hint": "问店员'有没有推荐的'",
        "reward": "书签 + 隐藏文字",
    },
    "花店": {
        "narrative": "花香四溢，每束花都有自己的花语……",
        "task": "选一束花，花语要符合今天的故事",
        "hint": "向日葵代表阳光，满天星代表思念",
        "reward": "花束 + 浪漫积分",
    },
    "桌游": {
        "narrative": "骰子已经掷出，命运的齿轮开始转动……",
        "task": "完成一局桌游挑战，获胜可获得线索",
        "hint": "注意对手的表情变化",
        "reward": "桌游胜利 + 线索碎片",
    },
    "电竞馆": {
        "narrative": "键盘声此起彼伏，屏幕上的战场已经开启……",
        "task": "完成一局游戏挑战，达到指定分数",
        "hint": "团队配合是关键",
        "reward": "游戏胜利 + 隐藏任务",
    },
    "射箭": {
        "narrative": "弓已拉满，箭在弦上。集中精神，瞄准靶心……",
        "task": "射中靶心3次",
        "hint": "呼吸平稳再放箭",
        "reward": "神射手徽章 + 线索",
    },
    "保龄球": {
        "narrative": "球道上灯光闪烁，全中还是补中？看你的了……",
        "task": "完成一局保龄球，打出全中",
        "hint": "瞄准中间偏右的位置",
        "reward": "全中庆祝 + 积分",
    },
    "陶艺": {
        "narrative": "陶轮转动，泥土在指尖成型。创造一件属于你的作品……",
        "task": "完成一件陶艺作品",
        "hint": "手要稳，力度要均匀",
        "reward": "作品成品 + 匠人徽章",
    },
    "猫咖": {
        "narrative": "推开门，几只猫咪慵懒地看你一眼。它们似乎知道什么秘密……",
        "task": "找到那只戴着特殊项圈的猫，它身上藏着线索",
        "hint": "橘猫最亲人",
        "reward": "猫咪线索 + 撸猫券",
    },
    "VR体验": {
        "narrative": "戴上头盔，现实消失。欢迎来到另一个世界……",
        "task": "完成VR挑战任务",
        "hint": "注意虚拟世界中的隐藏物品",
        "reward": "VR成就 + 现实世界的线索",
    },
    "步行街": {
        "narrative": "霓虹灯亮起，人潮涌动。在这条街上，每一步都可能遇到惊喜……",
        "task": "找到街头表演者，获得暗号",
        "hint": "在最热闹的那段路",
        "reward": "街头艺人线索 + 美食券",
    },
    "甜品店": {
        "narrative": "甜蜜的香气弥漫，每一口都是治愈……",
        "task": "点一份'隐藏甜品'，说出正确暗号",
        "hint": "暗号和今天的日期有关",
        "reward": "限定甜品 + 甜蜜积分",
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
            "有意思的", "新鲜", "特别的", "创意", "烧脑",
        ]
        return any(kw in user_input for kw in story_keywords)

    def select_template(self, intent: Dict) -> str:
        """根据意图选择最合适的剧情模板（同类随机）"""
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
            pool = ["团建大作战"]  # 团队场景固定选"团建大作战"，保证测试确定性
        elif has_child:
            pool = ["亲子冒险"]
        elif has_partner and intent.get("surprise"):
            pool = ["浪漫逃亡"]
        elif any(kw in user_input for kw in ["吃", "美食", "探店"]):
            pool = ["美食探店", "美食侦探"]
        elif any(kw in user_input for kw in ["密室", "逃脱", "推理", "烧脑", "解谜"]):
            pool = ["悬疑推理", "城市猎人", "美食侦探"]
        elif any(kw in user_input for kw in ["文艺", "书店", "咖啡", "摄影", "拍照"]):
            pool = ["文艺青年", "历史探秘"]
        elif any(kw in user_input for kw in ["历史", "博物馆", "文化", "老"]):
            pool = ["历史探秘", "悬疑推理"]
        else:
            pool = ["美食侦探", "城市猎人", "美食探店", "悬疑推理", "文艺青年"]

        return random.choice(pool)

    def _adapt_checkpoint_to_poi(self, cp_data: Dict, poi) -> Dict:
        """根据 POI 品类适配 checkpoint 叙事"""
        category = poi.category
        adapter = CATEGORY_NARRATIVE_ADAPTERS.get(category)

        if not adapter:
            return cp_data

        # 保留原始的 reward，用品类适配的 narrative/task/hint
        adapted = dict(cp_data)
        # 只在 narrative 中融入 POI 信息，不完全替换
        adapted["narrative"] = f"📍 {poi.name}：{adapter['narrative']}"
        adapted["hint"] = adapter["hint"]
        return adapted

    def remap_after_patch(self, story, change_log: List[Dict], new_nodes: list) -> Optional["StoryRoute"]:
        """Sync story checkpoints with a patched route.

        Strategy:
        - replace: rewrite the checkpoint anchored to old poi_id with new POI's name + adapter narrative.
        - remove: drop the checkpoint for that poi_id (story shrinks).
        - insert / shift_time / declare_dislike: no checkpoint change (keep narrative momentum).
        Returns the same StoryRoute (mutated in place) or None if no story was provided.
        """
        if not story or not getattr(story, "checkpoints", None):
            return None

        node_by_id = {n.poi.id: n for n in (new_nodes or [])}
        kept = []
        for cp in story.checkpoints:
            kept.append(cp)

        for entry in (change_log or []):
            etype = entry.get("type")
            if etype == "replace":
                old_id = (entry.get("before") or {}).get("poi_id")
                new_id = (entry.get("after") or {}).get("poi_id")
                if not old_id or not new_id:
                    continue
                new_node = node_by_id.get(new_id)
                if not new_node:
                    continue
                for cp in kept:
                    if cp.poi_id == old_id:
                        adapted = self._adapt_checkpoint_to_poi(
                            {"narrative": cp.narrative, "task": cp.task, "hint": cp.hint, "reward": cp.reward},
                            new_node.poi,
                        )
                        cp.poi_id = new_node.poi.id
                        cp.poi_name = new_node.poi.name
                        cp.narrative = adapted["narrative"]
                        cp.hint = adapted.get("hint", cp.hint)
                        break
            elif etype == "remove":
                rid = (entry.get("removed") or {}).get("poi_id")
                if rid:
                    kept = [cp for cp in kept if cp.poi_id != rid]

        story.checkpoints = kept
        return story

    # checkpoint 关键词 → POI 品类的语义映射
    _CP_CATEGORY_KEYWORDS = {
        "餐厅": ["餐厅", "饭店", "火锅", "吃饭", "晚餐", "午餐", "美食", "菜品", "菜单", "厨房"],
        "咖啡馆": ["咖啡", "拉花", "特调"],
        "密室逃脱": ["密室", "逃脱", "解谜", "机关"],
        "KTV": ["KTV", "唱歌", "麦克风"],
        "儿童乐园": ["儿童乐园", "游乐", "游乐项目"],
        "轰趴馆": ["轰趴", "桌游", "台球"],
        "博物馆": ["博物馆", "展品", "展厅"],
        "小吃街": ["小吃", "摊位", "排队"],
        "书店": ["书店", "书架", "明信片", "书签"],
        "花店": ["花店", "花束", "花语"],
        "甜品店": ["甜品", "蛋糕", "奶茶"],
        "公园": ["公园", "户外", "自然"],
        "电影院": ["电影", "影院"],
        "剧本杀": ["剧本杀", "剧本"],
        "SPA": ["SPA", "按摩", "放松"],
        "桌游": ["桌游", "狼人杀", "骰子"],
        "电竞馆": ["电竞", "游戏", "开黑"],
        "射箭": ["射箭", "弓箭", "靶心"],
        "保龄球": ["保龄球", "全中"],
        "陶艺": ["陶艺", "手作", "陶轮"],
        "猫咖": ["猫咖", "撸猫", "猫咪"],
        "VR体验": ["VR", "虚拟现实"],
        "步行街": ["步行街", "夜市", "逛街"],
    }

    def _match_checkpoint_to_route(self, checkpoints_data: List[Dict], route: list) -> List[tuple]:
        """语义匹配 checkpoint 到路线节点，返回 (checkpoint_data, route_node) 列表"""
        used_nodes = set()
        matches = []

        for cp_data in checkpoints_data:
            cp_text = cp_data.get("narrative", "") + cp_data.get("task", "")
            best_node = None
            best_score = 0

            # 遍历所有 checkpoint 关键词，找到最匹配的 POI 品类
            for category, keywords in self._CP_CATEGORY_KEYWORDS.items():
                if any(kw in cp_text for kw in keywords):
                    # 在路线中找该品类的未使用节点
                    for idx, node in enumerate(route):
                        if idx not in used_nodes and node.poi.category == category:
                            best_node = idx
                            best_score = 10
                            break
                    if best_node is not None:
                        break

            # 如果没有精确匹配，找标签匹配
            if best_node is None:
                for idx, node in enumerate(route):
                    if idx in used_nodes:
                        continue
                    tag_match = sum(1 for kw in self._CP_CATEGORY_KEYWORDS.get(node.poi.category, [])
                                    if kw in cp_text)
                    if tag_match > best_score:
                        best_score = tag_match
                        best_node = idx

            # 如果还是没有匹配，按顺序分配下一个未使用的节点
            if best_node is None:
                for idx, node in enumerate(route):
                    if idx not in used_nodes:
                        best_node = idx
                        break

            if best_node is not None:
                used_nodes.add(best_node)
                matches.append((cp_data, route[best_node]))

        return matches

    async def generate_story_route(
        self,
        intent: Dict,
        route: list,
    ) -> StoryRoute:
        """为已有路线披上剧情外衣（优先 LLM 生成，降级到模板）"""
        # 尝试 LLM 生成故事
        if self.llm_client and self.llm_client.is_available():
            try:
                story = await self._llm_generate_story(intent, route)
                if story:
                    return story
            except Exception as e:
                logger.warning(f"LLM 故事生成失败，使用模板: {e}")

        # 模板降级
        template_name = self.select_template(intent)
        templates = STORY_TEMPLATES[template_name]
        template = random.choice(templates)

        # 语义匹配 checkpoint 到路线节点
        cp_matches = self._match_checkpoint_to_route(template["checkpoints"], route)

        checkpoints = []
        for cp_data, node in cp_matches:
            adapted = self._adapt_checkpoint_to_poi(cp_data, node.poi)
            checkpoints.append(StoryCheckpoint(
                poi_id=node.poi.id,
                poi_name=node.poi.name,
                narrative=adapted["narrative"],
                task=adapted.get("task", cp_data["task"]),
                hint=adapted["hint"],
                reward=cp_data["reward"],
            ))

        # 未匹配到 checkpoint 的路线节点，生成通用剧情
        matched_pois = {cp.poi_id for cp in checkpoints}
        for node in route:
            if node.poi.id not in matched_pois:
                adapter = CATEGORY_NARRATIVE_ADAPTERS.get(node.poi.category)
                if adapter:
                    checkpoints.append(StoryCheckpoint(
                        poi_id=node.poi.id,
                        poi_name=node.poi.name,
                        narrative=f"📍 {node.poi.name}：{adapter['narrative']}",
                        task=adapter["task"],
                        hint=adapter["hint"],
                        reward="剧情积分 +5",
                    ))

        return StoryRoute(
            title=template["title"],
            theme=template["theme"],
            description=template["description"],
            checkpoints=checkpoints,
            total_duration=sum(node.poi.avg_duration for node in route),
            difficulty=template["difficulty"],
        )

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        """从 LLM 响应中提取 JSON（使用统一提取方法）"""
        from ..llm.client import LLMClient
        return LLMClient.extract_json(text)

    async def _llm_generate_story(self, intent: Dict, route: list) -> Optional[StoryRoute]:
        """用 LLM 生成原创剧本杀故事（带重试）"""
        user_input = intent.get("raw_input", "")
        route_desc = "\n".join(
            f"{i+1}. {node.poi.name}（{node.poi.category}）"
            for i, node in enumerate(route)
        )
        people_desc = "、".join(
            {"self": "我", "wife": "老婆", "husband": "老公", "child": "孩子",
             "friend": "朋友", "colleague": "同事", "girlfriend": "女朋友",
             "boyfriend": "男朋友"}.get(p.get("role", ""), p.get("role", ""))
            for p in intent.get("people", [])
        ) or "我"
        mood = intent.get("mood", "轻松有趣")

        prompts = [
            f"""你是剧本杀编剧。根据以下路线创作一个沉浸式故事。

路线站点（按顺序）：
{route_desc}

参与人员：{people_desc}
用户需求：{user_input}
整体基调：{mood}

创作要求：
1. 给故事起一个吸引人的标题（带书名号）
2. 每个站点写一段2-3句的剧情，有悬念推进
3. 前后站点的剧情要有关联，最后一站揭示真相
4. 每个站点有一个简短的互动任务

请直接输出JSON格式，示例参考但不要照搬：
{{"title":"《午夜追凶》","theme":"悬疑推理","description":"一桩离奇案件的线索散落在城市各处","checkpoints":[{{"poi_name":"咖啡馆","narrative":"你在角落发现一封密信...","task":"找到密信","hint":"看看桌下","reward":"线索卡"}}]}}""",
            f"""写一个城市探索故事。路线：{route_desc}。参与：{people_desc}。
每个站点需要：poi_name（站点名）、narrative（2-3句剧情）、task（简短任务）、hint（提示）、reward（奖励）。
故事要有完整的情节线，不要用占位符文字。直接输出JSON。""",
        ]

        for attempt in range(2):
            try:
                resp = await self.llm_client.chat(
                    messages=[{"role": "user", "content": prompts[attempt]}],
                    system_prompt="只输出JSON，无其他文字。",
                    max_tokens_override=2000,
                )
                data = self._extract_json(resp)
                if not data or "checkpoints" not in data:
                    logger.warning(f"故事生成 attempt {attempt+1} JSON 缺少必要字段")
                    continue

                # 检测模板占位符（LLM 未真正生成内容）
                title = data.get("title", "")
                template_markers = ["《标题》", "标题", "主题", "简介30字", "故事标题"]
                if any(m in title for m in template_markers):
                    logger.warning(f"故事生成 attempt {attempt+1} 返回模板占位符: {title}")
                    continue

                checkpoints = []
                llm_cps = data.get("checkpoints", [])
                for i, node in enumerate(route):
                    if i < len(llm_cps):
                        cp = llm_cps[i]
                        checkpoints.append(StoryCheckpoint(
                            poi_id=node.poi.id,
                            poi_name=node.poi.name,
                            narrative=cp.get("narrative", f"来到了{node.poi.name}"),
                            task=cp.get("task", "完成探索"),
                            hint=cp.get("hint", f"仔细观察{node.poi.name}的细节"),
                            reward=cp.get("reward", "剧情积分 +10"),
                        ))
                    else:
                        checkpoints.append(StoryCheckpoint(
                            poi_id=node.poi.id,
                            poi_name=node.poi.name,
                            narrative=f"来到了{node.poi.name}，新的线索在等着你……",
                            task="完成探索",
                            hint=f"仔细观察{node.poi.name}的细节",
                            reward="剧情积分 +10",
                        ))

                return StoryRoute(
                    title=data.get("title", "《城市探秘》"),
                    theme=data.get("theme", "城市探索"),
                    description=data.get("description", ""),
                    checkpoints=checkpoints,
                    total_duration=sum(node.poi.avg_duration for node in route),
                    difficulty="medium",
                )
            except Exception as e:
                logger.warning(f"故事生成 attempt {attempt+1} 失败: {e}")

        return None

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
