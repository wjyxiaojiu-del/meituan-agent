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
from .services.intent_service import IntentService
from .services.route_service import RouteService
from .services.task_plan_service import TaskPlanService
from .services.response_service import ResponseService
from .services.execution_service import ExecutionService
from .services import modification_parser as mod_parser
from .services import plan_patch_service as patch_svc
from .services.modification_parser import ModificationAction
from .context import ContextLogger, TimingContext, set_session_id, get_timings

logger = ContextLogger(logging.getLogger(__name__))


# ===== LLM fallback hardening helpers (used by Planner._llm_fallback_parse) =====

_VALID_MOD_ACTIONS = {"replace", "remove", "insert", "shift_time", "declare_dislike"}
_TIME_DELTA_RE = re.compile(r"-?\d+")
_HHMM_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*$")


def _coerce_time_delta(value: Any) -> Optional[int]:
    """LLM may emit '30', '30 分钟', or 30 — squeeze to a signed int or None."""
    if value is None:
        return None
    if isinstance(value, bool):  # bool is a subclass of int — reject explicitly
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        m = _TIME_DELTA_RE.search(value)
        if m:
            return int(m.group())
    return None


def _coerce_hhmm(value: Any) -> Optional[str]:
    """Accept only well-formed HH:MM strings; LLM noise like '晚上7点' is dropped."""
    if not isinstance(value, str):
        return None
    m = _HHMM_RE.match(value)
    if not m:
        return None
    h, mm = int(m.group(1)), int(m.group(2))
    if 0 <= h <= 23 and 0 <= mm <= 59:
        return f"{h:02d}:{mm:02d}"
    return None


