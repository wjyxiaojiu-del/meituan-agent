"""
请求上下文模块
使用 contextvars 实现跨 service 的 trace_id 和性能计时
"""

import time
import logging
from contextvars import ContextVar
from typing import Optional, Dict, Any

# 请求级上下文变量
trace_id_var: ContextVar[str] = ContextVar('trace_id', default='')
session_id_var: ContextVar[str] = ContextVar('session_id', default='')
timings_var: ContextVar[Dict[str, float]] = ContextVar('timings', default={})

logger = logging.getLogger(__name__)


def set_trace_id(trace_id: str):
    """设置当前请求的 trace_id"""
    trace_id_var.set(trace_id)


def get_trace_id() -> str:
    """获取当前请求的 trace_id"""
    return trace_id_var.get()


def set_session_id(session_id: str):
    """设置当前请求的 session_id"""
    session_id_var.set(session_id)


def get_session_id() -> str:
    """获取当前请求的 session_id"""
    return session_id_var.get()


class TimingContext:
    """性能计时上下文管理器"""

    def __init__(self, name: str):
        self.name = name
        self.start_time: float = 0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.perf_counter() - self.start_time
        timings = timings_var.get()
        timings[self.name] = round(elapsed * 1000, 1)  # 毫秒
        timings_var.set(timings)
        logger.info(f"[timing] {self.name}: {elapsed*1000:.1f}ms")
        return False


def get_timings() -> Dict[str, float]:
    """获取当前请求的所有计时"""
    return timings_var.get().copy()


def reset_context():
    """重置所有上下文变量（每个请求开始时调用）"""
    trace_id_var.set('')
    session_id_var.set('')
    timings_var.set({})


class ContextLogger:
    """带上下文的日志适配器"""

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def _log(self, level: int, msg: str, *args, **kwargs):
        trace_id = get_trace_id()
        session_id = get_session_id()
        extra_msg = f" [trace={trace_id}]" if trace_id else ""
        extra_msg += f" [session={session_id}]" if session_id else ""
        self._logger.log(level, msg + extra_msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self._log(logging.ERROR, msg, *args, **kwargs)
