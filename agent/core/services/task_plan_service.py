"""
任务计划服务
从 Planner 中提取的任务生成相关逻辑
"""

import json
import re
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from ..state_machine import Task
from ...llm.client import LLMClient
from ...tools.base import ToolRegistry

logger = logging.getLogger(__name__)


def _attach_poi_caps(task: Task, poi) -> None:
    """Copy POI capability_tags + deal_label into task.params (mutates).

    Frontend reads these to render the capability chip on each task card.
    Safe no-op when POI carries no capabilities.
    """
    if not poi:
        return
    caps = list(getattr(poi, "capability_tags", []) or [])
    if caps:
        task.params["capability_tags"] = caps
    label = getattr(poi, "deal_label", None)
    if label:
        task.params["deal_label"] = label


class TaskPlanService:
    """任务计划服务"""

    def __init__(self, llm_client: LLMClient, tool_registry: ToolRegistry):
        self.llm_client = llm_client
        self.tool_registry = tool_registry

    async def create_tasks(
        self, intent: Dict[str, Any], route=None, route_desc: str = ""
    ) -> List[Task]:
        """
        生成任务计划（LLM 优先，失败回退规则引擎）

        Args:
            intent: 用户意图
            route: 路线节点列表
            route_desc: 路线描述文本

        Returns:
            Task 列表
        """
        tasks = []
        if self.llm_client and self.llm_client.is_available():
            tasks = await self.llm_create_plan(intent, route, route_desc)
            if tasks:
                logger.info(f"LLM 规划成功: {len(tasks)} 个任务")
            else:
                logger.info("LLM 规划为空，回退规则引擎")

        if not tasks:
            tasks = self.rule_based_plan(intent, route)
            logger.info(f"规则引擎生成: {len(tasks)} 个任务")

        # 后处理：保证天气任务始终存在
        tasks = self.ensure_weather_task(tasks, intent)

        return tasks

    async def llm_create_plan(
        self, intent: Dict[str, Any], route, route_desc: str
    ) -> List[Task]:
        """让 LLM 根据意图和路线生成任务计划"""
        if not self.llm_client or not self.llm_client.is_available():
            return []

        tools_desc = self.tool_registry.to_openai_functions()

        route_section = f"已规划路线（按顺序）：\n{route_desc}" if route_desc else "暂无路线规划，请根据意图自行安排。"
        prompt = f"""你是美团智能行程助手。请根据用户意图生成详细的执行计划。

用户意图：
{json.dumps(intent, ensure_ascii=False, indent=2)}

{route_section}

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

            # 统一 JSON 提取
            plan_items = LLMClient.extract_json(response, expect_array=True)
            if plan_items is None:
                logger.warning("LLM 返回中未找到 JSON 数组")
                return []

            # 验证是对象数组而非其他类型
            if not isinstance(plan_items, list):
                logger.warning(f"LLM 返回的 JSON 不是数组: {type(plan_items)}")
                return []
            if plan_items and not isinstance(plan_items[0], dict):
                logger.warning(f"LLM 返回的 JSON 数组元素不是对象: {type(plan_items[0])}")
                return []

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
            tasks = self.fix_task_references(tasks)

            logger.info(f"LLM 生成了 {len(tasks)} 个任务")
            return tasks

        except Exception as e:
            logger.warning(f"LLM 规划失败，使用规则引擎: {e}")
            return []

    def fix_task_references(self, tasks: List[Task]) -> List[Task]:
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

    def rule_based_plan(self, intent: Dict[str, Any], route=None) -> List[Task]:
        """基于实际路线生成任务计划"""
        tasks = []
        task_counter = 0
        people = intent.get("people", [])
        has_child = any(p.get("role") == "child" for p in people)

        # 动态生成 special_requests
        special_requests = []
        for c in intent.get("constraints", []):
            if c.get("type") == "diet" and c.get("requirement") == "low_calorie":
                special_requests.extend(["低卡", "轻食", "健康"])
        if has_child:
            special_requests.append("宝宝椅")

        # 1. 天气查询（始终存在）
        task_counter += 1
        weather_id = f"T{task_counter:03d}"
        start_time_str = "14:00"
        if route:
            first_node = route[0]
            start_time_str = first_node.arrival_time.strftime("%H:%M")
        tasks.append(Task(
            task_id=weather_id, name="查询天气", tool_name="weather_api",
            params={"date": datetime.now().strftime("%Y-%m-%d"), "time": start_time_str},
            priority=10,
        ))

        # 2. 遍历路线节点，为每个 POI 生成对应任务
        search_ids = {}  # poi_id -> search_task_id
        book_id = None   # 最后一个餐厅的预订任务 ID
        last_restaurant_node = None

        if route:
            for node in route:
                poi = node.poi
                cat = poi.category
                task_counter += 1
                search_id = f"T{task_counter:03d}"
                search_ids[poi.id] = search_id

                # 搜索任务
                tasks.append(Task(
                    task_id=search_id, name=f"搜索{poi.name}", tool_name="search_poi",
                    params={"category": cat, "keywords": poi.tags[:3], "rating_min": 4.0,
                            "poi_name": poi.name},
                    priority=8, dependencies=[weather_id],
                ))
                _attach_poi_caps(tasks[-1], poi)

                # 餐厅类 → 预订 + 排队
                dining_categories = ["餐厅", "咖啡馆", "小吃街", "甜品店"]
                if cat in dining_categories:
                    last_restaurant_node = node
                    task_counter += 1
                    book_id = f"T{task_counter:03d}"
                    book_time = node.arrival_time.strftime("%H:%M")
                    tasks.append(Task(
                        task_id=book_id, name=f"预订{poi.name}", tool_name="book_restaurant",
                        params={"restaurant_id": "{" + search_id + ".results[0].id}",
                                "time": book_time, "party_size": len(people),
                                "special_requests": special_requests,
                                "restaurant_name": poi.name},
                        priority=6, dependencies=[search_id],
                    ))
                    _attach_poi_caps(tasks[-1], poi)

                    task_counter += 1
                    queue_id = f"T{task_counter:03d}"
                    tasks.append(Task(
                        task_id=queue_id, name=f"{poi.name}排队取号", tool_name="check_queue",
                        params={"restaurant_id": "{" + book_id + ".restaurant_id}",
                                "action": "take_number", "party_size": len(people)},
                        priority=5, dependencies=[book_id],
                    ))
                    _attach_poi_caps(tasks[-1], poi)

                # 娱乐类 → 预订场地
                play_categories = ["密室逃脱", "KTV", "轰趴馆", "儿童乐园", "剧本杀",
                                   "电影院", "户外拓展", "SPA"]
                if cat in play_categories:
                    task_counter += 1
                    venue_id = f"T{task_counter:03d}"
                    venue_time = node.arrival_time.strftime("%H:%M")
                    tasks.append(Task(
                        task_id=venue_id, name=f"预订{poi.name}", tool_name="book_venue",
                        params={"venue_id": "{" + search_id + ".results[0].id}",
                                "time": venue_time, "party_size": len(people),
                                "venue_name": poi.name},
                        priority=6, dependencies=[search_id],
                    ))
                    _attach_poi_caps(tasks[-1], poi)

        # 3. 惊喜配送（如果有餐厅且需要惊喜）
        if intent.get("surprise") and book_id and last_restaurant_node:
            task_counter += 1
            deliver_time = (last_restaurant_node.arrival_time + timedelta(minutes=30)).strftime("%H:%M")
            # 根据场景选择惊喜物品
            item_type, item_name, message = "鲜花", "玫瑰花束", "给你一个惊喜～"
            if has_child:
                item_type, item_name, message = "蛋糕", "儿童蛋糕", "宝贝开心每一天！"
            tasks.append(Task(
                task_id=f"T{task_counter:03d}", name="惊喜配送", tool_name="order_delivery",
                params={"item_type": item_type, "item_name": item_name,
                         "deliver_to": "{" + book_id + ".restaurant_name}",
                         "deliver_time": deliver_time, "message": message,
                         "capability_tags": ["闪送"],
                         "deal_label": "闪送 · 30分钟达"},
                priority=4, dependencies=[book_id],
            ))

        # 降级：如果没有路线，用简单逻辑兜底
        if not route:
            needs = list(intent.get("needs", []))
            if any(n in ("entertainment", "meeting") for n in needs):
                task_counter += 1
                tasks.append(Task(
                    task_id=f"T{task_counter:03d}", name="搜索活动场所", tool_name="search_poi",
                    params={"category": "儿童乐园" if has_child else "密室逃脱",
                            "keywords": ["室内"] if has_child else ["沉浸式"],
                            "rating_min": 4.5},
                    priority=8, dependencies=[weather_id],
                ))
            if any(n == "dining" for n in needs):
                task_counter += 1
                dining_id = f"T{task_counter:03d}"
                tasks.append(Task(
                    task_id=dining_id, name="搜索餐厅", tool_name="search_poi",
                    params={"category": "餐厅", "keywords": special_requests, "rating_min": 4.5},
                    priority=7, dependencies=[weather_id],
                ))
                task_counter += 1
                tasks.append(Task(
                    task_id=f"T{task_counter:03d}", name="预订餐厅", tool_name="book_restaurant",
                    params={"restaurant_id": "{" + dining_id + ".results[0].id}", "time": "17:00",
                             "party_size": len(people), "special_requests": special_requests},
                    priority=6, dependencies=[dining_id],
                ))

        return tasks

    def ensure_weather_task(self, tasks: List[Task], intent: Dict[str, Any]) -> List[Task]:
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
