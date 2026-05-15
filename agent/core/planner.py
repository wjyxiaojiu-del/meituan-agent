"""
规划引擎模块
实现 ReAct (Reasoning + Acting) 架构的规划引擎
支持多轮对话和上下文理解
"""

import json
import re
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from .state_machine import StateMachine, Task, TaskStatus, AgentState
from .exception_handler import ExceptionHandler
from .session import SessionManager, ConversationState, ContextBuilder
from ..tools.base import ToolRegistry, ToolResult
from ..llm.client import LLMClient
from ..llm.prompts import IntentPrompts

logger = logging.getLogger(__name__)


class Planner:
    """
    ReAct 规划引擎
    负责理解用户意图、拆解任务、规划执行顺序
    支持多轮对话和上下文理解
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        state_machine: StateMachine = None,
        exception_handler: ExceptionHandler = None,
        llm_client: Optional[LLMClient] = None,
        session_manager: Optional[SessionManager] = None,
        route_planner=None,
        scene_manager=None,
        story_engine=None,
    ):
        self.tool_registry = tool_registry
        # state_machine/exception_handler 仅供外部测试直接访问；
        # execute_plan() 使用局部实例，不依赖这两个属性。
        self.state_machine = state_machine or StateMachine()
        self.exception_handler = exception_handler or ExceptionHandler(self.state_machine)
        self.llm_client = llm_client or LLMClient()
        self.session_manager = session_manager or SessionManager()
        self.route_planner = route_planner
        self.scene_manager = scene_manager
        self.story_engine = story_engine

    async def parse_intent(
        self,
        user_input: str,
        session: Optional[ConversationState] = None
    ) -> Dict[str, Any]:
        """
        解析用户意图
        使用 LLM 进行意图识别，支持上下文理解

        Args:
            user_input: 用户输入
            session: 会话状态（可选）

        Returns:
            解析后的意图
        """
        logger.info(f"使用 LLM 解析意图: {user_input[:50]}...")

        # 构建消息
        if session:
            # 有会话上下文时，使用带历史的提示
            messages = ContextBuilder.build_context_for_intent(user_input, session)

            # 检测是否是修改请求
            is_modification = ContextBuilder.detect_modification_intent(user_input)
            if is_modification and session.current_intent:
                # 添加修改上下文
                modification_target = ContextBuilder.extract_modification_target(user_input)
                context_info = {
                    "is_modification": True,
                    "existing_intent": session.current_intent,
                    "modification_target": modification_target
                }
                # 在系统提示中添加修改上下文
                system_prompt = self._build_modification_system_prompt(context_info)
            else:
                system_prompt = IntentPrompts.SYSTEM_PROMPT
        else:
            messages = IntentPrompts.get_intent_prompt(user_input)
            system_prompt = IntentPrompts.SYSTEM_PROMPT

        # 调用 LLM
        intent = await self.llm_client.chat_json(
            messages=messages,
            system_prompt=system_prompt,
        )

        # 确保必要字段存在
        intent.setdefault("people", [])
        intent.setdefault("needs", [])
        intent.setdefault("constraints", [])
        intent.setdefault("surprise", False)

        # 如果没有识别到 "self"，自动添加
        if not any(p.get("role") == "self" for p in intent["people"]):
            intent["people"].append({"role": "self"})

        # 如果有会话，合并历史意图信息
        if session and session.current_intent:
            intent = self._merge_intent_with_history(intent, session.current_intent)

        logger.info(f"LLM 意图解析结果: {intent}")
        return intent

    def _build_modification_system_prompt(self, context_info: Dict[str, Any]) -> str:
        """构建修改请求的系统提示"""
        existing_intent = context_info.get("existing_intent", {})
        target = context_info.get("modification_target", "")

        base_prompt = IntentPrompts.SYSTEM_PROMPT
        modification_prompt = f"""

用户正在修改之前的规划。已有意图信息：
{json.dumps(existing_intent, ensure_ascii=False, indent=2)}

修改目标：{target}

