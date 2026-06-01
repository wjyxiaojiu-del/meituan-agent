"""
意图解析服务
从 Planner 中提取的意图解析相关逻辑
"""

import json
import re
import logging
from typing import Dict, Any, Optional

from ..session import ConversationState, ContextBuilder
from ...llm.client import LLMClient
from ...llm.prompts import IntentPrompts

logger = logging.getLogger(__name__)


class IntentService:
    """意图解析服务"""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

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
                system_prompt = self.build_modification_prompt(context_info)
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

        # 规则兜底：提取用户指定的具体 POI（LLM 可能漏提取）
        if not intent.get("specific_pois"):
            extracted = self.extract_specific_pois(user_input)
            if extracted:
                intent["specific_pois"] = extracted
                intent["route_ordered"] = True
                logger.info(f"规则提取到用户指定 POI: {extracted}")

        # 如果没有识别到 "self"，自动添加
        if not any(p.get("role") == "self" for p in intent["people"]):
            intent["people"].append({"role": "self"})

        # 如果有会话，合并历史意图信息
        if session and session.current_intent:
            intent = self.merge_with_history(intent, session.current_intent)

        logger.info(f"LLM 意图解析结果: {intent}")
        return intent

    def extract_specific_pois(self, user_input: str) -> Optional[list]:
        """规则兜底：从用户输入中提取指定的 POI 名称"""
        # 模式1: "A → B → C" 或 "A->B->C" 或 "A—B—C"
        arrow_pattern = r'[→\->—–\|｜]'
        if re.search(arrow_pattern, user_input):
            parts = re.split(arrow_pattern, user_input)
            # 清理每个部分，去掉前后缀文字
            prefix_re = r'^(帮我规划这条路线|帮我请|规划这条路线|帮我|请|这条路线|路线|先去|再去|然后去|最后去|按顺序|游玩|等|从|到|去)[：:：\s]*'
            suffix_re = r'[，,。！？!?\s]*(按顺序游玩|按顺序|游玩|等|吧|呗|好不好|可以吗|帮我|请)[，,。！？!?\s]*$'
            pois = []
            for part in parts:
                cleaned = re.sub(prefix_re, '', part.strip())
                cleaned = re.sub(suffix_re, '', cleaned)
                cleaned = cleaned.strip(' ，。！？,.!?')
                if cleaned and len(cleaned) >= 2:
                    pois.append(cleaned)
            if len(pois) >= 2:
                return pois

        # 模式2: "先去A，再去B，最后去C"
        go_pattern = r'(?:先去|再去|然后去|最后去|去)\s*([^\s，,、。！？!?]+)'
        matches = re.findall(go_pattern, user_input)
        if len(matches) >= 2:
            return matches

        return None

    def build_modification_prompt(self, context_info: Dict[str, Any]) -> str:
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

    def merge_with_history(
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
