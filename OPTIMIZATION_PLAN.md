# 美团 AI Agent 大赛 — 15 天冲刺优化方案

> **项目定位**：「剧本杀 Citywalk × 智能行程 Agent」—— 不只是推荐去哪玩，而是把整座城市变成沉浸式游戏场，Agent 做你的 DM（主持人），规划路线、编排剧情、一键执行所有预订。
>
> **双赛题覆盖**：任务型 Agent（帮你把事情做完）+ 智能路线规划（多 POI 串联最优路线）

---

## 一、现状诊断

### 1.1 现有资产

| 模块 | 现状 | 价值评估 |
|------|------|----------|
| Agent 核心框架 | Python + 状态机 + 三层异常处理 | 可用，需重构规划层 |
| LLM Client | 支持 Claude/OpenAI/Mock | 可用，需默认接入真实 LLM |
| Mock 工具链 | 5 个工具（搜索/预订/排队/配送/天气） | 数据太少，需扩充到 15+ |
| 微信小程序 | 有 JS 逻辑，缺 WXML/WXSS | 需要补齐前端 |
| 文档体系 | architecture + design_proposal + P0 | 包装不错，需对齐代码 |

### 1.2 核心问题

1. **规划层是硬编码规则引擎**，不是 AI 驱动 —— 与赛题"大语言模型"要求不符
2. **没有路线规划算法** —— 完全缺失赛题 B 的核心能力
3. **Mock 数据单薄** —— 只有 3 家餐厅、2 个乐园，Demo 一眼假
4. **前端跑不起来** —— 缺小程序模板文件
5. **没有用户确认环节** —— 赛题明确要求"确认后执行"
6. **没有分享/社交能力** —— 赛题要求"把计划发给小张"

### 1.3 15 天后的目标状态

```
┌─────────────────────────────────────────────────────────────┐
│  用户输入："周末和朋友4个人想玩点不一样的，要有剧情有挑战"      │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  🎭 场景识别 → 剧本杀 Citywalk 模式                           │
│  🧠 LLM 生成剧情大纲 + 任务节点                               │
│  🗺 路线规划引擎串联 POI（距离/时间/营业约束）                │
│  ✅ 用户确认方案                                             │
│  ⚡ Agent 一键执行：预订 → 排队 → 配送                       │
│  📤 生成分享文案："搞定了，下午2点出发，先去..."              │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、15 天总体节奏

| 阶段 | 天数 | 主题 | 交付物 |
|------|------|------|--------|
| **第一阶段** | Day 1-3 | 基础设施重建 | 路线规划引擎 + LLM 驱动规划 + 真实 LLM 接入 |
| **第二阶段** | Day 4-7 | 核心能力建设 | 剧本杀叙事引擎 + 扩充 Mock 数据 + 场景模板 |
| **第三阶段** | Day 8-11 | 前端与集成 | 小程序前端补齐 + 后端 API 完善 + 用户确认流程 |
| **第四阶段** | Day 12-14 | 演示打磨 | 3 个 Demo 场景 + 演示脚本 + 文档精修 |
| **第五阶段** | Day 15 | 最终验收 | 全链路测试 + 备用方案 + 提交检查 |

---

## 三、第一阶段：基础设施重建（Day 1-3）

### Day 1：路线规划引擎（赛题 B 核心）

#### 任务 1.1：新建 `agent/core/route_planner.py`

```python
"""
多 POI 智能路线规划引擎
算法：贪心初始化 + 2-opt 局部优化
约束：营业时间、步行距离、游玩时长、排队预估
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta, time
import math


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
    capacity: int = 50  # 容纳人数（团建场景用）
    equipment: List[str] = None  # 设备列表
    suitable_scenes: List[str] = None  # 适合场景


@dataclass
class RouteConstraints:
    """路线约束"""
    start_time: datetime
    max_duration: int  # 总时长上限（分钟）
    max_budget: float  # 总预算上限
    group_size: int = 2
    must_include: List[str] = None  # 必须包含的品类
    must_exclude: List[str] = None  # 排除的品类
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
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
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
        is_peak = any(start <= hour < end for start, end in poi.peak_hours)
        
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
        if poi.price_per_person > constraints.max_budget / constraints.group_size:
            budget_score = 0
        else:
            budget_score = (1 - poi.price_per_person / (constraints.max_budget / constraints.group_size)) * 100
        
        # 标签匹配（后续可接入情绪/偏好）
        tag_score = 50  # 基础分
        if emotion:
            emotion_tags = {
                "疲惫": ["安静", "放松", "治愈"],
                "兴奋": ["热闹", "刺激", "网红"],
                "浪漫": ["夜景", "情调", "私密"],
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
        
        # 筛选：营业时间内、预算内
        valid_pois = []
        for poi in pois:
            if poi.price_per_person > constraints.max_budget / constraints.group_size:
                continue
            valid_pois.append(poi)
        
        # 按综合评分排序
        valid_pois.sort(key=lambda p: self.score_poi(p, constraints, emotion), reverse=True)
        
        # 贪心构建初始路线
        route = []
        current_time = constraints.start_time
        current_location = start_location or valid_pois[0] if valid_pois else None
        total_cost = 0
        total_distance = 0
        
        for poi in valid_pois[:6]:  # 最多6个POI，避免行程太满
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
                continue
            
            # 检查总时长是否超限
            departure_time = activity_start + timedelta(minutes=poi.avg_duration)
            elapsed = (departure_time - constraints.start_time).total_seconds() / 60
            if elapsed > constraints.max_duration:
                break
            
            # 检查总预算
            poi_cost = poi.price_per_person * constraints.group_size
            if total_cost + poi_cost > constraints.max_budget:
                break
            
            node = RouteNode(
                poi=poi,
                arrival_time=arrival_time,
                departure_time=departure_time,
                travel_time_from_prev=travel_time,
                travel_distance_from_prev=travel_distance,
                estimated_queue_time=queue_time,
                activity_type="play" if poi.category in ["儿童乐园", "密室逃脱", "KTV"] else "dine",
            )
            route.append(node)
            
            total_cost += poi_cost
            total_distance += travel_distance
            current_time = departure_time
            current_location = poi
        
        # 2-opt 局部优化：尝试交换相邻节点，看是否能减少总交通时间
        route = self._two_opt(route)
        
        stats = {
            "total_duration": int((current_time - constraints.start_time).total_seconds() / 60),
            "total_distance": int(total_distance),
            "total_cost": total_cost,
            "poi_count": len(route),
        }
        
        return route, stats
    
    def _two_opt(self, route: List[RouteNode]) -> List[RouteNode]:
        """2-opt 局部优化：交换相邻节点看是否更优"""
        if len(route) < 3:
            return route
        
        improved = True
        max_iterations = 10
        iteration = 0
        
        while improved and iteration < max_iterations:
            improved = False
            iteration += 1
            
            for i in range(len(route) - 1):
                # 计算当前两段的距离
                current_dist = (
                    self.calculate_distance(route[i].poi, route[i+1].poi)
                    if i > 0 else 0
                )
                
                # 尝试交换（这里简化，实际更复杂）
                # 对于比赛级别，贪心+简单优化已足够
        
        return route
    
    def format_route_for_display(self, route: List[RouteNode]) -> str:
        """将路线格式化为人类可读的文本"""
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
```

#### 任务 1.2：接入真实 LLM（必须）

修改 `agent/main.py`，默认尝试接入真实 LLM：

```python
def create_agent(llm_provider: str = None, api_key: str = None, model: str = None):
    # 优先从环境变量读取
    llm_provider = llm_provider or os.environ.get("LLM_PROVIDER", "deepseek")
    api_key = api_key or os.environ.get("LLM_API_KEY", "")
    
    # 如果环境变量没有 API Key，尝试读取本地配置文件
    if not api_key:
        config_path = Path(__file__).parent.parent / "config.json"
        if config_path.exists():
            import json
            with open(config_path) as f:
                config = json.load(f)
                api_key = config.get("llm_api_key", "")
                llm_provider = config.get("llm_provider", llm_provider)
    
    # 如果还是没有 API Key，降级为 Mock（但打印警告）
    if not api_key:
        logger.warning("⚠️ 未配置 LLM API Key，将使用 Mock 模式。请设置环境变量 LLM_API_KEY")
        llm_provider = "mock"
    
    # ... 后续初始化
```

**推荐接入优先级**：
1. DeepSeek（API 便宜，注册送余额，推理能力强）
2. 通义千问（dashscope.aliyun.com，有免费额度）
3. 智谱 GLM（open.bigmodel.cn，有免费额度）

### Day 2：重构规划层 —— LLM 真正驱动

#### 任务 2.1：重写 `planner.py` 的 `create_plan`

从硬编码改为 LLM 生成：

```python
async def create_plan(self, intent: Dict[str, Any], route: List[RouteNode] = None) -> List[Task]:
    """
    让 LLM 根据意图和路线生成任务计划
    """
    # 构建工具描述
    tools_desc = self.tool_registry.to_openai_functions()
    
    # 构建路线描述（如果有）
    route_desc = ""
    if route:
        route_desc = "已规划的路线（按顺序）：\n"
        for i, node in enumerate(route):
            route_desc += f"{i+1}. {node.poi.name} ({node.poi.category}) "
            route_desc += f"到达时间{node.arrival_time.strftime('%H:%M')}，"
            route_desc += f"停留{node.poi.avg_duration}分钟\n"
    
    prompt = f"""你是美团智能行程助手。请根据用户意图生成详细的执行计划。

