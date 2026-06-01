"""
响应组装服务
从 Planner 中提取的摘要、故事检测、分享文案等逻辑
"""

import logging
from typing import Dict, Any, Optional, List

from ..state_machine import Task
from ..session import ConversationState
from ...llm.client import LLMClient

logger = logging.getLogger(__name__)


def aggregate_capabilities(tasks: List[Task]) -> Dict[str, int]:
    """Count Meituan capability_tag occurrences across tasks.

    Returns ordered insertion dict like {"团购券": 2, "闪送": 1, "会员折扣": 1}.
    Used by both plan summary and share text to render "美团味" copy.
    """
    counts: Dict[str, int] = {}
    seen_per_task: set = set()  # prevent double-count when a task has same tag twice
    for t in tasks or []:
        params = getattr(t, "params", {}) or {}
        tags = params.get("capability_tags") or []
        if not isinstance(tags, list):
            continue
        seen = set()
        for tag in tags:
            if not isinstance(tag, str) or tag in seen:
                continue
            seen.add(tag)
            counts[tag] = counts.get(tag, 0) + 1
    _ = seen_per_task
    return counts


def format_capability_phrase(counts: Dict[str, int]) -> str:
    """Render {"团购券":2,"闪送":1} → "用到了 团购券×2、闪送×1"."""
    if not counts:
        return ""
    parts = [f"{tag}×{n}" if n > 1 else tag for tag, n in counts.items()]
    return "用到了 " + "、".join(parts)


