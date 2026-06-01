"""
执行引擎服务
从 Planner 中提取的任务执行相关逻辑
"""

import re
import logging
from typing import Dict, Any, List

from ..state_machine import StateMachine, Task, TaskStatus, AgentState
from ..exception_handler import ExceptionHandler
from ...tools.base import ToolRegistry

logger = logging.getLogger(__name__)


class ExecutionService:
    """执行引擎服务"""

    def __init__(self, tool_registry: ToolRegistry, exception_handler: ExceptionHandler = None):
        self.tool_registry = tool_registry
        self.exception_handler = exception_handler

    async def execute_plan(self, tasks: List[Task]) -> Dict[str, Any]:
        """
        执行任务计划（每次调用创建局部状态机，避免并发串状态）

        Returns:
            执行结果摘要
        """
        # 每次执行创建局部状态机和异常处理器，避免全局状态被并发覆盖
        local_sm = StateMachine()
        local_sm.transition_to(AgentState.EXECUTING)
        local_eh = ExceptionHandler(local_sm, tool_registry=self.tool_registry)
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
                null_refs = self.check_null_refs(task.params, resolved_params)
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

    def check_null_refs(self, original: Dict[str, Any], resolved: Dict[str, Any]) -> list:
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
