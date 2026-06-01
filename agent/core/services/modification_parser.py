"""
Modification parser - rule-first multi-turn dialogue parser

Parses user utterances like "把餐厅换成火锅" / "第二个换一家" / "不要去三里屯"
into structured ModificationAction objects. Rule-based first, LLM fallback
handled by the caller.

Design notes:
- Rule-based path: deterministic, fast, no LLM call.
- Each action_type maps to a patch operation in plan_patch_service.
- Confidence: rule=1.0, LLM fallback=0.6 (set by caller).
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ModificationAction:
    """One structured modification request."""

    action_type: str  # replace | remove | insert | shift_time | declare_dislike
    target_ref: Optional[str] = None         # resolved task_id
    target_poi_id: Optional[str] = None      # resolved poi_id
    target_hint: Dict[str, Any] = field(default_factory=dict)
    new_category: Optional[str] = None
    new_tag: Optional[str] = None            # e.g. "火锅" within category "餐厅"
    new_poi_name: Optional[str] = None
    time_delta_min: Optional[int] = None     # +N = later, -N = earlier
    absolute_start: Optional[str] = None     # "HH:MM" for "改成晚上7点"
    confidence: float = 1.0
    raw: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "target_ref": self.target_ref,
            "target_poi_id": self.target_poi_id,
            "target_hint": self.target_hint,
            "new_category": self.new_category,
            "new_tag": self.new_tag,
            "new_poi_name": self.new_poi_name,
            "time_delta_min": self.time_delta_min,
            "absolute_start": self.absolute_start,
            "confidence": self.confidence,
            "raw": self.raw,
        }


# Category synonym table - maps user wording to POI.category strings
CATEGORY_SYNONYMS = {
    "餐厅": "餐厅", "饭店": "餐厅", "吃饭": "餐厅", "吃的": "餐厅",
    "火锅": "餐厅",  # 火锅 is a 餐厅 with tag=火锅, handled specially
    "本帮菜": "餐厅", "西餐": "餐厅", "日料": "餐厅", "烧烤": "餐厅",
    "ktv": "KTV", "KTV": "KTV", "K歌": "KTV",
    "咖啡": "咖啡馆", "咖啡馆": "咖啡馆",
    "奶茶": "甜品店", "甜品": "甜品店",
    "电影": "电影院", "电影院": "电影院",
    "密室": "密室逃脱", "密室逃脱": "密室逃脱",
    "剧本杀": "剧本杀",
    "桌游": "桌游",
    "儿童乐园": "儿童乐园", "游乐": "儿童乐园", "乐园": "儿童乐园",
    "花": "花店",
    "公园": "公园", "博物馆": "博物馆", "动物园": "动物园",
}

# Tag-specific category hints (when wording implies a specific tag within a category)
TAG_HINTS = {
    "火锅": "火锅",
    "本帮菜": "本帮菜",
    "西餐": "西餐",
    "日料": "日料",
    "烧烤": "烧烤",
}

POSITION_WORDS = {
    "第一": 0, "第一个": 0, "首个": 0, "开头": 0,
    "第二": 1, "第二个": 1,
    "第三": 2, "第三个": 2,
    "第四": 3, "第四个": 3,
    "第五": 4, "第五个": 4,
    "最后": -1, "最后一个": -1, "末尾": -1, "最后那个": -1,
    "中间": "middle",
}

REPLACE_KEYWORDS = ["换成", "改成", "替换", "换为", "换一个", "换一家", "改为"]
REMOVE_KEYWORDS = ["不要", "去掉", "删掉", "取消", "去除", "不去", "不需要", "删除"]
INSERT_KEYWORDS = ["加一个", "加一家", "加个", "再去", "再加", "加上", "增加"]
SHIFT_LATER = ["晚一点", "推迟", "迟一点", "晚点开始", "晚点"]
SHIFT_EARLIER = ["早一点", "提前", "早点开始", "早点"]
DISLIKE_KEYWORDS = ["下次别推", "下次别去", "下次别", "我不喜欢", "别再推", "下次不要"]


def parse(
    user_input: str,
    pending_tasks: List[Any] = None,
    pending_route: List[Any] = None,
    context: Dict[str, Any] = None,
) -> Optional[ModificationAction]:
    """Rule-based parse. Returns None if no rule matches."""
    text = user_input.strip()
    pending_tasks = pending_tasks or []
    pending_route = pending_route or []
    context = context or {}

    # Order matters: dislike before remove (declare_dislike contains "别")
    for parser_fn in (_try_dislike, _try_shift_time, _try_replace,
                      _try_remove, _try_insert):
        action = parser_fn(text, pending_tasks, pending_route, context)
        if action:
            action.raw = user_input
            resolve_target(action, pending_tasks, pending_route)
            logger.info(f"[mod_parser] rule hit: {action.action_type} - {user_input[:40]}")
            return action
    return None


def _try_replace(text, tasks, route, ctx) -> Optional[ModificationAction]:
    """Replace patterns: '把X换成Y' / '第二个换一家' / '换个火锅'."""
    if not any(kw in text for kw in REPLACE_KEYWORDS):
        return None

    target_hint = _extract_target_hint(text, route)
    new_cat, new_tag, new_name = _extract_new_value(text)

    # If no target hint, no new value, skip
    if not target_hint and not new_cat and not new_name:
        return None

    return ModificationAction(
        action_type="replace",
        target_hint=target_hint or {},
        new_category=new_cat,
        new_tag=new_tag,
        new_poi_name=new_name,
    )


def _try_remove(text, tasks, route, ctx) -> Optional[ModificationAction]:
    """Remove patterns: '不要去X' / '删掉最后那个' / '不要KTV了'."""
    if not any(kw in text for kw in REMOVE_KEYWORDS):
        return None
    # Avoid false positive with "不要太晚" / "不要太贵" (constraint, not removal)
    if re.search(r"不要太|不要超|不要超过", text):
        return None

    target_hint = _extract_target_hint(text, route)
    if not target_hint:
        return None

    return ModificationAction(
        action_type="remove",
        target_hint=target_hint,
    )


def _try_insert(text, tasks, route, ctx) -> Optional[ModificationAction]:
    """Insert patterns: '再加一家咖啡' / '中间加个奶茶'."""
    if not any(kw in text for kw in INSERT_KEYWORDS):
        return None

    new_cat, new_tag, new_name = _extract_new_value(text)
    if not new_cat and not new_name:
        return None

    position_hint = {}
    for word, pos in POSITION_WORDS.items():
        if word in text:
            position_hint = {"position": pos}
            break

    return ModificationAction(
        action_type="insert",
        target_hint=position_hint,
        new_category=new_cat,
        new_tag=new_tag,
        new_poi_name=new_name,
    )


def _try_shift_time(text, tasks, route, ctx) -> Optional[ModificationAction]:
    """Shift time patterns: '晚一点开始' / '改成晚上7点'."""
    # Absolute time first: "改成晚上 7 点" / "改到下午3点"
    abs_match = re.search(
        r"(改成|改到|改为|定在|定到)?\s*(早上|上午|中午|下午|晚上)?\s*(\d{1,2})\s*[点:：](\d{0,2})",
        text,
    )
    if abs_match and any(kw in text for kw in ["改成", "改到", "改为", "定在", "定到"]):
        period = abs_match.group(2) or ""
        hour = int(abs_match.group(3))
        minute_str = abs_match.group(4)
        minute = int(minute_str) if minute_str else 0
        if period in ("下午", "晚上") and hour < 12:
            hour += 12
        elif period == "中午" and hour < 12:
            hour = 12
        return ModificationAction(
            action_type="shift_time",
            absolute_start=f"{hour:02d}:{minute:02d}",
        )

    if any(kw in text for kw in SHIFT_LATER):
        delta = _extract_minute_delta(text, default=30)
        return ModificationAction(
            action_type="shift_time",
            time_delta_min=abs(delta),
        )
    if any(kw in text for kw in SHIFT_EARLIER):
        delta = _extract_minute_delta(text, default=30)
        return ModificationAction(
            action_type="shift_time",
            time_delta_min=-abs(delta),
        )
    return None


def _try_dislike(text, tasks, route, ctx) -> Optional[ModificationAction]:
    """Dislike patterns: '下次别推X' / '我不喜欢火锅'."""
    if not any(kw in text for kw in DISLIKE_KEYWORDS):
        return None

    target_hint = _extract_target_hint(text, route)
    if not target_hint:
        # Fallback: try to extract any category mention
        for word, cat in CATEGORY_SYNONYMS.items():
            if word in text:
                target_hint = {"category": cat}
                if word in TAG_HINTS:
                    target_hint["tag"] = TAG_HINTS[word]
                break
    if not target_hint:
        return None

    return ModificationAction(
        action_type="declare_dislike",
        target_hint=target_hint,
    )


def _extract_target_hint(text: str, route: List[Any]) -> Dict[str, Any]:
    """Extract what the user is referring to: index / category / poi_name / location."""
    hint: Dict[str, Any] = {}

    # Position words: 第二个、最后一个
    for word, pos in POSITION_WORDS.items():
        if word in text and pos != "middle":
            hint["index"] = pos
            return hint

    # Explicit POI name match against current route
    if route:
        for i, node in enumerate(route):
            poi_name = getattr(node.poi, "name", "") if hasattr(node, "poi") else ""
            if poi_name and poi_name in text:
                hint["poi_name"] = poi_name
                hint["index"] = i
                return hint

    # Category mention
    for word, cat in CATEGORY_SYNONYMS.items():
        if word in text:
            hint["category"] = cat
            if word in TAG_HINTS:
                hint["tag"] = TAG_HINTS[word]
            return hint

    # Location (very rough: anything before 附近/那边)
    loc_match = re.search(r"(三里屯|工体|国贸|王府井|南锣|后海|望京)", text)
    if loc_match:
        hint["location"] = loc_match.group(1)
    return hint


def _extract_new_value(text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract the new category / tag / explicit POI name from a replace/insert request."""
    # Look for content after replace keywords
    new_cat: Optional[str] = None
    new_tag: Optional[str] = None
    new_name: Optional[str] = None

    # "换成 X" / "改成 X" / "加个 X"
    for kw in REPLACE_KEYWORDS + INSERT_KEYWORDS:
        if kw in text:
            after = text.split(kw, 1)[1].strip()
            # Strip trailing punctuation/particles
            after = re.sub(r"[，。！？吧呗呀啊的了]+$", "", after).strip()
            if after:
                # Match category synonyms
                for word, cat in CATEGORY_SYNONYMS.items():
                    if word in after:
                        new_cat = cat
                        if word in TAG_HINTS:
                            new_tag = TAG_HINTS[word]
                        return new_cat, new_tag, None
                # Otherwise treat as explicit POI name (e.g. "望京小腰")
                if 2 <= len(after) <= 12:
                    new_name = after
                    return None, None, new_name
            break
    return new_cat, new_tag, new_name