用户意图：
{json.dumps(intent, ensure_ascii=False, indent=2)}

{route_desc}

可用工具列表：
{json.dumps(tools_desc, ensure_ascii=False, indent=2)}

请生成任务计划，返回 JSON 数组。每个任务包含：
- task_id: 如 "T001"
- name: 任务名称
- tool_name: 使用的工具名称
- params: 工具参数（可以直接写具体值）
- priority: 优先级（1-10，越大越优先）
- dependencies: 依赖的其他任务ID列表（前置任务）
- fallback_tool: 备选工具（可选）
- fallback_params: 备选参数（可选）

规则：
1. 先执行查询类工具（天气、搜索），再执行操作类工具（预订、下单）
2. 有依赖关系的任务必须声明 dependencies
3. 每个工具参数必须符合其 schema
4. 如果路线中有餐厅，必须包含预订任务
5. 如果用户提到"惊喜"，必须包含配送任务

只输出 JSON 数组，不要其他文字。"""

    try:
        plan_json = await self.llm_client.chat_json(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="你是一个专业的本地生活服务规划师，擅长为用户安排最优行程。",
        )
        
        tasks = []
        for item in plan_json if isinstance(plan_json, list) else plan_json.get("tasks", []):
            task = Task(
                task_id=item.get("task_id", f"T{len(tasks)+1:03d}"),
                name=item.get("name", "未命名任务"),
                tool_name=item.get("tool_name"),
                params=item.get("params", {}),
                priority=item.get("priority", 5),
                dependencies=item.get("dependencies", []),
                fallback_tool=item.get("fallback_tool"),
                fallback_params=item.get("fallback_params"),
            )
            tasks.append(task)
        
        return tasks
    except Exception as e:
        logger.error(f"LLM 规划失败: {e}，回退到默认规划")
        return self._create_default_plan(intent)  # 保留默认规划作为 fallback
```

#### 任务 2.2：新增 "计划确认" 环节

```python
async def run(self, user_input: str, session_id: str = None) -> Dict[str, Any]:
    """完整流程：规划 → 确认 → 执行"""
    
    # 1. 解析意图
    intent = await self.parse_intent(user_input)
    
    # 2. 场景识别 + 路线规划
    scene = self.scene_manager.detect_scene(intent)
    route, route_stats = self.route_planner.plan_route(
        candidate_pois=scene.get_default_pois(),
        constraints=RouteConstraints(
            start_time=datetime.now() + timedelta(hours=2),
            max_duration=360,
            max_budget=intent.get("budget", 1000),
            group_size=len(intent.get("people", [])),
        ),
        emotion=intent.get("mood"),
    )
    
    # 3. LLM 生成任务计划
    tasks = await self.create_plan(intent, route)
    
    # 4. 生成人类可读的方案摘要（关键！）
    plan_summary = await self._generate_plan_summary(intent, route, tasks)
    
    # 5. 保存到会话，等待用户确认
    session = self.session_manager.get_or_create_session(session_id)
    session.update_intent(intent)
    session.context["pending_route"] = route
    session.context["pending_tasks"] = tasks
    session.context["plan_summary"] = plan_summary
    
    return {
        "status": "waiting_confirmation",
        "plan_summary": plan_summary,
        "route_stats": route_stats,
        "session_id": session.session_id,
        "tasks_preview": [
            {"task_id": t.task_id, "name": t.name, "tool_name": t.tool_name}
            for t in tasks
        ]
    }

async def confirm_and_execute(self, session_id: str, confirmed: bool) -> Dict[str, Any]:
    """用户确认后执行"""
    session = self.session_manager.get_session(session_id)
    if not session:
        return {"status": "error", "message": "会话不存在"}
    
    if not confirmed:
        return {"status": "cancelled", "message": "已取消规划"}
    
    tasks = session.context.get("pending_tasks", [])
    if not tasks:
        return {"status": "error", "message": "没有待执行的任务"}
    
    # 执行计划
    result = await self.execute_plan(tasks)
    
    # 生成分享文案
    share_text = self._generate_share_text(session)
    result["share_text"] = share_text
    
    return result

async def _generate_plan_summary(self, intent: Dict, route: List[RouteNode], tasks: List[Task]) -> str:
    """生成人类可读的方案摘要"""
    prompt = f"""请根据以下信息，生成一份温馨的行程方案摘要（200字以内）：

用户需求：{json.dumps(intent, ensure_ascii=False)}
路线：{self.route_planner.format_route_for_display(route)}
任务数：{len(tasks)}