def _coerce_target_hint(value: Any) -> Dict[str, Any]:
    """target_hint must be a dict; sometimes LLM returns a bare poi name string."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        return {"poi_name": value.strip()}
    return {}


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
        self.intent_service = IntentService(self.llm_client)
        self.route_service = RouteService(route_planner, scene_manager)
        self.task_plan_service = TaskPlanService(self.llm_client, self.tool_registry)
        self.response_service = ResponseService(self.llm_client)
        self.execution_service = ExecutionService(self.tool_registry, self.exception_handler)
        self.route_planner = route_planner
        self.scene_manager = scene_manager
        self.story_engine = story_engine

    async def parse_intent(
        self,
        user_input: str,
        session: Optional[ConversationState] = None
    ) -> Dict[str, Any]:
        """解析用户意图（委托给 IntentService）"""
        return await self.intent_service.parse_intent(user_input, session)

    async def create_plan(self, intent: Dict[str, Any], session_context: Optional[Dict[str, Any]] = None):
        """
        根据意图创建执行计划

        流程：
        1. 路线规划引擎选出最优 POI 顺序
        2. LLM 生成任务计划（优先），失败回退规则引擎
        3. 后处理：保证天气任务始终存在

        Returns:
            (tasks, route, route_stats) 三元组
        """
        # === 第一步：路线规划 ===
        route = None
        route_desc = ""
        route_stats = {}
        if self.route_planner:
            route, route_stats = await self.route_service.plan_from_intent(intent, session_context)
            if route:
                route_desc = self.route_planner.format_route_for_display(route)
                logger.info(f"路线规划完成: {route_stats.get('poi_count', 0)} 个节点")

        # === 第二步：任务生成（委托给 TaskPlanService）===
        tasks = await self.task_plan_service.create_tasks(intent, route, route_desc)

        return tasks, route, route_stats

    def _ensure_weather_task(self, tasks: List[Task], intent: Dict[str, Any]) -> List[Task]:
        """保证天气查询任务始终存在（委托给 TaskPlanService）"""
        return self.task_plan_service.ensure_weather_task(tasks, intent)

    async def _plan_route_from_intent(self, intent: Dict[str, Any]):
        """根据意图规划路线（委托给 RouteService）"""
        return await self.route_service.plan_from_intent(intent)

    async def _llm_create_plan(
        self, intent: Dict[str, Any], route, route_desc: str
    ) -> List[Task]:
        """LLM 生成任务计划（委托给 TaskPlanService）"""
        return await self.task_plan_service.llm_create_plan(intent, route, route_desc)

    def _fix_task_references(self, tasks: List[Task]) -> List[Task]:
        """修正 LLM 生成的假 ID 引用（委托给 TaskPlanService）"""
        return self.task_plan_service.fix_task_references(tasks)

    def _rule_based_plan(self, intent: Dict[str, Any], route=None) -> List[Task]:
        """基于路线生成任务计划（委托给 TaskPlanService）"""
        return self.task_plan_service.rule_based_plan(intent, route)

    def _check_null_refs(self, original: Dict[str, Any], resolved: Dict[str, Any]) -> list:
        """检查引用解析结果（委托给 ExecutionService）"""
        return self.execution_service.check_null_refs(original, resolved)

    def resolve_params(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """解析动态参数引用（委托给 ExecutionService）"""
        return self.execution_service.resolve_params(params, context)

    async def execute_plan(self, tasks: List[Task]) -> Dict[str, Any]:
        """执行任务计划（委托给 ExecutionService）"""
        return await self.execution_service.execute_plan(tasks)

    def _detect_story_intent(self, user_input: str) -> bool:
        """检测用户是否想要故事剧情（委托给 ResponseService）"""
        return self.response_service.detect_story_intent(user_input)

    async def run(
        self,
        user_input: str,
        session_id: Optional[str] = None,
        enable_story: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        完整的规划-执行流程（支持多轮对话）

        Args:
            user_input: 用户自然语言输入
            session_id: 会话 ID（可选）
            enable_story: 是否启用剧情模式（None=自动检测，True=强制开启，False=强制关闭）

        Returns:
            执行结果
        """
        logger.info(f"收到用户输入: {user_input}")

        # 获取或创建会话
        session = self.session_manager.get_or_create_session(session_id)
        session_id = session.session_id
        set_session_id(session_id)

        # 1. 解析意图
        with TimingContext("intent_parse"):
            intent = await self.parse_intent(user_input, session)

        # 添加用户消息到会话
        session.add_message("user", user_input)
        intent["raw_input"] = user_input
        logger.info(f"解析意图: {intent}")

        # 更新会话意图
        session.update_intent(intent)

        # 2. 创建计划
        with TimingContext("plan_create"):
            tasks, route, route_stats = await self.create_plan(intent, session.context)
        logger.info(f"创建计划: {len(tasks)} 个任务")

        # 记录路线信息（如果有的话），保留原始节点供故事引擎使用
        route_info = None
        route_nodes = None
        if route:
            route_nodes = list(route)  # 复制一份
            route_info = self.route_planner.get_route_for_planner(route)

        # 2.5. 生成故事路线和方案摘要（串行调用，MiMo 不支持并发）
        story_route = None
        wants_story = enable_story if enable_story is not None else self._detect_story_intent(user_input)
        if self.story_engine and route_nodes and wants_story:
            with TimingContext("story_generate"):
                story_route = await self.story_engine.generate_story_route(intent, route_nodes)
            session.context["story_route"] = story_route
            logger.info(f"生成故事路线: {story_route.title}")

        with TimingContext("summary_generate"):
            plan_summary = await self._generate_plan_summary(intent, route_info, tasks)

        # 3. 保存待执行任务到会话，等待用户确认
        session.context["pending_tasks"] = tasks
        session.context["pending_route"] = route_info
        session.context["pending_route_nodes"] = route_nodes  # 供 patch 路径使用
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
            "route_stats": route_stats,
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
                {"task_id": t.task_id, "name": t.name, "tool_name": t.tool_name,
                 "params": t.params}
                for t in tasks
            ],
            "timings": get_timings(),
        }

    async def run_stream(
        self,
        user_input: str,
        session_id: Optional[str] = None,
        enable_story: Optional[bool] = None,
    ):
        """流式版 run()，yield SSE 事件字典"""
        logger.info(f"[stream] 收到用户输入: {user_input}")

        session = self.session_manager.get_or_create_session(session_id)
        session_id = session.session_id
        set_session_id(session_id)

        # 1. 意图解析
        yield {"type": "step", "step": "intent", "text": "正在理解你的需求..."}
        with TimingContext("intent_parse"):
            intent = await self.parse_intent(user_input, session)
        session.add_message("user", user_input)
        intent["raw_input"] = user_input
        session.update_intent(intent)
        yield {"type": "step", "step": "intent_done", "text": "需求理解完成"}

        # 2. 路线规划
        yield {"type": "step", "step": "route", "text": "正在规划最优路线..."}
        with TimingContext("plan_create"):
            tasks, route, route_stats = await self.create_plan(intent, session.context)
        route_info = None
        route_nodes = None
        if route:
            route_nodes = list(route)
            route_info = self.route_planner.get_route_for_planner(route)
        yield {"type": "step", "step": "route_done", "text": f"已规划 {len(route_info) if route_info else 0} 个站点"}

        # 3. 故事生成
        story_route = None
        wants_story = enable_story if enable_story is not None else self._detect_story_intent(user_input)
        if self.story_engine and route_nodes and wants_story:
            yield {"type": "step", "step": "story", "text": "正在创作专属剧情..."}
            with TimingContext("story_generate"):
                story_route = await self.story_engine.generate_story_route(intent, route_nodes)
            session.context["story_route"] = story_route
            yield {"type": "step", "step": "story_done", "text": "剧情创作完成"}

        # 4. 方案摘要（流式输出）
        yield {"type": "step", "step": "summary", "text": "正在生成方案摘要..."}
        plan_summary = ""
        with TimingContext("summary_generate"):
            async for chunk in self._generate_plan_summary_stream(intent, route_info, tasks):
                plan_summary += chunk
                yield {"type": "chunk", "text": chunk}
        yield {"type": "step", "step": "summary_done", "text": "摘要生成完成"}

        # 5. 保存 session
        session.context["pending_tasks"] = tasks
        session.context["pending_route"] = route_info
        session.context["pending_route_nodes"] = route_nodes  # 供 patch 路径使用
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

        # 6. 完成
        yield {
            "type": "done",
            "data": {
                "status": "waiting_confirmation",
                "session_id": session_id,
                "plan_summary": session.context["plan_summary"],
                "route": route_info,
                "route_stats": route_stats,
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
                    {"task_id": t.task_id, "name": t.name, "tool_name": t.tool_name,
                     "params": t.params}
                    for t in tasks
                ],
                "llmStatus": getattr(self.llm_client, '_last_status', 'unknown'),
                "timings": get_timings(),
            },
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

        # 只有成功时才清理待执行状态，失败时保留以便重试
        exec_status = result.get("status", "")
        if exec_status in ("success", "partial"):
            session.context.pop("pending_tasks", None)
            session.context.pop("pending_route", None)
            session.context.pop("pending_route_nodes", None)
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
        """生成方案摘要（委托给 ResponseService）"""
        return await self.response_service.generate_plan_summary(intent, route_info, tasks)

    async def _generate_plan_summary_stream(
        self,
        intent: Dict[str, Any],
        route_info: Optional[List[Dict]],
        tasks: List[Task],
    ):
        """流式生成方案摘要（委托给 ResponseService）"""
        async for chunk in self.response_service.generate_plan_summary_stream(intent, route_info, tasks):
            yield chunk

    def _default_plan_summary(
        self,
        intent: Dict[str, Any],
        route_info: Optional[List[Dict]],
        tasks: List[Task],
    ) -> str:
        """默认方案摘要（委托给 ResponseService）"""
        return self.response_service.default_plan_summary(intent, route_info, tasks)

    async def _generate_share_text(
        self,
        session: ConversationState,
        result: Dict[str, Any],
    ) -> str:
        """生成分享文案（委托给 ResponseService）"""
        return await self.response_service.generate_share_text(session, result)

    async def _generate_conversational_reply(
        self,
        user_input: str,
        session: ConversationState,
    ) -> str:
        """普通对话回复（委托给 ResponseService）"""
        return await self.response_service.generate_conversational_reply(user_input, session)

    async def continue_conversation(
        self,
        user_input: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        继续对话（多轮对话入口）

        优先走 patch 路径：规则解析器 → LLM 兜底 → 命中则局部修改 pending_*。
        未命中时如果检测出修改意图则走 run() 重新规划；否则普通对话。

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

        session.add_message("user", user_input)

        # 优先 patch 路径：有 pending plan 时
        pending_tasks = session.context.get("pending_tasks") or []
        pending_nodes = session.context.get("pending_route_nodes") or []
        if pending_tasks and pending_nodes:
            patched = await self._try_patch(
                user_input, session, pending_tasks, pending_nodes,
            )
            if patched is not None:
                return patched

        # 修改意图但 patch 未命中 → 重新规划
        is_modification = ContextBuilder.detect_modification_intent(user_input)
        if is_modification and session.current_plan:
            logger.info(f"修改请求未命中规则，走 run() 重新规划: {user_input}")
            return await self.run(user_input, session_id)

        # 普通对话回复
        reply = await self._generate_conversational_reply(user_input, session)
        session.add_message("assistant", reply)
        return {
            "status": "conversation_continued",
            "session_id": session.session_id,
            "reply": reply,
            "plan_summary": session.context.get("plan_summary"),
        }

    async def _try_patch(
        self,
        user_input: str,
        session: ConversationState,
        pending_tasks: List[Task],
        pending_nodes: list,
    ) -> Optional[Dict[str, Any]]:
        """尝试用 patch 路径处理修改请求。返回响应字典，未命中返回 None。"""
        action = mod_parser.parse(user_input, pending_tasks, pending_nodes, session.context)
        if action is None and ContextBuilder.detect_modification_intent(user_input):
            action = await self._llm_fallback_parse(user_input, pending_tasks, pending_nodes)
        if action is None:
            return None

        intent = session.current_intent or {}
        new_tasks, new_nodes, change_log = patch_svc.apply_modification(
            action, pending_tasks, pending_nodes, intent, session.context, self.route_planner,
        )

        # 仅错误：保留旧状态，反馈错误信息
        if change_log and change_log[0].get("type") == "error":
            err_msg = change_log[0].get("message", "调整失败")
            session.add_message("assistant", err_msg, {"change_log": change_log})
            return {
                "status": "plan_modify_failed",
                "session_id": session.session_id,
                "action_type": action.action_type,
                "change_log": change_log,
                "reply": err_msg,
                "plan_summary": session.context.get("plan_summary"),
            }

        # 回写 session
        session.context["pending_tasks"] = new_tasks
        session.context["pending_route_nodes"] = new_nodes
        route_info = (
            self.route_planner.get_route_for_planner(new_nodes)
            if new_nodes and self.route_planner else []
        )
        session.context["pending_route"] = route_info
        route_stats = self._stats_from_nodes(new_nodes, intent)
        session.context["pending_route_stats"] = route_stats

        # 同步剧本杀 checkpoints —— replace 改 POI 引用，remove 删 cp，其余不动
        story_route = session.context.get("story_route")
        story_payload = None
        if story_route and self.story_engine:
            try:
                self.story_engine.remap_after_patch(story_route, change_log, new_nodes)
                session.context["story_route"] = story_route
                story_payload = {
                    "title": story_route.title,
                    "theme": story_route.theme,
                    "description": story_route.description,
                    "checkpoints": [
                        {"poi_name": cp.poi_name, "narrative": cp.narrative, "task": cp.task}
                        for cp in story_route.checkpoints
                    ],
                }
            except Exception as e:
                logger.warning(f"story remap failed: {e}")

        new_summary = await self.response_service.regenerate_summary(
            intent, route_info, new_tasks, change_log,
        )
        session.context["plan_summary"] = new_summary

        session.update_plan({
            "tasks": [
                {
                    "task_id": t.task_id,
                    "name": t.name,
                    "tool_name": t.tool_name,
                    "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                }
                for t in new_tasks
            ],
            "status": "waiting_confirmation",
        })

        session.add_message("assistant", new_summary, {
            "change_log": change_log,
            "action_type": action.action_type,
        })

        return {
            "status": "plan_modified",
            "session_id": session.session_id,
            "action_type": action.action_type,
            "change_log": change_log,
            "plan_summary": new_summary,
            "route": route_info,
            "route_stats": route_stats,
            "story": story_payload,
            "tasks_preview": [
                {"task_id": t.task_id, "name": t.name, "tool_name": t.tool_name,
                 "params": t.params}
                for t in new_tasks
            ],
        }

    def _stats_from_nodes(self, nodes: list, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Compute route stats from RouteNode list — used in patch path."""
        if not nodes:
            return {"total_duration": 0, "total_distance": 0, "total_cost": 0,
                    "poi_count": 0, "walking_distance": 0, "total_savings": 0}
        group_size = (intent or {}).get("group_size") or 1
        total_duration = int((nodes[-1].departure_time - nodes[0].arrival_time).total_seconds() / 60)
        total_distance = sum(n.travel_distance_from_prev for n in nodes)
        total_cost = sum((n.poi.price_per_person or 0) * group_size for n in nodes)
        walking_distance = sum(
            n.travel_distance_from_prev for n in nodes
            if n.travel_distance_from_prev <= 2000
        )
        total_savings = 0
        for n in nodes:
            if n.poi.coupon_price and n.poi.original_price:
                total_savings += (n.poi.original_price - n.poi.coupon_price) * group_size
        return {
            "total_duration": total_duration,
            "total_distance": int(total_distance),
            "total_cost": int(total_cost),
            "poi_count": len(nodes),
            "walking_distance": int(walking_distance),
            "total_savings": int(total_savings),
        }

    async def _llm_fallback_parse(
        self,
        user_input: str,
        pending_tasks: List[Task],
        pending_nodes: list,
    ) -> Optional[ModificationAction]:
        """规则未命中时调 LLM 兜底解析。返回 ModificationAction 或 None。"""
        if not self.llm_client or not self.llm_client.is_available():
            return None

        route_text = " | ".join(
            f"[{i}] {n.poi.name}({n.poi.category})"
            for i, n in enumerate(pending_nodes) if hasattr(n, "poi")
        )
        prompt = (
            "用户对已规划的行程做出修改请求。请提取意图，只输出一个 JSON 对象。\n\n"
            f"当前行程：{route_text}\n\n"
            "JSON schema（严格）：\n"
            "- action_type: \"replace\" | \"remove\" | \"insert\" | \"shift_time\" | \"declare_dislike\"\n"
            "- target_hint: 对象，例如 {\"index\":1} / {\"category\":\"餐厅\"} / "
            "{\"poi_name\":\"海底捞\"} / {\"location\":\"三里屯\"}\n"
            "- new_category: 新类别字符串（如\"火锅\"），不用时省略\n"
            "- new_poi_name: 指定的 POI 名称字符串\n"
            "- time_delta_min: 整数，正=推迟，负=提前；仅 shift_time 用\n"
            "- absolute_start: \"HH:MM\" 24 小时制；仅 shift_time 用\n\n"
            "示例：\n"
            "「把第二个换成火锅」→ "
            "{\"action_type\":\"replace\",\"target_hint\":{\"index\":1},\"new_category\":\"火锅\"}\n"
            "「不要海底捞了」→ "
            "{\"action_type\":\"remove\",\"target_hint\":{\"poi_name\":\"海底捞\"}}\n"
            "「晚一个半小时开始」→ "
            "{\"action_type\":\"shift_time\",\"time_delta_min\":90}\n"
            "「改成晚上7点」→ "
            "{\"action_type\":\"shift_time\",\"absolute_start\":\"19:00\"}\n"
            "「下次别推三里屯了」→ "
            "{\"action_type\":\"declare_dislike\",\"target_hint\":{\"location\":\"三里屯\"}}\n\n"
            f"用户输入：{user_input}\n\n"
            "只输出 JSON，不要解释，不要 markdown 围栏。"
        )
        try:
            result = await self.llm_client.chat_json(
                messages=[{"role": "user", "content": prompt}],
            )
            logger.debug(f"[mod_parser] LLM fallback raw: {result}")
            action = self._build_action_from_llm(result, user_input)
            if action is None:
                return None
            mod_parser.resolve_target(action, pending_tasks, pending_nodes)
            logger.info(f"[mod_parser] LLM fallback hit: {action.action_type}")
            return action
        except Exception as e:
            logger.warning(f"LLM 兜底解析失败: {e}")
            return None

    @staticmethod
    def _build_action_from_llm(
        result: Any, user_input: str,
    ) -> Optional[ModificationAction]:
        """Validate LLM JSON and coerce fields. Return None on schema violation."""
        if not isinstance(result, dict):
            return None
        atype = result.get("action_type")
        if atype not in _VALID_MOD_ACTIONS:
            logger.warning(f"[mod_parser] LLM bad action_type: {atype!r}")
            return None
        return ModificationAction(
            action_type=atype,
            target_hint=_coerce_target_hint(result.get("target_hint")),
            new_category=(result.get("new_category") or None),
            new_tag=(result.get("new_tag") or None),
            new_poi_name=(result.get("new_poi_name") or None),
            time_delta_min=_coerce_time_delta(result.get("time_delta_min")),
            absolute_start=_coerce_hhmm(result.get("absolute_start")),
            confidence=0.6,
            raw=user_input,
        )