def _extract_minute_delta(text: str, default: int = 30) -> int:
    """Extract a minute delta from text like '推迟半小时' / '晚一小时'."""
    if "半小时" in text or "30分钟" in text or "三十分钟" in text:
        return 30
    if "一小时" in text or "1小时" in text or "60分钟" in text:
        return 60
    if "两小时" in text or "2小时" in text:
        return 120
    m = re.search(r"(\d+)\s*分钟", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*小时", text)
    if m:
        return int(m.group(1)) * 60
    return default


def resolve_target(
    action: ModificationAction,
    pending_tasks: List[Any],
    pending_route: List[Any],
) -> None:
    """Resolve target_hint into concrete target_ref (task_id) and target_poi_id.

    Mutates action in place. No-op for action_types that don't need a target
    (e.g. declare_dislike which only needs the hint preserved).
    """
    if not pending_route:
        return

    hint = action.target_hint
    if not hint:
        return

    idx: Optional[int] = None

    # 1. Direct index
    if "index" in hint:
        i = hint["index"]
        if isinstance(i, int):
            idx = i if i >= 0 else len(pending_route) + i

    # 2. POI name match
    if idx is None and "poi_name" in hint:
        for i, node in enumerate(pending_route):
            if getattr(node.poi, "name", "") == hint["poi_name"]:
                idx = i
                break

    # 3. Category + optional tag match
    if idx is None and "category" in hint:
        target_cat = hint["category"]
        target_tag = hint.get("tag")
        for i, node in enumerate(pending_route):
            poi = node.poi
            if getattr(poi, "category", "") != target_cat:
                continue
            if target_tag and target_tag not in getattr(poi, "tags", []):
                continue
            idx = i
            break

    # 4. Location match (substring in poi address)
    if idx is None and "location" in hint:
        loc = hint["location"]
        for i, node in enumerate(pending_route):
            addr = getattr(node.poi, "address", "")
            if loc in addr:
                idx = i
                break

    if idx is None or not (0 <= idx < len(pending_route)):
        return

    target_poi_id = pending_route[idx].poi.id
    action.target_poi_id = target_poi_id

    # Reverse lookup: find task that references this poi_id
    for task in pending_tasks:
        params = getattr(task, "params", {}) or {}
        if (params.get("poi_id") == target_poi_id
                or params.get("poi_name") == pending_route[idx].poi.name):
            action.target_ref = task.task_id
            break