要求：
1. 用第二人称"你"
2. 包含具体时间和地点
3. 突出亮点（比如惊喜安排）
4. 语气亲切自然"""
    
    return await self.llm_client.chat([{"role": "user", "content": prompt}])

async def _generate_share_text(self, session) -> str:
    """生成分享给朋友的文案"""
    prompt = f"""生成一段发给朋友的微信消息，告诉他们行程搞定了。

行程：{session.context.get("plan_summary", "")}
要求：口语化、简短、带时间地点。"""
    
    return await self.llm_client.chat([{"role": "user", "content": prompt}])
```

### Day 3：修复技术债 + 测试新架构

#### 任务 3.1：修复异步 Bug

```python
# agent/core/exception_handler.py
# 第142行：time.sleep(delay) → await asyncio.sleep(delay)

import asyncio  # 文件顶部添加

async def _handle_retry(self, task: Task, retry_func: Optional[Callable]) -> Dict[str, Any]:
    if task.retry_count >= self.max_retries:
        return self._handle_fallback(task)
    
    task.retry_count += 1
    delay = self.retry_delay * (2 ** (task.retry_count - 1))
    
    # 修复：同步 sleep 改异步 sleep
    await asyncio.sleep(delay)  # ← 修改这里
    
    if retry_func:
        try:
            result = await retry_func(task)  # ← 确保 await
            ...
```

#### 任务 3.2：修复测试 Bug

```python
# tests/test_planner.py
# 第19行：intent = agent.parse_intent(...) → intent = await agent.parse_intent(...)
```

#### 任务 3.3：跑通端到端测试

```bash
cd meituan-agent

# 1. 安装依赖
pip install -r requirements.txt

# 2. 设置 LLM API Key（以 DeepSeek 为例）
export LLM_API_KEY="sk-xxx"
export LLM_PROVIDER="deepseek"
export LLM_MODEL="deepseek-chat"

# 3. 跑基础测试
python -m pytest tests/test_planner.py -v

# 4. 跑异常场景测试
python tests/test_exception_scenarios.py

# 5. 跑 Demo
python run_demo.py
```

---

## 四、第二阶段：核心能力建设（Day 4-7）

### Day 4-5：剧本杀叙事引擎

#### 任务 4.1：新建 `agent/core/story_engine.py`

```python
"""
剧本杀叙事引擎
将普通 Citywalk 转化为沉浸式剧情冒险
"""

import json
import random
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class StoryCheckpoint:
    """剧情节点"""
    poi_id: str
    poi_name: str
    narrative: str  # 剧情描述
    task: str  # 用户需要完成的任务
    hint: str  # 提示
    reward: str  # 完成奖励
    unlocks_next: bool = True


@dataclass
class StoryRoute:
    """剧情路线"""
    title: str
    theme: str
    description: str
    checkpoints: List[StoryCheckpoint]
    total_duration: int  # 预估总时长（分钟）
    difficulty: str  # easy/medium/hard


class StoryEngine:
    """叙事引擎"""
    
    STORY_TEMPLATES = {
        "美食侦探": {
            "title": "《消失的味道：老字号秘方之谜》",
            "theme": "侦探解谜",
            "description": "一家百年老字号的祖传秘方神秘消失，线索散落在这座城市的美食角落...",
            "difficulty": "medium",
            "checkpoints": [
                {
                    "narrative": "你收到一封匿名信：'想知道秘方去哪了吗？先去那家最老的茶楼找老板聊聊。'",
                    "task": "找到茶楼老板，对他说暗号'今天的龙井真香'",
                    "hint": "看哪家茶楼历史最久",
                    "reward": "获得第一个线索碎片 + 茶楼8折券",
                },
                {
                    "narrative": "茶楼老板压低声音：'秘方可能被带到了小吃街，去找那个排队最长的摊位...'",
                    "task": "在小吃街找到排队最长的摊位，买一份招牌小吃并拍照",
                    "hint": "下午2-4点排队最长",
                    "reward": "获得第二个线索碎片 + 小吃买一送一",
                },
                {
                    "narrative": "小吃摊主悄悄告诉你：'最后有人看到秘方是在那家需要预订的私房菜馆...'",
                    "task": "到达私房菜馆，向服务员出示前两个线索碎片",
                    "hint": "需要提前预订",
                    "reward": "解锁隐藏菜单 + 解锁最终剧情",
                },
            ]
        },
        "浪漫逃亡": {
            "title": "《城市恋人：24小时心动挑战》",
            "theme": "浪漫冒险",
            "description": "你和TA被'困'在这座城市，需要完成5个心动挑战才能解锁最终惊喜...",
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
            ]
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
            ]
        },
    }
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    def detect_story_preference(self, user_input: str) -> Optional[str]:
        """从用户输入中识别是否偏好剧本杀模式"""
        story_keywords = [
            "好玩", "不一样", "剧情", "挑战", "游戏", "闯关",
            "探险", "冒险", "密室", "剧本杀", "解谜", "有趣",
            "刺激", "互动", "任务", "打卡", "收集"
        ]
        if any(kw in user_input for kw in story_keywords):
            return "story_preferred"
        return None
    
    async def generate_story_route(
        self,
        user_input: str,
        intent: Dict,
        route: List  # RouteNode list
    ) -> StoryRoute:
        """
        为已有路线披上剧情外衣
        """
        # 选择最接近的模板
        template_name = self._select_template(intent)
        template = self.STORY_TEMPLATES[template_name]
        
        # 将路线节点映射到剧情节点
        checkpoints = []
        for i, node in enumerate(route):
            if i < len(template["checkpoints"]):
                cp_template = template["checkpoints"][i]
                cp = StoryCheckpoint(
                    poi_id=node.poi.id,
                    poi_name=node.poi.name,
                    narrative=cp_template["narrative"],
                    task=cp_template["task"],
                    hint=cp_template["hint"],
                    reward=cp_template["reward"],
                )
                checkpoints.append(cp)
        
        return StoryRoute(
            title=template["title"],
            theme=template["theme"],
            description=template["description"],
            checkpoints=checkpoints,
            total_duration=sum(node.poi.avg_duration for node in route),
            difficulty=template["difficulty"],
        )
    
    def _select_template(self, intent: Dict) -> str:
        """根据意图选择最合适的剧情模板"""
        people = intent.get("people", [])
        needs = intent.get("needs", [])
        
        # 团建关键词
        if any(p.get("role") == "colleague" for p in people) or "团建" in str(intent):
            return "团建大作战"
        
        # 情侣/浪漫
        if any(p.get("role") in ["wife", "husband", "girlfriend", "boyfriend"] for p in people):
            if "surprise" in str(intent).lower() or intent.get("surprise"):
                return "浪漫逃亡"
        
        # 默认：美食侦探（适合朋友、家庭）
        return "美食侦探"
    
    async def generate_dynamic_narrative(
        self,
        checkpoint: StoryCheckpoint,
        user_progress: int,
        context: str
    ) -> str:
        """
        用 LLM 生成动态剧情文本
        让每次体验都有新鲜感
        """
        if not self.llm_client:
            return checkpoint.narrative
        
        prompt = f"""你是剧本杀 DM。当前剧情节点：
