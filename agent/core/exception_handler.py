"""
异常处理器模块
实现三层异常处理机制：Retry -> Fallback -> Replan
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Callable
from enum import Enum

from .state_machine import Task, TaskStatus, StateMachine, AgentState

logger = logging.getLogger(__name__)


class ErrorLevel(Enum):
    """错误级别"""
    RETRY = "RETRY"         # 可重试
    FALLBACK = "FALLBACK"   # 需要备选方案
    REPLAN = "REPLAN"       # 需要重新规划
    FATAL = "FATAL"         # 致命错误


class ErrorClassifier:
    """
    错误分类器
    根据错误类型判断处理策略
    """

    # 错误类型 -> 错误级别映射
    ERROR_MAPPING = {
        # 网络错误 - 可重试
        "timeout": ErrorLevel.RETRY,
        "connection_error": ErrorLevel.RETRY,
        "rate_limit": ErrorLevel.RETRY,
        "network_unreachable": ErrorLevel.RETRY,

        # 业务错误 - 需要备选方案
        "seat_unavailable": ErrorLevel.FALLBACK,
        "out_of_stock": ErrorLevel.FALLBACK,
        "queue_full": ErrorLevel.FALLBACK,
        "restaurant_closed": ErrorLevel.FALLBACK,

        # 环境变化 - 需要重新规划
        "weather_change": ErrorLevel.REPLAN,
        "traffic_jam": ErrorLevel.REPLAN,
        "event_cancelled": ErrorLevel.REPLAN,

        # 致命错误
        "invalid_api_key": ErrorLevel.FATAL,
        "service_unavailable": ErrorLevel.FATAL,
    }

    @classmethod
    def classify(cls, error_type: str, error_message: str = "") -> ErrorLevel:
        """根据错误类型分类"""
        # 先检查已知错误类型
        if error_type in cls.ERROR_MAPPING:
            return cls.ERROR_MAPPING[error_type]

        # 根据错误消息关键词判断
        error_lower = error_message.lower()
        if any(kw in error_lower for kw in ["timeout", "超时", "网络"]):
            return ErrorLevel.RETRY
        if any(kw in error_lower for kw in ["满座", "已满", "售罄", "closed"]):
            return ErrorLevel.FALLBACK
        if any(kw in error_lower for kw in ["天气", "暴雨", "台风"]):
            return ErrorLevel.REPLAN

        # 默认可重试
        return ErrorLevel.RETRY


class ExceptionHandler:
    """
    异常处理器
    实现三层处理机制
    """

    def __init__(self, state_machine: StateMachine, tool_registry=None):
        self.state_machine = state_machine
        self.tool_registry = tool_registry
        self.classifier = ErrorClassifier()
        self.max_retries = 3
        self.retry_delay = 1.0  # 秒

    async def handle_error(
        self,
        task: Task,
        error_type: str,
        error_message: str,
        retry_func: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        处理任务错误

        Args:
            task: 出错的任务
            error_type: 错误类型
            error_message: 错误消息
            retry_func: 重试函数（如果需要重试）

        Returns:
            处理结果
        """
        error_level = self.classifier.classify(error_type, error_message)
        logger.info(f"处理错误: task={task.task_id}, level={error_level.value}, msg={error_message}")

        result = {
            "task_id": task.task_id,
            "error_level": error_level.value,
            "error_message": error_message,
            "action_taken": None,
        }

        if error_level == ErrorLevel.RETRY:
            result.update(await self._handle_retry(task, retry_func))

        elif error_level == ErrorLevel.FALLBACK:
            result.update(await self._handle_fallback(task))

        elif error_level == ErrorLevel.REPLAN:
            result.update(self._handle_replan(task, error_message))

        elif error_level == ErrorLevel.FATAL:
            result.update(self._handle_fatal(task, error_message))

        return result

    async def _handle_retry(self, task: Task, retry_func: Optional[Callable]) -> Dict[str, Any]:
        """L1: 重试策略（异步）"""
        if task.retry_count >= self.max_retries:
            logger.warning(f"任务 {task.task_id} 重试次数耗尽，升级为 Fallback")
            return await self._handle_fallback(task)

        task.retry_count += 1
        task.status = TaskStatus.RETRYING
        self.state_machine.update_task_status(task.task_id, TaskStatus.RETRYING)

        # 指数退避延迟（异步非阻塞）
        delay = self.retry_delay * (2 ** (task.retry_count - 1))
        logger.info(f"任务 {task.task_id} 第 {task.retry_count} 次重试，延迟 {delay}s")
        await asyncio.sleep(delay)

        # 执行重试
        if retry_func:
            try:
                result = await retry_func(task)
                # 检查重试结果是否真正成功
                is_success = False
                if hasattr(result, "success"):
                    is_success = result.success
                    if is_success:
                        task.status = TaskStatus.SUCCESS
                        task.result = result.data if hasattr(result, "data") else result
                        self.state_machine.update_task_status(task.task_id, TaskStatus.SUCCESS, task.result)
                elif isinstance(result, dict):
                    is_success = result.get("success", False)
                    if is_success:
                        task.status = TaskStatus.SUCCESS
                        task.result = result
                        self.state_machine.update_task_status(task.task_id, TaskStatus.SUCCESS, result)

                if is_success:
                    return {"action_taken": "retry_success", "retry_count": task.retry_count}
                else:
                    logger.warning(f"重试结果仍失败: {result}")
                    return await self._handle_retry(task, retry_func)
            except Exception as e:
                logger.warning(f"重试异常: {e}")
                return await self._handle_retry(task, retry_func)

        return {"action_taken": "retry_scheduled", "retry_count": task.retry_count}

    async def _handle_fallback(self, task: Task) -> Dict[str, Any]:
        """L2: 备选方案策略 — 切换工具并立即执行"""
        if not task.fallback_tool:
            logger.warning(f"任务 {task.task_id} 无备选方案，标记为 FAILED")
            task.status = TaskStatus.FAILED
            self.state_machine.update_task_status(task.task_id, TaskStatus.FAILED)
            return {"action_taken": "no_fallback", "status": "FAILED"}

        original_tool = task.tool_name
        original_params = task.params.copy()

        # 交换主方案和备选方案
        task.tool_name = task.fallback_tool
        task.params = task.fallback_params or {}
        task.fallback_tool = original_tool
        task.fallback_params = original_params

        logger.info(f"任务 {task.task_id} 切换到备选方案: {task.tool_name}，立即执行")

        # 立即执行备选工具
        if self.tool_registry:
            tool = self.tool_registry.get(task.tool_name)
            if tool:
                try:
                    result = await tool(task.params)
                    if result.success:
                        task.status = TaskStatus.SUCCESS
                        task.result = result.data
                        self.state_machine.update_task_status(task.task_id, TaskStatus.SUCCESS, result.data)
                        return {
                            "action_taken": "fallback_success",
                            "original_tool": original_tool,
                            "new_tool": task.tool_name,
                            "fallback_result": result.data,
                        }
                    else:
                        logger.warning(f"备选方案也失败: {result.error_message}")
                        task.status = TaskStatus.FAILED
                        self.state_machine.update_task_status(task.task_id, TaskStatus.FAILED, error=result.error_message)
                        return {
                            "action_taken": "fallback_failed",
                            "original_tool": original_tool,
                            "new_tool": task.tool_name,
                        }
                except Exception as e:
                    logger.error(f"备选方案执行异常: {e}")
                    task.status = TaskStatus.FAILED
                    self.state_machine.update_task_status(task.task_id, TaskStatus.FAILED, error=str(e))
                    return {
                        "action_taken": "fallback_failed",
                        "original_tool": original_tool,
                        "new_tool": task.tool_name,
                    }

        # 没有 tool_registry，只做切换，标记为 FALLBACK 等待外部执行
        task.status = TaskStatus.FALLBACK
        self.state_machine.update_task_status(task.task_id, TaskStatus.FALLBACK)
        return {
            "action_taken": "fallback",
            "original_tool": original_tool,
            "new_tool": task.tool_name,
        }

    def _handle_replan(self, task: Task, reason: str) -> Dict[str, Any]:
        """L3: 重新规划策略"""
        logger.info(f"触发重新规划，原因: {reason}")

        # 将当前任务标记为失败
        task.status = TaskStatus.FAILED
        self.state_machine.update_task_status(task.task_id, TaskStatus.FAILED)

        # 切换状态机到 ERROR 状态，再到 PLANNING 状态
        # EXECUTING -> ERROR -> PLANNING
        self.state_machine.transition_to(AgentState.ERROR)
        self.state_machine.transition_to(AgentState.PLANNING)

        # 将原因保存到上下文，供规划引擎使用
        self.state_machine.context["replan_reason"] = reason
        self.state_machine.context["replan_trigger_task"] = task.task_id

        return {
            "action_taken": "replan",
            "reason": reason,
            "trigger_task": task.task_id,
        }

    def _handle_fatal(self, task: Task, error_message: str) -> Dict[str, Any]:
        """致命错误处理"""
        logger.error(f"致命错误: {error_message}")

        task.status = TaskStatus.FAILED
        self.state_machine.update_task_status(task.task_id, TaskStatus.FAILED)
        self.state_machine.transition_to(AgentState.CANCELLED)

        return {
            "action_taken": "cancel",
            "reason": error_message,
        }

    def generate_user_notification(self, result: Dict[str, Any]) -> str:
        """
        生成用户通知消息

        Args:
            result: handle_error 的返回结果

        Returns:
            适合展示给用户的通知文本
        """
        action = result.get("action_taken")
        task_id = result.get("task_id")

        if action == "retry_success":
            return f"任务 {task_id} 已自动重试成功，继续执行。"

        if action == "retry_scheduled":
            count = result.get("retry_count", 0)
            return f"遇到临时问题，正在第 {count} 次重试中..."

        if action in ("fallback", "fallback_success", "fallback_failed"):
            original = result.get("original_tool", "")
            new = result.get("new_tool", "")
            if action == "fallback_success":
                return f"原方案暂时不可用，已自动切换到备选方案并执行成功。"
            if action == "fallback_failed":
                return f"原方案和备选方案均不可用，任务已跳过。"
            return (
                f"原方案暂时不可用，已为您切换到备选方案。\n"
                f"原方案: {original}\n"
                f"新方案: {new}"
            )

        if action == "replan":
            reason = result.get("reason", "未知原因")
            return f"检测到环境变化（{reason}），正在为您重新规划行程..."

        if action == "cancel":
            return "遇到了无法处理的问题，任务已取消。请联系客服获取帮助。"

        if action == "no_fallback":
            return f"任务 {task_id} 暂时无法完成，已跳过。"

        return "处理中..."
