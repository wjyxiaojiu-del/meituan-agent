"""
会话管理模块
支持多轮对话和上下文理解
"""

import json
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """对话消息"""
    role: str  # user / assistant / system
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class ConversationState:
    """对话状态"""
    session_id: str
    messages: List[Message] = field(default_factory=list)
    current_intent: Optional[Dict[str, Any]] = None
    current_plan: Optional[Dict[str, Any]] = None
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None):
        """添加消息"""
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(message)
        self.updated_at = datetime.now()

    def get_recent_messages(self, count: int = 10) -> List[Dict[str, str]]:
        """获取最近的消息"""
        recent = self.messages[-count:] if len(self.messages) > count else self.messages
        return [{"role": m.role, "content": m.content} for m in recent]

    def get_conversation_history(self) -> str:
        """获取对话历史摘要"""
        if not self.messages:
            return ""

        history_parts = []
        for msg in self.messages[-6:]:  # 最近6条消息
            role_name = "用户" if msg.role == "user" else "助手"
            history_parts.append(f"{role_name}: {msg.content[:100]}...")

        return "\n".join(history_parts)

    def update_intent(self, intent: Dict[str, Any]):
        """更新当前意图"""
        self.current_intent = intent
        self.updated_at = datetime.now()

    def update_plan(self, plan: Dict[str, Any]):
        """更新当前计划"""
        self.current_plan = plan
        self.updated_at = datetime.now()

    def get_context_summary(self) -> Dict[str, Any]:
        """获取上下文摘要"""
        return {
            "session_id": self.session_id,
            "message_count": len(self.messages),
            "current_intent": self.current_intent,
            "has_plan": self.current_plan is not None,
            "context": self.context
        }


class SessionManager:
    """会话管理器"""

    def __init__(self, max_sessions: int = 100, session_timeout: int = 3600):
        """
        初始化会话管理器

        Args:
            max_sessions: 最大会话数
            session_timeout: 会话超时时间（秒）
        """
        self.sessions: Dict[str, ConversationState] = {}
        self.max_sessions = max_sessions
        self.session_timeout = session_timeout

    def create_session(self) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())[:8]
        self.sessions[session_id] = ConversationState(session_id=session_id)
        logger.info(f"创建新会话: {session_id}")

        # 清理过期会话
        self._cleanup_sessions()

        return session_id

    def get_session(self, session_id: str) -> Optional[ConversationState]:
        """获取会话"""
        return self.sessions.get(session_id)

    def get_or_create_session(self, session_id: Optional[str] = None) -> ConversationState:
        """获取或创建会话"""
        if session_id and session_id in self.sessions:
            return self.sessions[session_id]

        new_session_id = self.create_session()
        return self.sessions[new_session_id]

    def add_message(self, session_id: str, role: str, content: str, metadata: Dict[str, Any] = None):
        """添加消息到会话"""
        session = self.get_session(session_id)
        if session:
            session.add_message(role, content, metadata)

    def _cleanup_sessions(self):
        """清理过期会话"""
        now = datetime.now()
        expired_sessions = []

        for session_id, session in self.sessions.items():
            if (now - session.updated_at).total_seconds() > self.session_timeout:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            del self.sessions[session_id]
            logger.info(f"清理过期会话: {session_id}")

        # 如果超过最大会话数，删除最旧的
        if len(self.sessions) > self.max_sessions:
            sorted_sessions = sorted(
                self.sessions.items(),
                key=lambda x: x[1].updated_at
            )
            sessions_to_remove = len(self.sessions) - self.max_sessions
            for i in range(sessions_to_remove):
                session_id = sorted_sessions[i][0]
                del self.sessions[session_id]
                logger.info(f"清理旧会话: {session_id}")


class ContextBuilder:
    """上下文构建器"""

    @staticmethod
    def build_context_for_intent(
        user_input: str,
        session: ConversationState
    ) -> List[Dict[str, str]]:
        """
        为意图解析构建上下文

        Args:
            user_input: 用户输入
            session: 会话状态

        Returns:
            消息列表
        """
        messages = []

        # 添加对话历史
        recent_messages = session.get_recent_messages(6)
        messages.extend(recent_messages)

        # 添加当前用户输入
        messages.append({"role": "user", "content": user_input})

        return messages

    @staticmethod
    def build_context_for_modification(
        user_input: str,
        session: ConversationState
    ) -> Dict[str, Any]:
        """
        为修改请求构建上下文

        Args:
            user_input: 用户输入
            session: 会话状态

        Returns:
            上下文字典
        """
        context = {
            "user_input": user_input,
            "has_existing_plan": session.current_plan is not None,
            "existing_intent": session.current_intent,
            "conversation_history": session.get_conversation_history()
        }

        # 如果有现有计划，添加计划摘要
        if session.current_plan:
            plan_summary = {
                "task_count": len(session.current_plan.get("tasks", [])),
                "tasks": [
                    {
                        "id": t.get("task_id"),
                        "name": t.get("name"),
                        "status": t.get("status")
                    }
                    for t in session.current_plan.get("tasks", [])
                ]
            }
            context["existing_plan_summary"] = plan_summary

        return context

    @staticmethod
    def detect_modification_intent(user_input: str) -> bool:
        """
        检测是否是修改请求

        Args:
            user_input: 用户输入

        Returns:
            是否是修改请求
        """
        modification_keywords = [
            "把", "换成", "改成", "不要", "取消", "换一个",
            "修改", "调整", "变更", "替代", "换成", "换掉",
            "不需要", "不要了", "去掉", "删除"
        ]

        return any(keyword in user_input for keyword in modification_keywords)

    @staticmethod
    def extract_modification_target(user_input: str) -> Optional[str]:
        """
        提取修改目标

        Args:
            user_input: 用户输入

        Returns:
            修改目标（如 "餐厅", "活动" 等）
        """
        targets = {
            "餐厅": ["餐厅", "饭店", "火锅", "烧烤", "吃饭"],
            "活动": ["活动", "玩", "游乐", "娱乐"],
            "时间": ["时间", "几点", "早上", "下午", "晚上"],
            "地点": ["地点", "地方", "位置", "哪里"],
            "配送": ["配送", "鲜花", "蛋糕", "礼物"]
        }

        for target, keywords in targets.items():
            if any(keyword in user_input for keyword in keywords):
                return target

        return None