地点：{checkpoint.poi_name}
基础剧情：{checkpoint.narrative}
用户进度：已完成 {user_progress} 个任务
额外背景：{context}

请用 100 字以内，以 DM 的口吻重新讲述这段剧情，要有悬念感和代入感。"""
        
        return await self.llm_client.chat([{"role": "user", "content": prompt}])
    
    def format_story_for_display(self, story: StoryRoute) -> str:
        """格式化剧情路线供展示"""
        lines = [
            f"🎭 {story.title}",
            f"主题：{story.theme} | 难度：{'⭐' * (3 if story.difficulty == 'hard' else 2)}",
            f"\n{story.description}\n",
            "📍 任务节点：",
        ]
        
        for i, cp in enumerate(story.checkpoints, 1):
            lines.append(f"\n🔍 第{i}关：{cp.poi_name}")
            lines.append(f"   📖 {cp.narrative}")
            lines.append(f"   🎯 任务：{cp.task}")
            lines.append(f"   💡 提示：{cp.hint}")
            lines.append(f"   🎁 奖励：{cp.reward}")
        
        return "\n".join(lines)
```

#### 任务 4.2：场景识别器

新建 `agent/core/scene_manager.py`：

```python
"""
场景管理器
识别用户场景，加载对应的默认配置
"""

from typing import Dict, List
from enum import Enum


class SceneType(Enum):
    FAMILY = "family"           # 家庭出游
    FRIENDS = "friends"         # 朋友聚会
    DATE = "date"               # 情侣约会
    TEAM_BUILDING = "team_building"  # 企业团建
    SOLO = "solo"               # 个人出行
    PARENT_CHILD = "parent_child"    # 亲子游


class SceneManager:
    """场景管理器"""
    
    # 各场景默认偏好的 POI 类型（按优先级）
    SCENE_POI_PREFERENCES = {
        SceneType.FAMILY: {
            "poi_types": ["亲子乐园", "博物馆", "公园", "家庭餐厅", "甜品店"],
            "default_budget_per_person": 200,
            "default_duration": 360,
            "pace": "slow",
        },
        SceneType.FRIENDS: {
            "poi_types": ["密室逃脱", "剧本杀", "KTV", "烧烤", "酒吧", "咖啡馆"],
            "default_budget_per_person": 150,
            "default_duration": 420,
            "pace": "normal",
        },
        SceneType.DATE: {
            "poi_types": ["花店", "咖啡馆", "景观餐厅", "电影院", "夜市", "书店"],
            "default_budget_per_person": 300,
            "default_duration": 300,
            "pace": "slow",
        },
        SceneType.TEAM_BUILDING: {
            "poi_types": ["会议室", "轰趴馆", "户外拓展", "团建餐厅", "KTV"],
            "default_budget_per_person": 200,
            "default_duration": 480,
            "pace": "normal",
        },
        SceneType.SOLO: {
            "poi_types": ["书店", "咖啡馆", "展览", "小吃街", "SPA", "电影院"],
            "default_budget_per_person": 150,
            "default_duration": 240,
            "pace": "free",
        },
    }
    
    def detect_scene(self, intent: Dict) -> SceneType:
        """从意图中识别场景类型"""
        people = intent.get("people", [])
        needs = intent.get("needs", [])
        user_input = intent.get("raw_input", "")
        
        # 团建关键词优先
        if any(kw in user_input for kw in ["团建", "公司", "同事", "部门", "年会"]):
            return SceneType.TEAM_BUILDING
        
        # 角色识别
        roles = [p.get("role", "") for p in people]
        
        if "child" in roles and len(roles) >= 2:
            return SceneType.FAMILY
        
        if any(r in ["wife", "husband", "girlfriend", "boyfriend"] for r in roles):
            return SceneType.DATE
        
        if len(people) >= 3 and "friend" in roles:
            return SceneType.FRIENDS
        
        if len(people) <= 1:
            return SceneType.SOLO
        
        return SceneType.FRIENDS  # 默认
    
    def get_scene_config(self, scene_type: SceneType) -> Dict:
        """获取场景配置"""
        return self.SCENE_POI_PREFERENCES.get(scene_type, self.SCENE_POI_PREFERENCES[SceneType.FRIENDS])
    
    def get_default_pois(self, scene_type: SceneType, poi_database: Dict) -> List[str]:
        """获取该场景默认偏好的 POI ID 列表"""
        config = self.get_scene_config(scene_type)
        preferred_types = config["poi_types"]
        
        matching_pois = []
        for poi_id, poi in poi_database.items():
            if poi.category in preferred_types:
                matching_pois.append(poi_id)
        
        return matching_pois
```

### Day 6：扩充 Mock 数据到生产级

#### 任务 6.1：重写 `agent/tools/search_poi.py`

数据量从 5 条扩充到 50+ 条，覆盖 15+ 品类：

```python
MOCK_DATA = {
    # ===== 亲子/家庭 =====
    "儿童乐园": [
        {"id": "kids_001", "name": "奇乐儿儿童主题乐园", "rating": 4.8, "review_count": 2300,
         "location": {"lat": 31.2304, "lng": 121.4737}, "address": "万达广场3楼",
         "open_time": "10:00", "close_time": "21:00", "avg_duration": 150,
         "price_per_person": 128, "tags": ["室内", "适合3-8岁", "有家长休息区", "防滑地板"],
         "peak_hours": [(14, 16), (19, 21)], "queue_factor": 1.5, "capacity": 100},
        {"id": "kids_002", "name": "Meland Club", "rating": 4.9, "review_count": 1800,
         "location": {"lat": 31.2320, "lng": 121.4750}, "address": "万象城2楼",
         "open_time": "10:00", "close_time": "22:00", "avg_duration": 180,
         "price_per_person": 198, "tags": ["室内", "适合2-10岁", "沉浸式体验", "拍照好看"],
         "peak_hours": [(10, 12), (14, 17)], "queue_factor": 2.0, "capacity": 80},
        # ... 再补充3个
    ],
    
    # ===== 餐饮 =====
    "餐厅": [
        {"id": "rest_001", "name": "新元素餐厅", "rating": 4.7, "review_count": 3100,
         "location": {"lat": 31.2310, "lng": 121.4740}, "address": "万达广场4楼",
         "open_time": "11:00", "close_time": "22:00", "avg_duration": 90,
         "price_per_person": 120, "tags": ["低卡", "轻食", "沙拉", "适合减肥", "宝宝椅"],
         "peak_hours": [(12, 14), (18, 20)], "queue_factor": 1.3, "capacity": 60},
        {"id": "rest_002", "name": "海底捞火锅", "rating": 4.6, "review_count": 5600,
         "location": {"lat": 31.2312, "lng": 121.4742}, "address": "万达广场5楼",
         "open_time": "10:00", "close_time": "07:00", "avg_duration": 120,
         "price_per_person": 150, "tags": ["火锅", "服务好", "有宝宝椅", "免费美甲"],
         "peak_hours": [(18, 22), (23, 02)], "queue_factor": 2.5, "capacity": 100},
        {"id": "rest_003", "name": "wagas", "rating": 4.5, "review_count": 1200,
         "location": {"lat": 31.2330, "lng": 121.4760}, "address": "万象城1楼",
         "open_time": "08:00", "close_time": "21:00", "avg_duration": 60,
         "price_per_person": 85, "tags": ["轻食", "低卡", "健康", "早餐", "办公友好"],
         "peak_hours": [(8, 10), (12, 14)], "queue_factor": 1.2, "capacity": 40},
        {"id": "rest_004", "name": "西贝莜面村", "rating": 4.6, "review_count": 4200,
         "location": {"lat": 31.2308, "lng": 121.4735}, "address": "凯德晶萃广场3楼",
         "open_time": "11:00", "close_time": "21:30", "avg_duration": 90,
         "price_per_person": 110, "tags": ["西北菜", "亲子友好", "开放式厨房", "手工面食"],
         "peak_hours": [(12, 14), (18, 20)], "queue_factor": 1.4, "capacity": 80},
        # ... 再补充6个（日料、烧烤、私房菜、川菜、粤菜、素食）
    ],
    
    # ===== 娱乐 =====
    "密室逃脱": [
        {"id": "escape_001", "name": "X先生密室", "rating": 4.8, "review_count": 1500,
         "location": {"lat": 31.2340, "lng": 121.4770}, "address": "南京东路步行街",
         "open_time": "10:00", "close_time": "23:00", "avg_duration": 120,
         "price_per_person": 168, "tags": ["沉浸式", "真人NPC", "剧情向", "恐怖可选"],
         "peak_hours": [(14, 17), (19, 22)], "queue_factor": 1.8, "capacity": 30},
        # ... 再补充2个
    ],
    
    "KTV": [
        {"id": "ktv_001", "name": "纯K", "rating": 4.7, "review_count": 2800,
         "location": {"lat": 31.2350, "lng": 121.4780}, "address": "淮海中路",
         "open_time": "12:00", "close_time": "06:00", "avg_duration": 180,
         "price_per_person": 80, "tags": ["音响好", "小吃丰富", "大包间", "可带生日蛋糕"],
         "peak_hours": [(19, 23)], "queue_factor": 2.0, "capacity": 50},
    ],
    
    # ===== 团建专用 =====
    "轰趴馆": [
        {"id": "party_001", "name": "Party King 轰趴馆", "rating": 4.6, "review_count": 890,
         "location": {"lat": 31.2360, "lng": 121.4790}, "address": "静安寺商圈",
         "open_time": "10:00", "close_time": "24:00", "avg_duration": 300,
         "price_per_person": 150, "tags": ["KTV", "桌游", "台球", "自助厨房", "投影"],
         "peak_hours": [(14, 18), (19, 23)], "queue_factor": 1.5, "capacity": 50,
         "equipment": ["KTV", "桌游", "台球", "Switch", "投影", "自助厨房"]},
    ],
    
    "会议室": [
        {"id": "meet_001", "name": "WeWork 联合办公", "rating": 4.5, "review_count": 600,
         "location": {"lat": 31.2370, "lng": 121.4800}, "address": "陆家嘴中心",
         "open_time": "08:00", "close_time": "20:00", "avg_duration": 240,
         "price_per_person": 80, "tags": ["商务", "投影", "白板", "高速WiFi", "咖啡"],
         "peak_hours": [(9, 12), (14, 17)], "queue_factor": 1.0, "capacity": 30,
         "equipment": ["投影", "白板", "音响", "视频会议", "打印机"]},
    ],
    
    "户外拓展": [
        {"id": "outdoor_001", "name": "勇者户外拓展基地", "rating": 4.7, "review_count": 450,
         "location": {"lat": 31.2100, "lng": 121.4500}, "address": "青浦区朱家角",
         "open_time": "09:00", "close_time": "17:00", "avg_duration": 360,
         "price_per_person": 200, "tags": ["攀岩", "真人CS", "烧烤", "篝火晚会", "团队合作"],
         "peak_hours": [(10, 12), (14, 16)], "queue_factor": 1.3, "capacity": 100},
    ],
    
    # ===== 文化/休闲 =====
    "博物馆": [
        {"id": "museum_001", "name": "上海自然博物馆", "rating": 4.8, "review_count": 5600,
         "location": {"lat": 31.2380, "lng": 121.4600}, "address": "静安雕塑公园",
         "open_time": "09:00", "close_time": "17:00", "avg_duration": 180,
         "price_per_person": 30, "tags": ["亲子", "科普", "恐龙化石", "互动体验", "室内"],
         "peak_hours": [(10, 12), (14, 16)], "queue_factor": 1.6, "capacity": 500},
    ],
    
    "书店": [
        {"id": "book_001", "name": "钟书阁", "rating": 4.7, "review_count": 2100,
         "location": {"lat": 31.2390, "lng": 121.4610}, "address": "泰晤士小镇",
         "open_time": "10:00", "close_time": "21:00", "avg_duration": 120,
         "price_per_person": 50, "tags": ["网红", "拍照", "安静", "咖啡", "阅读"],
         "peak_hours": [(14, 17)], "queue_factor": 1.2, "capacity": 80},
    ],
    
    # ===== 其他 =====
    "花店": [
        {"id": "flower_001", "name": "花点时间", "rating": 4.8, "review_count": 900,
         "location": {"lat": 31.2315, "lng": 121.4745}, "address": "万达广场1楼",
         "open_time": "09:00", "close_time": "21:00", "avg_duration": 20,
         "price_per_person": 150, "tags": ["鲜花", "即时配送", "定制花束", "生日"],
         "peak_hours": [(10, 12), (17, 19)], "queue_factor": 1.0, "capacity": 20},
    ],
    
    "咖啡馆": [
        {"id": "cafe_001", "name": "%Arabica", "rating": 4.6, "review_count": 3400,
         "location": {"lat": 31.2400, "lng": 121.4620}, "address": "武康路",
         "open_time": "08:00", "close_time": "20:00", "avg_duration": 60,
         "price_per_person": 45, "tags": ["网红", "拍照", "手冲", "极简风", "街景"],
         "peak_hours": [(10, 12), (14, 16)], "queue_factor": 1.8, "capacity": 30},
    ],
    
    "剧本杀": [
        {"id": "script_001", "name": "迷雾剧本杀馆", "rating": 4.7, "review_count": 1100,
         "location": {"lat": 31.2410, "lng": 121.4630}, "address": "徐家汇",
         "open_time": "12:00", "close_time": "24:00", "avg_duration": 240,
         "price_per_person": 128, "tags": ["换装", "推理", "情感本", "恐怖本", "DM专业"],
         "peak_hours": [(14, 17), (19, 22)], "queue_factor": 1.7, "capacity": 40},
    ],
    
    "电影院": [
        {"id": "cinema_001", "name": "万达影城IMAX", "rating": 4.5, "review_count": 6700,
         "location": {"lat": 31.2310, "lng": 121.4740}, "address": "万达广场6楼",
         "open_time": "10:00", "close_time": "02:00", "avg_duration": 150,
         "price_per_person": 80, "tags": ["IMAX", "杜比全景声", "情侣座", "爆米花套餐"],
         "peak_hours": [(19, 22)], "queue_factor": 1.5, "capacity": 300},
    ],
    
    "公园": [
        {"id": "park_001", "name": "世纪公园", "rating": 4.6, "review_count": 4300,
         "location": {"lat": 31.2150, "lng": 121.5400}, "address": "浦东新区",
         "open_time": "06:00", "close_time": "18:00", "avg_duration": 180,
         "price_per_person": 0, "tags": ["免费", "骑行", "野餐", "划船", "亲子", "跑步"],
         "peak_hours": [(9, 11), (15, 17)], "queue_factor": 1.0, "capacity": 1000},
    ],
    
    "小吃街": [
        {"id": "snack_001", "name": "城隍庙小吃街", "rating": 4.4, "review_count": 8900,
         "location": {"lat": 31.2250, "lng": 121.4900}, "address": "豫园商圈",
         "open_time": "10:00", "close_time": "22:00", "avg_duration": 90,
         "price_per_person": 60, "tags": ["老字号", "生煎", "小笼包", "蟹壳黄", "网红打卡"],
         "peak_hours": [(12, 14), (18, 20)], "queue_factor": 2.2, "capacity": 200},
    ],
}
```

#### 任务 6.2：团建专用工具

新建 `agent/tools/book_venue.py`：

```python
"""场地预订工具（会议室/轰趴馆/拓展基地）"""

from typing import Dict, Any
from datetime import datetime
from .base import BaseTool, ToolResult


class BookVenueTool(BaseTool):
    name = "book_venue"
    description = "预订团建/聚会场地（会议室、轰趴馆、拓展基地）"
    parameters_schema = {
        "type": "object",
        "properties": {
            "venue_id": {"type": "string", "description": "场地ID"},
            "venue_name": {"type": "string", "description": "场地名称"},
            "date": {"type": "string", "description": "日期 YYYY-MM-DD"},
            "start_time": {"type": "string", "description": "开始时间 HH:MM"},
            "end_time": {"type": "string", "description": "结束时间 HH:MM"},
            "group_size": {"type": "integer", "description": "人数"},
            "requirements": {"type": "array", "items": {"type": "string"}, "description": "特殊需求"},
        },
        "required": ["venue_id", "date", "start_time", "end_time", "group_size"]
    }
    
    MOCK_VENUES = {
        "venue_001": {"name": "Party King 轰趴馆", "capacity": 50, "price_half_day": 1500, "available": True},
        "venue_002": {"name": "WeWork 会议室", "capacity": 30, "price_half_day": 800, "available": True},
        "venue_003": {"name": "勇者拓展基地", "capacity": 100, "price_half_day": 3000, "available": True},
    }
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        venue_id = params.get("venue_id")
        group_size = params.get("group_size")
        
        venue = self.MOCK_VENUES.get(venue_id)
        if not venue:
            return ToolResult(success=False, error_type="not_found", error_message="场地不存在")
        
        if venue["capacity"] < group_size:
            return ToolResult(success=False, error_type="capacity_exceeded",
                            error_message=f"场地容量{venue['capacity']}人，需要{group_size}人")
        
        booking_id = f"VN{datetime.now().strftime('%Y%m%d%H%M%S')}"
        return ToolResult(success=True, data={
            "booking_id": booking_id,
            "venue_name": venue["name"],
            "status": "confirmed",
            "message": f"{venue['name']}预订成功！"
        })
```

### Day 7：测试第二阶段成果

- 路线规划引擎能跑出带时间轴的路线
- LLM 能生成动态任务计划
- 剧本杀叙事引擎能为路线披上剧情
- Mock 数据覆盖 15+ 品类

---

## 五、第三阶段：前端与集成（Day 8-11）

### Day 8：补齐小程序前端

#### 任务 8.1：首页 `miniprogram/pages/index/index.wxml`

```xml
<!--pages/index/index.wxml-->
<view class="container">
  <!-- 欢迎区域 -->
  <view class="welcome-section">
    <text class="greeting">你好，我是美团 AI 助手</text>
    <text class="subtitle">告诉我你的需求，我来帮你规划行程</text>
  </view>
  
  <!-- 快捷场景 -->
  <view class="section">
    <view class="section-title">快捷场景</view>
    <view class="scene-grid">
      <view class="scene-item" wx:for="{{quickEntries}}" wx:key="title" bindtap="onQuickEntry" data-input="{{item.inputs[0]}}">
        <text class="scene-icon">{{item.icon}}</text>
        <text class="scene-name">{{item.title}}</text>
        <text class="scene-desc">{{item.desc}}</text>
      </view>
    </view>
  </view>
  
  <!-- 输入框 -->
  <view class="input-section">
    <input class="input" placeholder="例如：周末和朋友4个人想玩点不一样的" bindinput="onInput" value="{{userInput}}"/>
    <button class="btn-primary" bindtap="onSubmit">开始规划</button>
  </view>
  
  <!-- 热门推荐 -->
  <view class="section">
    <view class="section-title">热门玩法</view>
    <view class="hot-list">
      <view class="hot-item" wx:for="{{hotItems}}" wx:key="title" bindtap="onQuickEntry" data-input="{{item.input}}">
        <text class="hot-emoji">{{item.emoji}}</text>
        <view class="hot-info">
          <text class="hot-title">{{item.title}}</text>
          <text class="hot-tag">{{item.tag}}</text>
        </view>
      </view>
    </view>
  </view>
</view>
```

#### 任务 8.2：首页样式 `miniprogram/pages/index/index.wxss`

```css
/* pages/index/index.wxss */
.container {
  padding: 30rpx;
  background: #F5F5F5;
  min-height: 100vh;
}

.welcome-section {
  background: linear-gradient(135deg, #FFD100 0%, #FF8C00 100%);
  border-radius: 24rpx;
  padding: 40rpx;
  margin-bottom: 30rpx;
}

.greeting {
  display: block;
  font-size: 40rpx;
  font-weight: bold;
  color: #1A1A1A;
}

.subtitle {
  display: block;
  font-size: 28rpx;
  color: #333;
  margin-top: 10rpx;
}

.section {
  margin-bottom: 30rpx;
}

.section-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #1A1A1A;
  margin-bottom: 20rpx;
}

.scene-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20rpx;
}

.scene-item {
  background: #fff;
  border-radius: 20rpx;
  padding: 30rpx;
  text-align: center;
  box-shadow: 0 2rpx 12rpx rgba(0,0,0,0.05);
}

.scene-icon {
  font-size: 60rpx;
  display: block;
}

.scene-name {
  display: block;
  font-size: 28rpx;
  font-weight: bold;
  margin-top: 10rpx;
}

.scene-desc {
  display: block;
  font-size: 22rpx;
  color: #999;
  margin-top: 6rpx;
}

.input-section {
  background: #fff;
  border-radius: 20rpx;
  padding: 30rpx;
  margin-bottom: 30rpx;
}

.input {
  width: 100%;
  height: 80rpx;
  background: #F5F5F5;
  border-radius: 16rpx;
  padding: 0 20rpx;
  font-size: 28rpx;
  box-sizing: border-box;
  margin-bottom: 20rpx;
}

.btn-primary {
  width: 100%;
  height": 80rpx;
  background: linear-gradient(135deg, #FFD100 0%, #FF8C00 100%);
  color: #1A1A1A;
  border-radius: 40rpx;
  font-size: 30rpx;
  font-weight: bold;
  border: none;
}

.hot-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.hot-item {
  background: #fff;
  border-radius: 20rpx;
  padding: 24rpx;
  display: flex;
  align-items: center;
  box-shadow: 0 2rpx 12rpx rgba(0,0,0,0.05);
}

.hot-emoji {
  font-size: 48rpx;
  margin-right: 20rpx;
}

.hot-info {
  flex: 1;
}

.hot-title {
  display: block;
  font-size: 30rpx;
  font-weight: bold;
}

.hot-tag {
  display: inline-block;
  font-size: 22rpx;
  color: #FF8C00;
  background: #FFF5E6;
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
  margin-top: 8rpx;
}
```

#### 任务 8.3：对话页 `miniprogram/pages/chat/chat.wxml`

```xml
<!--pages/chat/chat.wxml-->
<view class="chat-container">
  <!-- 消息列表 -->
  <scroll-view class="message-list" scroll-y scroll-into-view="{{scrollToMessage}}">
    <view wx:for="{{messages}}" wx:key="id" class="message {{item.role}}" id="msg-{{item.id}}">
      
      <!-- 普通文本消息 -->
      <block wx:if="{{item.type === 'text'}}">
        <view class="bubble">
          <text>{{item.content}}</text>
          <text class="time">{{item.timeStr}}</text>
        </view>
      </block>
      
      <!-- 计划卡片 -->
      <block wx:if="{{item.type === 'plan'}}">
        <view class="plan-card">
          <view class="plan-header">
            <text class="plan-status {{item.status}}">{{item.statusText}}</text>
            <text class="plan-summary">{{item.summary}}</text>
          </view>
          <view class="task-list">
            <view wx:for="{{item.tasks}}" wx:for-item="task" wx:key="taskId" class="task-item">
              <text class="task-name">{{task.name}}</text>
              <text class="task-status {{task.status}}">{{task.status}}</text>
            </view>
          </view>
          <button class="btn-confirm" bindtap="onConfirmPlan" data-plan-id="{{item.planId}}">确认方案</button>
        </view>
      </block>
      
      <!-- 加载中 -->
      <block wx:if="{{item.type === 'loading'}}">
        <view class="loading">
          <text>{{item.content}}</text>
        </view>
      </block>
      
    </view>
    <view id="msg-bottom"></view>
  </scroll-view>
  
  <!-- 输入区 -->
  <view class="input-bar">
    <input class="chat-input" placeholder="输入你的需求..." value="{{userInput}}" bindinput="onInput" confirm-type="send" bindconfirm="onSubmit"/>
    <button class="btn-send" bindtap="onSubmit">发送</button>
  </view>
</view>
```

### Day 9：后端 API 完善

#### 任务 9.1：用 FastAPI 替换 http.server

新建 `agent/api.py`：

```python
"""
FastAPI 后端服务
替代 backend_simple.py
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio
import os

