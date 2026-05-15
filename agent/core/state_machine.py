"""
状态机管理模块
管理 Agent 的执行状态和状态转换
"""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime


class AgentState(Enum):
    """Agent 状态枚举"""
    PLANNING = "PLANNING"       # 规划中
    EXECUTING = "EXECUTING"     # 执行中
    ERROR = "ERROR"             # 错误处理中
    COMPLETED = "COMPLETED"     # 完成
    CANCELLED = "CANCELLED"     # 取消


class TaskStatus(Enum):
    """单个任务状态"""
    PENDING = "PENDING"         # 待执行
    RUNNING = "RUNNING"         # 执行中
    SUCCESS = "SUCCESS"         # 成功
    FAILED = "FAILED"           # 失败
    RETRYING = "RETRYING"       # 重试中
    FALLBACK = "FALLBACK"       # 使用备选方案
    SKIPPED = "SKIPPED"         # 跳过


class Task:
    """任务定义"""

    def __init__(
        self,
        task_id: str,
        name: str,
        tool_name: str,
        params: Dict[str, Any],
        priority: int = 0,
        dependencies: Optional[list] = None,
        fallback_tool: Optional[str] = None,
        fallback_params: Optional[Dict[str, Any]] = None,
    ):
        self.task_id = task_id
        self.name = name
        self.tool_name = tool_name
        self.params = params
        self.priority = priority
        self.dependencies = dependencies or []
        self.fallback_tool = fallback_tool
        self.fallback_params = fallback_params

        self.status = TaskStatus.PENDING
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.retry_count = 0
        self.max_retries = 3
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "tool_name": self.tool_name,
            "params": self.params,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
        }


class StateMachine:
    """
    状态机管理器
    管理整个 Agent 的执行流程
    """

    def __init__(self):
        self.state = AgentState.PLANNING
        self.tasks: Dict[str, Task] = {}
        self.context: Dict[str, Any] = {}  # 共享上下文
        self.history: list = []  # 状态变更历史
        self._record_transition("INIT", AgentState.PLANNING)

    def _record_transition(self, from_state: str, to_state: AgentState):
        """记录状态转换"""
        self.history.append({
            "from": from_state,
            "to": to_state.value,
            "timestamp": datetime.now().isoformat(),
        })

    def transition_to(self, new_state: AgentState) -> bool:
        """
        状态转换
        定义合法的状态转换规则
        """
        valid_transitions = {
            AgentState.PLANNING: [AgentState.EXECUTING, AgentState.CANCELLED],
            AgentState.EXECUTING: [AgentState.ERROR, AgentState.COMPLETED, AgentState.CANCELLED],
            AgentState.ERROR: [AgentState.EXECUTING, AgentState.PLANNING, AgentState.CANCELLED],
            AgentState.COMPLETED: [],  # 终态
            AgentState.CANCELLED: [],  # 终态
        }

        if new_state in valid_transitions.get(self.state, []):
            old_state = self.state
            self.state = new_state
            self._record_transition(old_state.value, new_state)
            return True
        return False

    def add_task(self, task: Task):
        """添加任务"""
        self.tasks[task.task_id] = task

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self.tasks.get(task_id)

    def update_task_status(self, task_id: str, status: TaskStatus, result=None, error=None):
        """更新任务状态"""
        task = self.tasks.get(task_id)
        if task:
            task.status = status
            task.updated_at = datetime.now()
            if result is not None:
                task.result = result
            if error is not None:
                task.error = error

    def get_pending_tasks(self) -> list:
        """获取待执行的任务（依赖已满足）"""
        pending = []
        for task in self.tasks.values():
            if task.status == TaskStatus.PENDING:
                # 检查依赖是否都已完成
                deps_met = all(
                    self.tasks.get(dep) and self.tasks[dep].status == TaskStatus.SUCCESS
                    for dep in task.dependencies
                )
                if deps_met:
                    pending.append(task)
        return sorted(pending, key=lambda t: t.priority, reverse=True)

    def has_failed_tasks(self) -> bool:
        """是否有失败的任务"""
        return any(t.status == TaskStatus.FAILED for t in self.tasks.values())

    def all_tasks_completed(self) -> bool:
        """所有任务是否完成（包括成功、跳过、失败、使用备选方案）"""
        terminal_states = {TaskStatus.SUCCESS, TaskStatus.SKIPPED, TaskStatus.FAILED, TaskStatus.FALLBACK}
        return all(t.status in terminal_states for t in self.tasks.values())

    def get_execution_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        status_counts = {}
        for task in self.tasks.values():
            status_counts[task.status.value] = status_counts.get(task.status.value, 0) + 1

        return {
            "current_state": self.state.value,
            "total_tasks": len(self.tasks),
            "status_counts": status_counts,
            "tasks": [t.to_dict() for t in self.tasks.values()],
        }

    def reset(self):
        """重置状态机，为下一次执行做准备"""
        self.state = AgentState.PLANNING
        self.tasks = {}
        self.context = {}
        self._record_transition("RESET", AgentState.PLANNING)