请根据用户的新输入，更新意图信息。保留未修改的部分，只更新用户明确要修改的内容。
返回完整的更新后的意图 JSON。
"""

        return base_prompt + modification_prompt

    def _merge_intent_with_history(
        self,
        new_intent: Dict[str, Any],
        old_intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        合并新意图和历史意图
        数组类型去重合并（保留历史中未被新值覆盖的元素）
        标量类型：新值非空则覆盖
        """
        merged = old_intent.copy()

        # 数组字段：去重合并（按 role/need 等关键字段去重）
        for array_key in ("people", "needs", "constraints"):
            old_items = merged.get(array_key, [])
            new_items = new_intent.get(array_key, [])
            if not new_items:
                continue
            if not old_items:
                merged[array_key] = new_items
                continue
            # 合并：新值中出现的 key 覆盖旧值中相同 key 的元素
            if array_key == "people":
                old_roles = {p.get("role"): p for p in old_items if isinstance(p, dict)}
                for p in new_items:
                    if isinstance(p, dict):
                        old_roles[p.get("role")] = p
                merged[array_key] = list(old_roles.values())
            elif array_key == "needs":
                merged[array_key] = list(dict.fromkeys(old_items + new_items))
            elif array_key == "constraints":
                old_types = {c.get("type"): c for c in old_items if isinstance(c, dict)}
                for c in new_items:
                    if isinstance(c, dict):
                        old_types[c.get("type")] = c
                merged[array_key] = list(old_types.values())

        # 标量字段：新值非空则覆盖
        for scalar_key in ("surprise", "time_preference", "mood", "raw_input"):
            if scalar_key in new_intent and new_intent[scalar_key] is not None:
                merged[scalar_key] = new_intent[scalar_key]

        return merged

    async def create_plan(self, intent: Dict[str, Any]):
        """
        根据意图创建执行计划

        流程：
        1. 路线规划引擎选出最优 POI 顺序
        2. LLM 根据路线 + 工具列表生成任务计划
        3. LLM 失败时回退到规则引擎
        4. 后处理：保证天气任务始终存在

        Returns:
            (tasks, route) 二元组
        """
        # === 第一步：路线规划 ===
        route = None
        route_desc = ""
        if self.route_planner:
            route, route_stats = self._plan_route_from_intent(intent)
            if route:
                route_desc = self.route_planner.format_route_for_display(route)
                logger.info(f"路线规划完成: {route_stats['poi_count']} 个节点")

        # === 第二步：LLM 生成任务计划 ===
        tasks = await self._llm_create_plan(intent, route, route_desc)
        if not tasks:
            # === 第三步：LLM 失败，回退到规则引擎 ===
            logger.warning("LLM 规划失败，回退到规则引擎")
            tasks = self._rule_based_plan(intent)

        # === 第四步：后处理 ===
        tasks = self._ensure_weather_task(tasks, intent)

        return tasks, route

    def _ensure_weather_task(self, tasks: List[Task], intent: Dict[str, Any]) -> List[Task]:
        """保证天气查询任务始终存在，且排在最前面（不重排已有 ID，避免破坏依赖引用）"""
        has_weather = any(t.tool_name == "weather_api" for t in tasks)
        if has_weather:
            # 确保天气任务排在第一位
            weather_tasks = [t for t in tasks if t.tool_name == "weather_api"]
            other_tasks = [t for t in tasks if t.tool_name != "weather_api"]
            return weather_tasks + other_tasks

        # 没有天气任务，在最前面插入一个（用 W001 避免与已有 T00X 冲突）
        weather_task = Task(
            task_id="W001",
            name="查询天气",
            tool_name="weather_api",
            params={"date": datetime.now().strftime("%Y-%m-%d"), "time": "14:00"},
            priority=10,
        )
        return [weather_task] + tasks

    def _plan_route_from_intent(self, intent: Dict[str, Any]):
        """根据意图调用路线规划引擎"""
        from .route_planner import RouteConstraints

        people = intent.get("people", [])

        # 用 SceneManager 识别场景，选择候选 POI
        if self.scene_manager:
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
                budget = c.get("max") or 1000  # None 时回退默认值

        constraints = RouteConstraints(
            start_time=datetime.now().replace(hour=14, minute=0, second=0, microsecond=0),
            max_duration=default_duration,
            max_budget=budget,
            group_size=max(group_size, 1),
            transport_mode="walk",
        )

        route, stats = self.route_planner.plan_route(
            candidate_pois=candidates,
            constraints=constraints,
            emotion=intent.get("mood"),
        )
        return route, stats

    async def _llm_create_plan(
        self, intent: Dict[str, Any], route, route_desc: str
    ) -> List[Task]:
        """让 LLM 根据意图和路线生成任务计划"""
        if not self.llm_client or not self.llm_client.is_available():
            return []

        tools_desc = self.tool_registry.to_openai_functions()

        prompt = f"""你是美团智能行程助手。请根据用户意图生成详细的执行计划。

用户意图：
{json.dumps(intent, ensure_ascii=False, indent=2)}

{f"已规划路线（按顺序）：\\n{route_desc}" if route_desc else "暂无路线规划，请根据意图自行安排。"}

可用工具列表：
{json.dumps(tools_desc, ensure_ascii=False, indent=2)}

请生成任务计划，返回 JSON 数组。每个任务包含：
- task_id: 如 "T001"
- name: 任务名称
- tool_name: 使用的工具名称
- params: 工具参数（必须符合工具的 parameters_schema）
- priority: 优先级（1-10，越大越优先）
- dependencies: 依赖的其他任务ID列表
- fallback_tool: 备选工具（可选）
- fallback_params: 备选参数（可选）

【极其重要】参数引用规则：
当任务 B 依赖任务 A 的搜索结果时，B 的参数中引用 A 结果的字段必须用以下格式：
  {{T00X.results[0].字段名}}
其中 T00X 是被依赖任务的 task_id。

示例（你必须严格遵守此格式）：
  T001: {{"task_id":"T001","name":"搜索餐厅","tool_name":"search_poi","params":{{"category":"餐厅"}},"priority":8,"dependencies":[]}}
  T002: {{"task_id":"T002","name":"预订餐厅","tool_name":"book_restaurant","params":{{"restaurant_id":"{{T001.results[0].id}}","time":"17:00","party_size":3}},"priority":6,"dependencies":["T001"]}}

注意：restaurant_id 的值是字符串 "{{T001.results[0].id}}"，不是 R001 之类的假 ID！

规则：
1. 先执行查询类工具（天气、搜索），再执行操作类工具（预订、下单）
2. 有依赖关系的任务必须声明 dependencies
3. 预订/排队等操作类任务的 restaurant_id 必须用 {{{{T00X.results[0].id}}}} 引用搜索结果
4. 如果路线中有餐厅，必须包含预订任务
5. 如果用户提到"惊喜"，必须包含配送任务
6. 如果有儿童，搜索时加上年龄关键词
7. party_size 从意图的 people 数组长度获取

只输出 JSON 数组，不要其他文字。"""

        try:
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="你是一个专业的本地生活服务规划师，擅长为用户安排最优行程。只输出 JSON 数组。",
            )

            # 解析 JSON（容错处理）
            # 提取 JSON 数组（支持 markdown 代码块）
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response, re.DOTALL)
            if not json_match:
                json_match = re.search(r'(\[.*\])', response, re.DOTALL)
            if not json_match:
                logger.warning("LLM 返回中未找到 JSON 数组")
                return []

            json_str = json_match.group(1)
            # 修复常见 JSON 问题：尾部逗号
            json_str = re.sub(r',\s*([}\]])', r'\1', json_str)

            plan_items = json.loads(json_str)

            tasks = []
            for item in plan_items:
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

            # 后处理：修正 LLM 生成的假 ID 引用
            for t in tasks:
                logger.info(f"LLM 任务: {t.task_id} | {t.name} | {t.tool_name} | params={t.params}")
            tasks = self._fix_task_references(tasks)

            logger.info(f"LLM 生成了 {len(tasks)} 个任务")
            return tasks

        except Exception as e:
            logger.error(f"LLM 规划失败: {e}")
            return []

    def _fix_task_references(self, tasks: List[Task]) -> List[Task]:
        """
        后处理：修正 LLM 生成的假 ID 引用
        如果操作类任务依赖搜索任务但用了假 ID，自动替换为引用格式
        """
        ref_tools = {"book_restaurant", "check_queue"}
        search_tools = {"search_poi"}

        # 品类关键词映射：从任务名称推断目标品类
        category_keywords = {
            "餐厅": "餐厅", "饭店": "餐厅", "火锅": "餐厅", "烧烤": "餐厅",
            "拉面": "餐厅", "素食": "餐厅", "轻食": "餐厅",
            "密室": "密室逃脱", "逃脱": "密室逃脱",
            "电影": "电影院", "影城": "电影院", "IMAX": "电影院",
            "剧本杀": "剧本杀",
            "KTV": "KTV", "唱歌": "KTV",
            "儿童乐园": "儿童乐园", "乐园": "儿童乐园",
            "咖啡": "咖啡馆",
            "花": "花店",
        }

        for task in tasks:
            if task.tool_name not in ref_tools:
                continue

            restaurant_id = task.params.get("restaurant_id", "")
            # 如果已经是引用格式（包含 .results），跳过
            if ".results" in str(restaurant_id):
                continue

            # 从任务名称推断目标品类
            target_category = "餐厅"  # 默认
            for keyword, category in category_keywords.items():
                if keyword in task.name:
                    target_category = category
                    break

            # 按品类匹配搜索任务
            search_task = None
            for t in tasks:
                if t.tool_name not in search_tools:
                    continue
                if t.task_id >= task.task_id:
                    continue
                if t.params.get("category") == target_category:
                    search_task = t
                    break

            # 没找到精确匹配，取最近的搜索任务
            if not search_task:
                for t in tasks:
                    if t.tool_name in search_tools and t.task_id < task.task_id:
                        search_task = t

            if search_task:
                task.params["restaurant_id"] = "{" + search_task.task_id + ".results[0].id}"
                if search_task.task_id not in task.dependencies:
                    task.dependencies.append(search_task.task_id)
                logger.info(f"修正 {task.task_id} 的 restaurant_id -> {{{search_task.task_id}.results[0].id}}")

        return tasks

    def _rule_based_plan(self, intent: Dict[str, Any]) -> List[Task]:
        """规则引擎兜底规划"""
        tasks = []
        task_counter = 0
        task_ids = {}
        people = intent.get("people", [])
        needs = intent.get("needs", [])

        # 1. 检查天气
        task_counter += 1
        weather_id = f"T{task_counter:03d}"
        task_ids["weather"] = weather_id
        tasks.append(Task(
            task_id=weather_id, name="查询天气", tool_name="weather_api",
            params={"date": datetime.now().strftime("%Y-%m-%d"), "time": "14:00"},
            priority=10,
        ))

        # 2. 搜索娱乐场所
        ent_id = None
        if any(n == "entertainment" for n in needs):
            task_counter += 1
            ent_id = f"T{task_counter:03d}"
            # 根据人群选择品类
            has_child = any(p.get("role") == "child" for p in people)
            category = "儿童乐园" if has_child else "密室逃脱"
            keywords = ["室内"] if has_child else ["沉浸式", "剧情向"]
            tasks.append(Task(
                task_id=ent_id, name=f"搜索{category}", tool_name="search_poi",
                params={"category": category, "keywords": keywords, "rating_min": 4.5},
                priority=8, dependencies=[weather_id],
            ))

        # 3. 搜索餐厅
        dining_id = None
        book_id = None
        if any(n == "dining" for n in needs):
            task_counter += 1
            dining_id = f"T{task_counter:03d}"
            dining_keywords = []
            for c in intent.get("constraints", []):
                if c.get("type") == "diet" and c.get("requirement") == "low_calorie":
                    dining_keywords.extend(["低卡", "轻食", "健康"])
            tasks.append(Task(
                task_id=dining_id, name="搜索餐厅", tool_name="search_poi",
                params={"category": "餐厅", "keywords": dining_keywords, "rating_min": 4.5},
                priority=7, dependencies=[weather_id],
            ))

            # 4. 预订餐厅
            task_counter += 1
            book_id = f"T{task_counter:03d}"
            tasks.append(Task(
                task_id=book_id, name="预订餐厅", tool_name="book_restaurant",
                params={"restaurant_id": "{" + dining_id + ".results[0].id}", "time": "17:00",
                         "party_size": len(people), "special_requests": ["宝宝椅"]},
                priority=6, dependencies=[dining_id],
                fallback_tool="book_restaurant",
                fallback_params={"restaurant_id": "{" + dining_id + ".results[1].id}", "time": "17:00",
                                  "party_size": len(people)},
            ))

            # 5. 云排队
            task_counter += 1
            queue_id = f"T{task_counter:03d}"
            tasks.append(Task(
                task_id=queue_id, name="云排队取号", tool_name="check_queue",
                params={"restaurant_id": "{" + book_id + ".restaurant_id}", "action": "take_number",
                         "party_size": len(people)},
                priority=5, dependencies=[book_id],
            ))

        # 6. 惊喜配送
        if intent.get("surprise") and book_id:
            task_counter += 1
            tasks.append(Task(
                task_id=f"T{task_counter:03d}", name="惊喜配送", tool_name="order_delivery",
                params={"item_type": "鲜花", "item_name": "玫瑰花束",
                         "deliver_to": "{" + book_id + ".restaurant_name}",
                         "deliver_time": "17:30", "message": "老婆辛苦了，爱你！"},
                priority=4, dependencies=[book_id],
            ))

        return tasks

    def _check_null_refs(self, original: Dict[str, Any], resolved: Dict[str, Any]) -> list:
        """检查哪些引用解析后变成了 None"""
        null_keys = []
        for key, orig_val in original.items():
            if not isinstance(orig_val, str):
                continue
            # 检测引用格式
            cleaned = orig_val.strip().replace('\n', '').replace('\r', '')
            match = re.match(r'^\{+["\']?(\w+\.\S+?)["\']?\}+$', cleaned)
            if match:
                resolved_val = resolved.get(key)
                if resolved_val is None:
                    null_keys.append(key)
        return null_keys

    def resolve_params(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析参数中的动态引用
        支持多种格式：{{T001.results[0].id}}、{T001.results[0].id}、{"T001.results[0].id"}
        """

        def _resolve_ref(ref: str):
            """解析单个引用路径"""
            ref = ref.strip().strip('"').strip("'")
            dot_index = ref.find(".")
            if dot_index == -1:
                return context.get(ref)

            task_id = ref[:dot_index]
            path = ref[dot_index + 1:]
            current = context.get(task_id, {})

            path_parts = re.split(r'\.|\[|\]', path)
            path_parts = [p for p in path_parts if p]

            for part in path_parts:
                if current is None:
                    break
                if isinstance(current, dict):
                    current = current.get(part)
                elif isinstance(current, list):
                    try:
                        idx = int(part)
                        current = current[idx] if 0 <= idx < len(current) else None
                    except (ValueError, IndexError):
                        current = None
                else:
                    current = None
            return current

        resolved = {}
        for key, value in params.items():
            if not isinstance(value, str):
                resolved[key] = value
                continue

            # 清理空白字符
            cleaned = value.strip().replace('\n', '').replace('\r', '')

            # 匹配 {{...}}、{...}、{"..."} 等格式
            match = re.match(r'^\{+["\']?(\w+\.\S+?)["\']?\}+$', cleaned)
            if match:
                resolved[key] = _resolve_ref(match.group(1))
            else:
                resolved[key] = value
        return resolved

    async def execute_plan(self, tasks: List[Task]) -> Dict[str, Any]:
        """
        执行任务计划（每次调用创建局部状态机，避免并发串状态）

        Returns:
            执行结果摘要
        """
        # 每次执行创建局部状态机和异常处理器，避免全局状态被并发覆盖
        from .state_machine import StateMachine as _SM
        from .exception_handler import ExceptionHandler as _EH
        local_sm = _SM()
        local_sm.transition_to(AgentState.EXECUTING)
        local_eh = _EH(local_sm, tool_registry=self.tool_registry)
        state_machine = local_sm

        for task in tasks:
            state_machine.add_task(task)

        results = {}

        while not state_machine.all_tasks_completed():
            # 获取可执行的任务
            pending_tasks = state_machine.get_pending_tasks()

            if not pending_tasks:
                if state_machine.has_failed_tasks():
                    logger.warning("存在失败任务且无法恢复")
                    break
                logger.info("没有待执行的任务")
                break

            # 执行任务
            for task in pending_tasks:
                # 解析动态参数
                resolved_params = self.resolve_params(task.params, results)

                # 检查关键参数是否解析成功
                null_refs = self._check_null_refs(task.params, resolved_params)
                if null_refs:
                    logger.error(f"任务 {task.task_id} 关键参数解析为 None: {null_refs}")
                    state_machine.update_task_status(
                        task.task_id, TaskStatus.FAILED,
                        error=f"参数引用解析失败: {null_refs}"
                    )
                    continue

                # 获取工具
                tool = self.tool_registry.get(task.tool_name)
                if not tool:
                    logger.error(f"工具 {task.tool_name} 不存在")
                    state_machine.update_task_status(
                        task.task_id, TaskStatus.FAILED, error="工具不存在"
                    )
                    continue

                # 执行工具
                state_machine.update_task_status(task.task_id, TaskStatus.RUNNING)
                tool_result = await tool(resolved_params)

                if tool_result.success:
                    # 成功
                    state_machine.update_task_status(
                        task.task_id, TaskStatus.SUCCESS, result=tool_result.data
                    )
                    result_data = dict(tool_result.data) if isinstance(tool_result.data, dict) else {"data": tool_result.data}
                    result_data["task_name"] = task.name
                    results[task.task_id] = result_data
                    logger.info(f"任务 {task.task_id} 执行成功")
                else:
                    # 失败，交给异常处理器
                    logger.warning(f"任务 {task.task_id} 执行失败: {tool_result.error_message}")

                    # 创建重试函数
                    async def retry_func(t=task, p=resolved_params):
                        tool = self.tool_registry.get(t.tool_name)
                        return await tool(p)

                    error_result = await local_eh.handle_error(
                        task=task,
                        error_type=tool_result.error_type or "unknown",
                        error_message=tool_result.error_message or "未知错误",
                        retry_func=retry_func,
                    )

                    # 生成用户通知
                    notification = local_eh.generate_user_notification(error_result)
                    logger.info(f"用户通知: {notification}")

                    # Fallback 执行成功，写入结果
                    if error_result.get("action_taken") == "fallback_success":
                        fallback_data = error_result.get("fallback_result", {})
                        result_data = fallback_data.copy() if isinstance(fallback_data, dict) else {"data": fallback_data}
                        result_data["task_name"] = task.name
                        result_data["used_fallback"] = True
                        results[task.task_id] = result_data
                        logger.info(f"任务 {task.task_id} 备选方案执行成功")

                    # 如果需要重新规划
                    if error_result.get("action_taken") == "replan":
                        return {
                            "status": "replan_needed",
                            "reason": error_result.get("reason"),
                            "notification": notification,
                            "completed_results": results,
                        }

        # 生成执行摘要
        summary = state_machine.get_execution_summary()
        summary["results"] = results

        # 判断整体状态：所有任务都成功/跳过才算 success
        all_ok = all(
            t.status in (TaskStatus.SUCCESS, TaskStatus.SKIPPED)
            for t in state_machine.tasks.values()
        )
        if all_ok:
            summary["status"] = "success"
        else:
            summary["status"] = "partial"

        return summary

    async def run(
        self,
        user_input: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        完整的规划-执行流程（支持多轮对话）

        Args:
            user_input: 用户自然语言输入
            session_id: 会话 ID（可选）

        Returns:
            执行结果
        """
        logger.info(f"收到用户输入: {user_input}")

        # 获取或创建会话
        session = self.session_manager.get_or_create_session(session_id)
        session_id = session.session_id

        # 1. 解析意图（先构建上下文，再添加消息，避免重复）
        intent = await self.parse_intent(user_input, session)

        # 添加用户消息到会话（在 parse_intent 之后，避免 context 里重复）
        session.add_message("user", user_input)
        intent["raw_input"] = user_input  # 保留原始输入，供路线规划器使用
        logger.info(f"解析意图: {intent}")

        # 更新会话意图
        session.update_intent(intent)

        # 2. 创建计划
        tasks, route = await self.create_plan(intent)
        logger.info(f"创建计划: {len(tasks)} 个任务")

        # 记录路线信息（如果有的话），保留原始节点供故事引擎使用
        route_info = None
        route_nodes = None
        if route:
            route_nodes = list(route)  # 复制一份
            route_info = self.route_planner.get_route_for_planner(route)

        # 2.5. 检测剧本杀偏好，生成故事路线
        story_route = None
        if self.story_engine and route_nodes:
            if self.story_engine.detect_story_preference(user_input):
                story_route = await self.story_engine.generate_story_route(
                    intent, route_nodes
                )
                session.context["story_route"] = story_route
                logger.info(f"生成故事路线: {story_route.title}")

        # 3. 生成方案摘要
        plan_summary = await self._generate_plan_summary(intent, route_info, tasks)

        # 4. 保存待执行任务到会话，等待用户确认
        session.context["pending_tasks"] = tasks
        session.context["pending_route"] = route_info
        session.context["plan_summary"] = plan_summary
        if story_route:
            session.context["plan_summary"] = (
                f"🎭 {story_route.title}\n"
                f"{story_route.description}\n\n"
                f"{plan_summary}"
            )

        session.update_plan({
            "tasks": [
                {
                    "task_id": t.task_id,
                    "name": t.name,
                    "tool_name": t.tool_name,
                    "status": t.status.value if hasattr(t.status, 'value') else str(t.status)
                }
                for t in tasks
            ],
            "status": "waiting_confirmation"
        })

        session.add_message("assistant", plan_summary, {
            "task_count": len(tasks),
            "status": "waiting_confirmation"
        })

        return {
            "status": "waiting_confirmation",
            "session_id": session_id,
            "plan_summary": session.context["plan_summary"],
            "route": route_info,
            "story": {
                "title": story_route.title,
                "theme": story_route.theme,
                "description": story_route.description,
                "checkpoints": [
                    {"poi_name": cp.poi_name, "narrative": cp.narrative, "task": cp.task}
                    for cp in story_route.checkpoints
                ],
            } if story_route else None,
            "tasks_preview": [
                {"task_id": t.task_id, "name": t.name, "tool_name": t.tool_name}
                for t in tasks
            ],
        }

    async def confirm_and_execute(
        self,
        session_id: str,
        confirmed: bool = True,
    ) -> Dict[str, Any]:
        """
        用户确认后执行计划

        Args:
            session_id: 会话 ID
            confirmed: 是否确认执行

        Returns:
            执行结果
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            return {"status": "error", "message": "会话不存在或已过期"}

        if not confirmed:
            session.add_message("assistant", "好的，已取消本次规划。有需要随时告诉我～")
            return {"status": "cancelled", "session_id": session_id, "message": "已取消规划"}

        tasks = session.context.get("pending_tasks", [])
        if not tasks:
            return {"status": "error", "message": "没有待执行的任务，请重新规划"}

        route_info = session.context.get("pending_route")

        # 执行计划
        result = await self.execute_plan(tasks)

        # 生成分享文案
        share_text = await self._generate_share_text(session, result)

        # 更新会话
        session.update_plan({
            "tasks": [
                {
                    "task_id": t.task_id,
                    "name": t.name,
                    "status": t.status.value if hasattr(t.status, 'value') else str(t.status)
                }
                for t in tasks
            ],
            "result": result
        })

        session.add_message("assistant", f"全部搞定！{share_text}", {
            "status": result.get("status")
        })

        # 清理待执行状态
        session.context.pop("pending_tasks", None)
        session.context.pop("pending_route", None)
        session.context.pop("plan_summary", None)

        result["session_id"] = session_id
        result["share_text"] = share_text
        if route_info:
            result["route"] = route_info

        return result

    async def _generate_plan_summary(
        self,
        intent: Dict[str, Any],
        route_info: Optional[List[Dict]],
        tasks: List[Task],
    ) -> str:
        """生成人类可读的方案摘要"""
        if not self.llm_client or not self.llm_client.is_available():
            return self._default_plan_summary(intent, route_info, tasks)

        route_text = ""
        if route_info:
            route_text = "路线安排：\n" + "\n".join(
                f"  {r['arrival_time']} {r['poi_name']}（{r['category']}）"
                for r in route_info
            )

        task_text = "\n".join(
            f"  {t.task_id}: {t.name}" for t in tasks
        )

        prompt = f"""请根据以下信息，生成一份温馨的行程方案摘要（200字以内）。

用户需求：{intent.get('raw_input', '')}
意图：{json.dumps(intent, ensure_ascii=False)}

{route_text}

执行任务：
{task_text}

要求：
1. 用第二人称"你"
2. 包含具体时间和地点
3. 突出亮点（比如惊喜安排）
4. 语气亲切自然，像朋友推荐
5. 不要罗列任务清单，要讲故事"""

        try:
            summary = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="你是一个温暖的行程规划师，擅长用亲切的语气描述行程安排。",
            )
            return summary.strip()
        except Exception as e:
            logger.warning(f"生成方案摘要失败: {e}")
            return self._default_plan_summary(intent, route_info, tasks)

    def _default_plan_summary(
        self,
        intent: Dict[str, Any],
        route_info: Optional[List[Dict]],
        tasks: List[Task],
    ) -> str:
        """默认方案摘要（LLM 不可用时）"""
        parts = ["已为你规划好行程！"]
        if route_info:
            stops = " → ".join(r["poi_name"] for r in route_info)
            parts.append(f"路线：{stops}")
        parts.append(f"共 {len(tasks)} 个任务待执行。")
        return " ".join(parts)

    async def _generate_share_text(
        self,
        session: ConversationState,
        result: Dict[str, Any],
    ) -> str:
        """生成分享给朋友的文案"""
        if not self.llm_client or not self.llm_client.is_available():
            return "行程已安排好，具体细节稍后分享给你～"

        plan_summary = session.context.get("plan_summary", "")

        prompt = f"""生成一段发给朋友的微信消息，告诉他们行程搞定了。

行程信息：{plan_summary}
执行结果：{json.dumps(result.get('results', {}), ensure_ascii=False, default=str)[:500]}

要求：
1. 口语化，像真的在发微信
2. 简短（50字以内）
3. 包含关键时间地点
4. 如果有惊喜安排，不要剧透"""

        try:
            share_text = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="你是一个帮用户发微信通知朋友的助手。简短口语化。",
            )
            return share_text.strip()
        except Exception as e:
            logger.warning(f"生成分享文案失败: {e}")
            return "行程已安排好，具体细节稍后分享给你～"

    async def _generate_conversational_reply(
        self,
        user_input: str,
        session: ConversationState,
    ) -> str:
        """普通对话回复（不触发规划流程）"""
        if not self.llm_client or not self.llm_client.is_available():
            return "收到！如果需要规划行程，随时告诉我～"

        history = session.get_conversation_history()
        plan_summary = session.context.get("plan_summary", "暂无行程规划")

        prompt = f"""你是美团智能行程助手。用户正在和你对话。

对话历史：
{history}

当前行程状态：{plan_summary}

用户说：{user_input}

请用亲切自然的语气回复（50字以内）。如果用户想规划新行程或修改行程，引导他描述需求。"""

        try:
            reply = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="你是美团智能行程助手，语气亲切自然，像朋友一样。",
            )
            return reply.strip()
        except Exception as e:
            logger.warning(f"生成对话回复失败: {e}")
            return "收到！如果需要规划行程，随时告诉我～"

    async def continue_conversation(
        self,
        user_input: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        继续对话（多轮对话入口）

        Args:
            user_input: 用户输入
            session_id: 会话 ID

        Returns:
            执行结果
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.warning(f"会话 {session_id} 不存在，创建新会话")
            return await self.run(user_input)

        # 检测是否是修改请求
        is_modification = ContextBuilder.detect_modification_intent(user_input)

        if is_modification and session.current_plan:
            logger.info(f"检测到修改请求: {user_input}")
            return await self.run(user_input, session_id)

        # 普通对话：用 LLM 生成对话回复，不触发完整规划流程
        session.add_message("user", user_input)
        reply = await self._generate_conversational_reply(user_input, session)
        session.add_message("assistant", reply)
        return {
            "status": "conversation_continued",
            "session_id": session.session_id,
            "reply": reply,
            "plan_summary": session.context.get("plan_summary"),
        }