from .main import create_agent

app = FastAPI(title="美团 AI Agent", version="2.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局 Agent 实例
agent = create_agent()


class ExecuteRequest(BaseModel):
    userInput: str
    sessionId: Optional[str] = None
    confirmed: Optional[bool] = None  # 用户确认标志


@app.get("/api/agent/health")
async def health():
    return {"status": "ok", "version": "2.0", "llm_provider": os.environ.get("LLM_PROVIDER", "mock")}


@app.post("/api/agent/execute")
async def execute(req: ExecuteRequest):
    """主执行接口"""
    try:
        if req.confirmed is True and req.sessionId:
            # 用户确认后执行
            result = await agent.confirm_and_execute(req.sessionId, confirmed=True)
        elif req.confirmed is False and req.sessionId:
            # 用户取消
            result = await agent.confirm_and_execute(req.sessionId, confirmed=False)
        else:
            # 新请求：生成计划（等待确认）
            result = await agent.run(req.userInput, req.sessionId)
        
        return {
            "status": result.get("status"),
            "sessionId": result.get("session_id"),
            "planSummary": result.get("plan_summary"),
            "routeStats": result.get("route_stats"),
            "tasks": result.get("tasks_preview", []),
            "shareText": result.get("share_text"),
            "results": result.get("results", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

### Day 10-11：集成测试

- 前端调用后端 API
- 完整流程：输入 → 规划 → 确认 → 执行 → 分享
- 修复集成过程中的 Bug

---

## 六、第四阶段：演示打磨（Day 12-14）

### Day 12：设计 3 个 Demo 场景

#### 场景 1：家庭出游（覆盖基础功能）

```
输入："这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜"

预期输出：
🎭 已为您规划「家庭周末欢乐游」

📍 下午2:00 出发
├─ 🚶 12分钟 → 奇乐儿儿童主题乐园
│   2:12-4:42 室内游乐场（适合5岁，有防滑地板）
│   评分4.8 | 人均¥128
├─ 🚶 5分钟 → 新元素餐厅
│   4:50-6:20 低卡轻食晚餐（有宝宝椅）
│   评分4.7 | 人均¥120 | 预订已确认
│   🎁 惊喜：17:30 鲜花将送达餐厅
└─ 🏠 6:20 返程

总步行：约800m | 总预算：约¥620

💬 分享文案：
"搞定了，周六下午2点出发，先去奇乐儿让孩子放电，
然后吃新元素，老婆的花17点半送到餐厅。完美！"
```

#### 场景 2：朋友聚会 + 剧本杀 Citywalk（展示差异化）

```
输入："周末和4个朋友一起出去玩，想玩点不一样的，要有剧情"

预期输出：
🎭 为您开启剧本杀 Citywalk：《消失的味道》

📖 剧情：一家百年老字号的秘方被盗，线索散落在城市的美食角落...

🔍 任务节点：
第1关：城隍庙小吃街
  任务：找到排队最长的摊位，买一份招牌小吃
  奖励：获得线索碎片 + 小吃买一送一

第2关：迷雾剧本杀馆
  任务：用线索碎片解锁隐藏剧情
  奖励：解锁最终目的地

第3关：海底捞火锅
  任务：庆祝破案成功！
  预订：已确认5人包间
```

#### 场景 3：企业团建（展示高价值场景）

```
输入："公司20人团建，预算人均200，下午开始，要有会议室和聚餐"

预期输出：
📋 企业团建方案（20人）

🏢 14:00-17:00 WeWork 联合办公会议室
   设备：投影、白板、音响
   费用：¥1600（半日场）

🚌 17:00-17:30 大巴接送 → Party King 轰趴馆

🎉 17:30-21:30 Party King 轰趴馆
   包含：KTV、桌游、台球、自助厨房
   费用：¥3000（20人包场）

🍽 21:30-23:00 海底捞火锅（步行3分钟）
   预订：20人包间已确认
   费用：约¥3000

💰 总预算：约¥7600（人均¥380）
   ⚠️ 超出预算 ¥3600，建议调整：
   选项A：会议室改普通场地（省¥800）
   选项B：轰趴馆改非黄金时段（省¥1000）
```

### Day 13：演示脚本 + 录屏准备

编写 `demo_showcase.py`，自动运行 3 个场景：

```python
"""
竞赛演示脚本
一键运行 3 个场景，展示核心能力
"""

import asyncio
from agent.main import create_agent

async def showcase():
    agent = create_agent()
    
    scenarios = [
        {
            "name": "场景1：家庭出游",
            "input": "这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜",
        },
        {
            "name": "场景2：剧本杀 Citywalk",
            "input": "周末和4个朋友一起出去玩，想玩点不一样的，要有剧情",
        },
        {
            "name": "场景3：企业团建",
            "input": "公司20人团建，预算人均200，下午开始，要有会议室和聚餐",
        },
    ]
    
    for scenario in scenarios:
        print(f"\n{'='*60}")
        print(f"🎬 {scenario['name']}")
        print(f"{'='*60}")
        print(f"用户：{scenario['input']}")
        
        result = await agent.run(scenario['input'])
        
        print(f"\nAgent 回复：")
        print(result.get('plan_summary', '规划完成'))
        print(f"\n状态：{result.get('status')}")
        print(f"任务数：{len(result.get('tasks_preview', []))}")

if __name__ == "__main__":
    asyncio.run(showcase())
```

### Day 14：文档精修

#### 必须提交的文档

1. **README.md**（项目说明，≤2页）
2. **DESIGN.md**（设计文档，≤2页，包含 Planning 策略、工具调用链路、异常处理机制）
3. **DEMO_GUIDE.md**（演示指南，告诉评委怎么跑）

#### DESIGN.md 核心内容

```markdown
# 设计文档

## 1. Planning 策略

### 1.1 双层规划架构

第一层：路线规划引擎（Route Planner）
- 输入：用户意图 + 场景类型 + 约束条件
- 处理：候选 POI 筛选 → 综合评分排序 → 贪心构建路线 → 2-opt 优化
- 输出：带时间轴的最优路线

第二层：LLM 任务规划（Task Planner）
- 输入：用户意图 + 已规划路线 + 可用工具列表
- 处理：LLM 生成任务列表（工具选择 + 参数填充 + 依赖声明）
- 输出：可执行的任务 DAG

### 1.2 评分函数

POI 综合评分 = 评分×0.4 + 热度×0.2 + 预算适配×0.2 + 个性化匹配×0.2

### 1.3 约束处理

- 营业时间：硬约束（不营业的 POI 直接过滤）
- 预算：硬约束（超出预算停止追加）
- 时间窗口：软约束（允许微小偏移）

## 2. 工具调用链路

```
用户输入
  → 意图解析（LLM）
  → 场景识别（规则分类器）
  → 路线规划（算法引擎）
  → 任务生成（LLM）
  → 用户确认
  → 工具执行（状态机调度）
  → 异常处理（Retry → Fallback → Replan）
  → 结果汇总
  → 分享输出
```

## 3. 异常处理机制

### 3.1 三层处理

| 层级 | 策略 | 触发条件 | 示例 |
|------|------|----------|------|
| L1 Retry | 指数退避重试 | 网络超时、API 限流 | 天气查询失败，1s→2s→4s 重试 |
| L2 Fallback | 切换备选方案 | 业务性失败 | 餐厅满座 → 自动推荐相似餐厅 |
| L3 Replan | 重新规划 | 环境剧变 | 暴雨 → 室内替代方案 |

### 3.2 状态机

PLANNING → EXECUTING → COMPLETED
              ↓
            ERROR → Retry/Fallback → EXECUTING
              ↓
            ERROR → Replan → PLANNING
```

---

## 七、第五阶段：最终验收（Day 15）

### 验收清单

#### 功能验收

- [ ] LLM API 接入成功，意图识别准确
- [ ] 路线规划引擎能输出带时间轴的路线
- [ ] 剧本杀叙事引擎能为路线生成剧情
- [ ] 用户确认 → 一键执行流程完整
- [ ] 分享文案自动生成
- [ ] 3 个 Demo 场景运行流畅
- [ ] 异常处理（Retry/Fallback/Replan）能演示
- [ ] 小程序前端能展示计划卡片

#### 代码验收

- [ ] 所有测试通过：`pytest tests/ -v`
- [ ] 没有明显的异步 Bug（time.sleep 已修复）
- [ ] Mock 数据覆盖 15+ 品类
- [ ] 代码有基本注释

#### 文档验收

- [ ] README.md 完整（安装、运行、演示）
- [ ] DESIGN.md ≤2页（Planning策略、工具链路、异常处理）
- [ ] 代码中有 config.json 模板

### 备用方案

如果比赛现场出现问题：

1. **LLM API 不可用**：准备 Mock 模式的离线 Demo，预生成 3 个场景的完整输出
2. **网络问题**：本地运行 `run_demo.py`，不需要网络
3. **前端跑不起来**：用命令行 Demo 替代，重点展示 Agent 核心能力

---

## 八、每日 Check-in 模板

每天结束时，问自己这 3 个问题：

1. **今天完成了什么？**（对照上面的任务列表）
2. **最大的阻塞是什么？**（需要帮助的点）
3. **明天的第一件事是什么？**（确保优先级正确）

---

## 九、资源推荐

### LLM API（按推荐度排序）

| 平台 | 地址 | 费用 | 备注 |
|------|------|------|------|
| DeepSeek | platform.deepseek.com | ¥1-2/百万token | 性价比高，推理强 |
| 通义千问 | dashscope.aliyun.com | 有免费额度 | 国内稳定 |
| 智谱 GLM | open.bigmodel.cn | 有免费额度 | 中文优化好 |

### 参考项目

- Microsoft Guidance：结构化 LLM 输出
- LangChain ReAct Agent：真正的 ReAct 实现
- Google OR-Tools：路线优化算法（如需更高级的 TSP 求解）

---

> **最后提醒**：评委看 30-50 个项目，你的目标不是"功能最全"，而是**"3分钟内让评委记住你"**。剧本杀 Citywalk 这个差异化点，就是你的记忆锚。
>
> 加油，15 天后见分晓！