class ResponseService:
    """响应组装服务"""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def detect_story_intent(self, user_input: str) -> bool:
        """检测用户是否想要故事剧情（仅在用户明确请求时触发）"""
        # 先检查否定模式
        no_story_keywords = ["不要故事", "不要剧情", "简单点", "不用剧本", "不需要故事", "不要剧本杀", "不想要故事"]
        if any(kw in user_input for kw in no_story_keywords):
            return False
        # 再检查肯定关键词
        story_keywords = [
            "剧情", "剧本杀", "悬疑", "探案", "冒险", "挑战",
            "有剧情", "沉浸", "角色扮演", "闯关", "解谜", "Citywalk",
            "剧本", "推理", "密室", "恐怖", "科幻", "武侠", "古风",
        ]
        return any(kw in user_input for kw in story_keywords)

    async def generate_plan_summary(
        self,
        intent: Dict[str, Any],
        route_info: Optional[List[Dict]],
        tasks: List[Task],
    ) -> str:
        """生成人类可读的方案摘要（LLM 生成个性化内容）"""
        if not self.llm_client or not self.llm_client.is_available():
            return self.default_plan_summary(intent, route_info, tasks)

        route_text = ""
        if route_info:
            route_text = " → ".join(
                f"{r['arrival_time']} {r['poi_name']}" for r in route_info
            )

        prompt = f"你是美团行程推荐官。只输出推荐文案（2-3句话，100字以内），用「你」开头。\n\n用户需求：{intent.get('raw_input', '')}\n路线：{route_text}\n\n要求：像朋友推荐一样亲切。绝对不要输出JSON、代码、分析过程。直接输出文案。"

        try:
            summary = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens_override=300,
            )
            summary = summary.strip()
            # 清理 JSON 泄漏（MiMo 在文本中夹带 intent JSON）
            if "{" in summary:
                first_brace = summary.index("{")
                clean = summary[:first_brace].strip()
                clean = clean.rstrip("\n").strip()
                if len(clean) > 5:
                    summary = clean
                else:
                    logger.warning("LLM 返回 JSON 而非摘要，使用模板")
                    return self.default_plan_summary(intent, route_info, tasks)
            # 过滤掉 MiMo 推理过程
            bad_prefixes = ("首先", "用户", "根据", "需求是", "分析", "好的，")
            if summary.startswith(bad_prefixes) or "需求是" in summary[:20]:
                logger.warning("LLM 返回推理过程而非摘要，使用模板")
                return self.default_plan_summary(intent, route_info, tasks)
            if len(summary) > 5:
                return summary
            logger.warning("LLM 方案摘要过短，使用模板")
            return self.default_plan_summary(intent, route_info, tasks)
        except Exception as e:
            logger.warning(f"生成方案摘要失败: {e}")
            return self.default_plan_summary(intent, route_info, tasks)

    async def generate_plan_summary_stream(
        self,
        intent: Dict[str, Any],
        route_info: Optional[List[Dict]],
        tasks: List[Task],
    ):
        """流式生成方案摘要，yield 每个文本 chunk"""
        if not self.llm_client or not self.llm_client.is_available():
            yield self.default_plan_summary(intent, route_info, tasks)
            return

        route_text = ""
        if route_info:
            route_text = " → ".join(
                f"{r['arrival_time']} {r['poi_name']}" for r in route_info
            )

        prompt = f"你是美团行程推荐官。只输出推荐文案（2-3句话，100字以内），用「你」开头。\n\n用户需求：{intent.get('raw_input', '')}\n路线：{route_text}\n\n要求：像朋友推荐一样亲切。绝对不要输出JSON、代码、分析过程。直接输出文案。"

        try:
            # 缓冲模式：先收集完整文本，验证后再 yield（摘要只有 100 字，缓冲无感知）
            full_text = ""
            async for chunk in self.llm_client.chat_stream(
                messages=[{"role": "user", "content": prompt}],
                max_tokens_override=300,
            ):
                full_text += chunk

            # 检查是否是推理过程而非摘要
            bad_prefixes = ("首先", "用户", "根据", "需求是", "分析", "好的，")
            if full_text.startswith(bad_prefixes) or "需求是" in full_text[:20]:
                logger.warning("LLM 流式返回推理过程，使用模板")
                yield self.default_plan_summary(intent, route_info, tasks)
            elif len(full_text.strip()) > 5:
                yield full_text.strip()
            else:
                yield self.default_plan_summary(intent, route_info, tasks)
        except Exception as e:
            logger.warning(f"流式摘要生成失败: {e}")
            yield self.default_plan_summary(intent, route_info, tasks)

    async def regenerate_summary(
        self,
        intent: Dict[str, Any],
        route_info: Optional[List[Dict]],
        tasks: List[Task],
        change_log: List[Dict[str, Any]],
    ) -> str:
        """根据 change_log 生成"调整后"的简短回复（patch 路径专用）"""
        prefix = self._format_change_summary(change_log)
        route_text = ""
        if route_info:
            route_text = " → ".join(
                f"{r['arrival_time']} {r['poi_name']}" for r in route_info
            )

        if not self.llm_client or not self.llm_client.is_available():
            return f"{prefix}\n新方案：{route_text}" if route_text else prefix

        prompt = (
            "你是美团行程推荐官。用户对原方案做了调整，请用 1-2 句话确认调整结果（不超过 80 字），"
            "用「你」开头，亲切自然，不要输出 JSON 或分析过程。\n\n"
            f"用户调整：{intent.get('raw_input', '')}\n"
            f"调整摘要：{prefix}\n"
            f"新路线：{route_text}"
        )
        try:
            text = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens_override=200,
            )
            text = text.strip()
            if "{" in text:
                text = text.split("{", 1)[0].strip()
            if len(text) < 5:
                return f"{prefix}\n新方案：{route_text}" if route_text else prefix
            return text
        except Exception as e:
            logger.warning(f"重新生成摘要失败: {e}")
            return f"{prefix}\n新方案：{route_text}" if route_text else prefix

    @staticmethod
    def _format_change_summary(change_log: List[Dict[str, Any]]) -> str:
        """把 change_log 渲染成一句中文摘要。"""
        if not change_log:
            return "已为你更新方案。"
        msgs = []
        for entry in change_log:
            kind = entry.get("type")
            if kind == "replace":
                before = entry.get("before", {}).get("name", "")
                after = entry.get("after", {}).get("name", "")
                msgs.append(f"已把「{before}」换成「{after}」")
            elif kind == "remove":
                removed = entry.get("removed", {}).get("name", "")
                msgs.append(f"已删除「{removed}」")
            elif kind == "insert":
                inserted = entry.get("inserted", {}).get("name", "")
                msgs.append(f"已加入「{inserted}」")
            elif kind == "shift_time":
                new_start = entry.get("new_start", "")
                msgs.append(f"已调整出发时间到 {new_start}")
            elif kind == "preference_noted":
                noted = entry.get("noted", {})
                tag = noted.get("category") or noted.get("location") or noted.get("tag") or "你的偏好"
                msgs.append(f"好的，记下了：下次不再推荐「{tag}」")
            elif kind == "error":
                msgs.append(entry.get("message", "调整失败"))
        return "；".join(msgs)

    def default_plan_summary(
        self,
        intent: Dict[str, Any],
        route_info: Optional[List[Dict]],
        tasks: List[Task],
    ) -> str:
        """默认方案摘要（模板生成）"""
        parts = ["已为你规划好行程！"]

        people = intent.get("people", [])
        role_counts = {}
        has_self = False
        for p in people:
            role = p.get("role", "")
            if role == "self":
                has_self = True
            else:
                role_counts[role] = role_counts.get(role, 0) + 1
        people_desc = []
        if has_self or role_counts:
            people_desc.append("你")
        role_labels = {"child": "孩子", "wife": "另一半", "husband": "另一半",
                       "friend": "朋友", "colleague": "同事"}
        for role, count in role_counts.items():
            label = role_labels.get(role, role)
            if role == "child":
                age = next((p.get("age", "") for p in people if p.get("role") == "child"), "")
                label = f"孩子({age}岁)" if age else "孩子"
            if count > 1:
                people_desc.append(f"{count}位{label}")
            else:
                people_desc.append(label)
        if people_desc:
            if len(people_desc) == 1:
                parts.append(f"和{people_desc[0]}一起出发。")
            else:
                parts.append(f"{'和'.join(people_desc)}一起出发。")

        if route_info:
            stops = " → ".join(r["poi_name"] for r in route_info)
            parts.append(f"路线：{stops}。")

            # 提取时间范围
            if len(route_info) >= 2:
                start_t = route_info[0].get("arrival_time", "")
                end_t = route_info[-1].get("departure_time", "")
                if start_t and end_t:
                    parts.append(f"预计 {start_t} 出发，{end_t} 结束。")

        surprise = intent.get("surprise", False)
        if surprise:
            parts.append("还为你准备了惊喜环节！")

        # 计算团购优惠
        if route_info:
            total_original = 0
            total_coupon = 0
            for r in route_info:
                coupon = r.get("coupon_price")
                original = r.get("original_price")
                if coupon is not None and original is not None:
                    total_original += original
                    total_coupon += coupon
                else:
                    total_original += r.get("price_per_person", 0)
                    total_coupon += r.get("price_per_person", 0)
            if total_original > total_coupon:
                saved = total_original - total_coupon
                parts.append(f"已为你匹配最优团购，预计节省 ¥{int(saved)}。")

        # Surface Meituan capabilities actually used (团购券/闪送/会员折扣 ...)
        cap_phrase = format_capability_phrase(aggregate_capabilities(tasks))
        if cap_phrase:
            parts.append(cap_phrase + "。")

        parts.append(f"共 {len(tasks)} 个任务，马上开始执行。")
        return " ".join(parts)

    async def generate_share_text(
        self,
        session: ConversationState,
        result: Dict[str, Any],
    ) -> str:
        """生成分享给朋友的文案（LLM 生成自然语言）"""
        # Surface capabilities so the share copy can flex "美团味"
        tasks = result.get("tasks") or []
        cap_counts = aggregate_capabilities(tasks)
        cap_phrase = format_capability_phrase(cap_counts)
        fallback = "行程已安排好，具体细节稍后分享给你～"
        if cap_phrase:
            fallback = f"行程都搞定啦，{cap_phrase}，到点直接出发～"

        if not self.llm_client or not self.llm_client.is_available():
            return fallback

        plan_summary = session.context.get("plan_summary", "")
        # 取前100字避免 prompt 过长
        short_summary = plan_summary[:100] if plan_summary else ""

        cap_hint = f"\n本次美团能力：{cap_phrase}。请自然提一句，不要堆砌。" if cap_phrase else ""
        prompt = f"直接输出微信消息内容，不要解释。行程安排好了：{short_summary}{cap_hint}\n\n帮我写一句发给朋友的微信通知（30字以内），口语化，不剧透惊喜。直接写内容。"

        try:
            share_text = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens_override=100,
            )
            share_text = share_text.strip()
            # 过滤推理过程
            if share_text and (share_text.startswith("首先") or share_text.startswith("用户") or "需求是" in share_text[:20]):
                return fallback
            return share_text if share_text else fallback
        except Exception as e:
            logger.warning(f"生成分享文案失败: {e}")
            return fallback

    async def generate_conversational_reply(
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
