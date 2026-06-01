"""
Plan patch service - applies a ModificationAction to existing pending_tasks
and pending_route in place, without re-running the full planner.

This is the core of "real multi-turn dialogue": user says "change restaurant
to hotpot" → we patch the existing plan rather than regenerate from scratch.

Stable task_ids are preserved across patches so the frontend diff can use
task_id as a stable key.
"""

import copy
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..route_planner import POI, RouteNode, RouteConstraints
from ..state_machine import Task
from .modification_parser import ModificationAction

logger = logging.getLogger(__name__)


# ===== Structured error change_log =====
# reason_code is the machine-readable handle; message is user-facing; suggestions
# are clickable chips the frontend prefills back into the input box.

REASON_NO_CANDIDATE = "no_candidate"
REASON_BUSY_HOURS = "busy_hours"
REASON_OVER_BUDGET = "over_budget"
REASON_LOCATION_MISMATCH = "location_mismatch"
REASON_UNKNOWN = "unknown"


def _err(
    reason_code: str,
    message: str,
    suggestions: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Build a structured error entry for change_log."""
    return {
        "type": "error",
        "reason_code": reason_code,
        "message": message,
        "suggestions": suggestions or [],
    }


def _suggest_for_no_candidate(action: ModificationAction, route: List[RouteNode]) -> List[Dict[str, str]]:
    """Suggestions when the candidate pool is empty for the requested cat/tag."""
    requested = action.new_category or action.new_tag or "替代"
    alternates = {
        "火锅": "本帮菜", "本帮菜": "火锅", "日料": "西餐", "西餐": "日料",
        "烧烤": "火锅", "咖啡馆": "甜品店", "甜品店": "咖啡馆",
    }
    fallback_cat = alternates.get(requested, "餐厅")
    suggestions = [
        {"label": f"换成 {fallback_cat}", "hint": f"换成{fallback_cat}"},
        {"label": "放宽预算", "hint": "把预算调高 200"},
    ]
    if action.action_type == "insert":
        suggestions.append({"label": "算了不加了", "hint": "不用加新的"})
    else:
        suggestions.append({"label": "去掉这站", "hint": "不要这站了"})
    return suggestions


def _suggest_for_busy_hours(invalid_node: RouteNode) -> List[Dict[str, str]]:
    """Suggestions when the new start time pushes a stop past its open hours."""
    open_hh = invalid_node.poi.open_time.hour
    open_mm = invalid_node.poi.open_time.minute
    return [
        {"label": f"改到 {open_hh:02d}:{open_mm:02d} 开始", "hint": f"改成 {open_hh:02d}:{open_mm:02d} 开始"},
        {"label": f"换掉 {invalid_node.poi.name}", "hint": f"把{invalid_node.poi.name}换一家"},
        {"label": "保持原时间", "hint": "算了别动时间"},
    ]


def _suggest_for_over_budget(over_amount: int) -> List[Dict[str, str]]:
    return [
        {"label": f"放宽预算 ¥{max(over_amount, 100)}", "hint": f"预算加 {max(over_amount, 100)}"},
        {"label": "换个便宜的", "hint": "换个便宜点的"},
        {"label": "算了不加了", "hint": "算了不用加"},
    ]


def _suggest_for_location_mismatch(route: List[RouteNode]) -> List[Dict[str, str]]:
    """Suggestions when the target can't be resolved from the user's hint."""
    suggestions: List[Dict[str, str]] = []
    if route:
        first_name = route[0].poi.name
        suggestions.append({"label": f"用 第一个 指定", "hint": f"第一个换一家"})
        if len(route) >= 2:
            suggestions.append({"label": f"用 最后一个 指定", "hint": "最后一个换一家"})
        suggestions.append({"label": f"用名字指定", "hint": f"换掉 {first_name}"})
    return suggestions


def apply_modification(
    action: ModificationAction,
    pending_tasks: List[Task],
    pending_route: List[RouteNode],
    intent: Dict[str, Any],
    session_context: Dict[str, Any],
    route_planner,
) -> Tuple[List[Task], List[RouteNode], List[Dict[str, Any]]]:
    """Apply the action and return (new_tasks, new_route, change_log).

    All inputs are read-only conceptually; new lists are returned. Caller
    must persist these back to session.context.

    change_log is a list of dicts the frontend can render as diff highlights.
    """
    handlers = {
        "replace": _apply_replace,
        "remove": _apply_remove,
        "insert": _apply_insert,
        "shift_time": _apply_shift_time,
        "declare_dislike": _apply_declare_dislike,
    }
    handler = handlers.get(action.action_type)
    if not handler:
        logger.warning(f"Unknown action_type: {action.action_type}")
        return pending_tasks, pending_route, []

    new_tasks = [_clone_task(t) for t in pending_tasks]
    new_route = [_clone_node(n) for n in pending_route]
    return handler(action, new_tasks, new_route, intent, session_context, route_planner)


def _apply_replace(action, tasks, route, intent, ctx, route_planner):
    """Replace one POI with a candidate matching new_category/new_tag/new_poi_name."""
    idx = _resolve_route_index(action, route)
    if idx is None:
        return tasks, route, [_err(
            REASON_LOCATION_MISMATCH,
            "找不到要替换的位置，请说得更具体一点",
            _suggest_for_location_mismatch(route),
        )]

    old_node = route[idx]
    old_poi = old_node.poi

    new_poi = _pick_replacement(action, old_poi, route, ctx, route_planner)
    if new_poi is None:
        requested = action.new_category or action.new_tag or "替代"
        return tasks, route, [_err(
            REASON_NO_CANDIDATE,
            f"找不到合适的{requested}",
            _suggest_for_no_candidate(action, route),
        )]

    new_node = _build_node_with_poi(new_poi, old_node, route_planner)
    route[idx] = new_node
    _recalculate_route_times(route, route_planner)

    updated_tasks = _update_tasks_for_poi_swap(tasks, old_poi, new_poi)

    change_log = [{
        "type": "replace",
        "task_id": action.target_ref or "",
        "before": {"poi_id": old_poi.id, "name": old_poi.name, "category": old_poi.category},
        "after": {"poi_id": new_poi.id, "name": new_poi.name, "category": new_poi.category},
    }]
    return updated_tasks, route, change_log


def _apply_remove(action, tasks, route, intent, ctx, route_planner):
    """Remove a POI and the task chain that depends on it."""
    idx = _resolve_route_index(action, route)
    if idx is None:
        return tasks, route, [_err(
            REASON_LOCATION_MISMATCH,
            "找不到要删除的项",
            _suggest_for_location_mismatch(route),
        )]

    removed_poi = route[idx].poi
    route.pop(idx)
    _recalculate_route_times(route, route_planner)

    removed_task_ids = {
        t.task_id for t in tasks
        if _task_targets_poi(t, removed_poi)
    }
    if action.target_ref:
        removed_task_ids.add(action.target_ref)

    kept_tasks = []
    for t in tasks:
        if t.task_id in removed_task_ids:
            continue
        # Unlink dependencies on removed tasks (don't cascade-delete downstream)
        t.dependencies = [d for d in (t.dependencies or []) if d not in removed_task_ids]
        kept_tasks.append(t)

    change_log = [{
        "type": "remove",
        "task_ids": sorted(removed_task_ids),
        "removed": {"poi_id": removed_poi.id, "name": removed_poi.name},
    }]
    return kept_tasks, route, change_log


def _apply_insert(action, tasks, route, intent, ctx, route_planner):
    """Insert a new POI at the best position."""
    new_poi = _pick_replacement(action, None, route, ctx, route_planner)
    if new_poi is None:
        return tasks, route, [_err(
            REASON_NO_CANDIDATE,
            f"找不到合适的{action.new_category or '新增项'}",
            _suggest_for_no_candidate(action, route),
        )]

    # Budget gate: refuse if inserting blows past max_budget * 1.2
    over = _check_budget_overflow(new_poi, route, ctx)
    if over > 0:
        return tasks, route, [_err(
            REASON_OVER_BUDGET,
            f"加上「{new_poi.name}」会超预算 ¥{over}",
            _suggest_for_over_budget(over),
        )]

    position_hint = action.target_hint.get("position")
    insert_idx = _choose_insert_position(new_poi, route, position_hint, route_planner)

    # Build the node
    if insert_idx == 0:
        prev = None
    else:
        prev = route[insert_idx - 1]

    travel_time = 0
    travel_distance = 0.0
    if prev is not None:
        travel_time = route_planner.calculate_travel_time(prev.poi, new_poi)
        travel_distance = route_planner.calculate_distance(prev.poi, new_poi)
        arrival = prev.departure_time + timedelta(minutes=travel_time)
    elif route:
        arrival = route[0].arrival_time
    else:
        arrival = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0)

    new_node = RouteNode(
        poi=new_poi,
        arrival_time=arrival,
        departure_time=arrival + timedelta(minutes=new_poi.avg_duration),
        travel_time_from_prev=travel_time,
        travel_distance_from_prev=travel_distance,
        estimated_queue_time=route_planner.estimate_queue_time(new_poi, arrival),
        activity_type=_infer_activity_type(new_poi.category),
    )
    route.insert(insert_idx, new_node)
    _recalculate_route_times(route, route_planner)

    new_task = _build_search_task(new_poi, tasks)
    tasks.append(new_task)

    change_log = [{
        "type": "insert",
        "task_id": new_task.task_id,
        "inserted": {"poi_id": new_poi.id, "name": new_poi.name, "category": new_poi.category},
        "position": insert_idx,
    }]
    return tasks, route, change_log


def _apply_shift_time(action, tasks, route, intent, ctx, route_planner):
    """Shift all nodes' times by delta or to an absolute start."""
    if not route:
        return tasks, route, [_err(REASON_UNKNOWN, "还没有规划路线", [])]

    new_start = _compute_new_start(action, route[0].arrival_time)
    if new_start is None:
        return tasks, route, [_err(
            REASON_UNKNOWN,
            "时间表达没看懂，能换种说法吗",
            [
                {"label": "改成 18:00", "hint": "改成 18:00 开始"},
                {"label": "晚一小时", "hint": "晚一小时开始"},
            ],
        )]

    backup = [_clone_node(n) for n in route]
    _shift_route_times(route, new_start, route_planner)

    invalid_node = _find_unopen_node(route, route_planner)
    if invalid_node is not None:
        # Roll back
        for i, original in enumerate(backup):
            route[i] = original
        return tasks, route, [_err(
            REASON_BUSY_HOURS,
            f"这个时间 {invalid_node.poi.name} 还没开门",
            _suggest_for_busy_hours(invalid_node),
        )]

    change_log = [{
        "type": "shift_time",
        "new_start": new_start.strftime("%H:%M"),
        "affected_task_ids": [t.task_id for t in tasks if getattr(t, "tool_name", "") == "weather_api"],
    }]
    return tasks, route, change_log


def _apply_declare_dislike(action, tasks, route, intent, ctx, route_planner):
    """Record a negative preference in session context. Does not change plan."""
    hint = action.target_hint or {}
    disliked_poi_ids = ctx.setdefault("disliked_poi_ids", [])
    disliked_categories = ctx.setdefault("disliked_categories", [])

    noted = {}
    if action.target_poi_id and action.target_poi_id not in disliked_poi_ids:
        disliked_poi_ids.append(action.target_poi_id)
        noted["poi_id"] = action.target_poi_id

    location = hint.get("location")
    if location:
        # Mark every POI in current route that lives at this location
        for node in route:
            addr = getattr(node.poi, "address", "") or ""
            if location in addr and node.poi.id not in disliked_poi_ids:
                disliked_poi_ids.append(node.poi.id)
        noted["location"] = location

    category = hint.get("category")
    if category and category not in disliked_categories:
        disliked_categories.append(category)
        noted["category"] = category

    tag = hint.get("tag")
    if tag:
        noted["tag"] = tag

    return tasks, route, [{
        "type": "preference_noted",
        "noted": noted,
    }]


def _resolve_route_index(action: ModificationAction, route: List[RouteNode]) -> Optional[int]:
    """Find the route index that the action refers to. Try target_poi_id, then hint."""
    if action.target_poi_id:
        for i, node in enumerate(route):
            if node.poi.id == action.target_poi_id:
                return i

    hint = action.target_hint or {}
    if "index" in hint:
        i = hint["index"]
        if isinstance(i, int):
            idx = i if i >= 0 else len(route) + i
            if 0 <= idx < len(route):
                return idx
    if "poi_name" in hint:
        for i, node in enumerate(route):
            if node.poi.name == hint["poi_name"]:
                return i
    if "category" in hint:
        target_tag = hint.get("tag")
        for i, node in enumerate(route):
            if node.poi.category != hint["category"]:
                continue
            if target_tag and target_tag not in (node.poi.tags or []):
                continue
            return i
    if "location" in hint:
        loc = hint["location"]
        for i, node in enumerate(route):
            if loc in (node.poi.address or ""):
                return i
    return None


def _pick_replacement(
    action: ModificationAction,
    old_poi: Optional[POI],
    current_route: List[RouteNode],
    ctx: Dict[str, Any],
    route_planner,
) -> Optional[POI]:
    """Pick the best POI to use as replacement or insertion."""
    db = route_planner.poi_database
    if not db:
        return None

    excluded_ids = set(ctx.get("disliked_poi_ids", []) or [])
    excluded_ids.update(n.poi.id for n in current_route)
    if old_poi is not None:
        excluded_ids.add(old_poi.id)

    if action.new_poi_name:
        for poi in db.values():
            if action.new_poi_name in poi.name and poi.id not in excluded_ids:
                return poi

    target_category = action.new_category or (old_poi.category if old_poi else None)
    target_tag = action.new_tag

    candidates: List[POI] = []
    for poi in db.values():
        if poi.id in excluded_ids:
            continue
        if target_category and poi.category != target_category:
            continue
        if target_tag and target_tag not in (poi.tags or []):
            continue
        candidates.append(poi)

    if not candidates:
        return None

    constraints = _build_lightweight_constraints(ctx, current_route)
    candidates.sort(
        key=lambda p: route_planner.score_poi(p, constraints, emotion=None, seed=0),
        reverse=True,
    )
    return candidates[0]


def _build_lightweight_constraints(ctx, route) -> RouteConstraints:
    """Build minimal constraints for score_poi during a patch."""
    return RouteConstraints(
        start_time=route[0].arrival_time if route else datetime.now(),
        max_duration=ctx.get("max_duration", 480),
        max_budget=ctx.get("max_budget", 1000),
        group_size=ctx.get("group_size", 2),
    )


def _build_node_with_poi(new_poi: POI, old_node: RouteNode, route_planner) -> RouteNode:
    """Build a RouteNode for new_poi using old_node's arrival as anchor."""
    return RouteNode(
        poi=new_poi,
        arrival_time=old_node.arrival_time,
        departure_time=old_node.arrival_time + timedelta(minutes=new_poi.avg_duration),
        travel_time_from_prev=old_node.travel_time_from_prev,
        travel_distance_from_prev=old_node.travel_distance_from_prev,
        estimated_queue_time=route_planner.estimate_queue_time(new_poi, old_node.arrival_time),
        activity_type=_infer_activity_type(new_poi.category),
    )


def _recalculate_route_times(route: List[RouteNode], route_planner) -> None:
    """Recompute arrival/departure for all nodes given the first node's arrival."""
    if not route:
        return
    start = route[0].arrival_time
    if hasattr(route_planner, "_recalculate_times"):
        route_planner._recalculate_times(route, start)


def _update_tasks_for_poi_swap(tasks: List[Task], old_poi: POI, new_poi: POI) -> List[Task]:
    """Rewrite any task params that reference the old POI to the new one."""
    for task in tasks:
        params = task.params or {}
        was_for_old = False
        if params.get("poi_id") == old_poi.id:
            params["poi_id"] = new_poi.id
            was_for_old = True
        if params.get("poi_name") == old_poi.name:
            params["poi_name"] = new_poi.name
            was_for_old = True
        if params.get("category") == old_poi.category and new_poi.category != old_poi.category:
            params["category"] = new_poi.category
        # Also patch tool-specific id fields
        for key in ("restaurant_id", "venue_id", "store_id"):
            if params.get(key) == old_poi.id:
                params[key] = new_poi.id
                was_for_old = True
        # Refresh Meituan capability surface (团购券/闪送/会员折扣 etc.)
        if was_for_old:
            new_caps = list(getattr(new_poi, "capability_tags", []) or [])
            if new_caps:
                params["capability_tags"] = new_caps
            else:
                params.pop("capability_tags", None)
            new_label = getattr(new_poi, "deal_label", None)
            if new_label:
                params["deal_label"] = new_label
            else:
                params.pop("deal_label", None)
    return tasks


def _choose_insert_position(new_poi, route, position_hint, route_planner) -> int:
    """Pick where to insert: explicit hint > min travel-time increment."""
    if not route:
        return 0
    if position_hint == "middle":
        return len(route) // 2
    if isinstance(position_hint, int):
        if position_hint < 0:
            return max(0, len(route) + position_hint + 1)
        return min(position_hint, len(route))

    # Min travel-time delta: try every gap, pick the smallest extra time
    best_pos = len(route)
    best_extra = float("inf")
    for i in range(len(route) + 1):
        prev = route[i - 1].poi if i > 0 else None
        nxt = route[i].poi if i < len(route) else None
        original = route_planner.calculate_travel_time(prev, nxt) if prev and nxt else 0
        added = 0
        if prev:
            added += route_planner.calculate_travel_time(prev, new_poi)
        if nxt:
            added += route_planner.calculate_travel_time(new_poi, nxt)
        extra = added - original
        if extra < best_extra:
            best_extra = extra
            best_pos = i
    return best_pos


def _build_search_task(new_poi: POI, existing_tasks: List[Task]) -> Task:
    """Construct a search_poi task for a newly inserted POI."""
    max_id = 0
    for t in existing_tasks:
        try:
            n = int(t.task_id.lstrip("T"))
        except (ValueError, AttributeError):
            continue
        max_id = max(max_id, n)
    new_id = f"T{max_id + 1:03d}"
    params = {
        "category": new_poi.category,
        "keywords": (new_poi.tags or [])[:3],
        "rating_min": 4.0,
        "poi_name": new_poi.name,
        "poi_id": new_poi.id,
    }
    caps = list(getattr(new_poi, "capability_tags", []) or [])
    if caps:
        params["capability_tags"] = caps
    label = getattr(new_poi, "deal_label", None)
    if label:
        params["deal_label"] = label
    return Task(
        task_id=new_id,
        name=f"搜索{new_poi.name}",
        tool_name="search_poi",
        params=params,
        priority=8,
    )


def _compute_new_start(action: ModificationAction, current_start: datetime) -> Optional[datetime]:
    if action.absolute_start:
        try:
            hh, mm = action.absolute_start.split(":")
            return current_start.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
        except (ValueError, AttributeError):
            return None
    if action.time_delta_min is not None:
        return current_start + timedelta(minutes=action.time_delta_min)
    return None


def _shift_route_times(route: List[RouteNode], new_start: datetime, route_planner) -> None:
    """Shift the first node to new_start, then recompute the rest."""
    route[0].arrival_time = new_start
    if hasattr(route_planner, "_recalculate_times"):
        route_planner._recalculate_times(route, new_start)


def _find_unopen_node(route: List[RouteNode], route_planner) -> Optional[RouteNode]:
    for node in route:
        check_start = node.arrival_time + timedelta(minutes=node.estimated_queue_time or 0)
        if not route_planner.check_open(node.poi, check_start, node.poi.avg_duration):
            return node
    return None


def _suggest_alternate_time(node: RouteNode) -> str:
    """Suggest a time that would let this node fit its business hours.
    Kept for legacy callers; new error paths use _suggest_for_busy_hours."""
    open_hh = node.poi.open_time.hour
    open_mm = node.poi.open_time.minute
    return f"{node.poi.name} 营业时间从 {open_hh:02d}:{open_mm:02d} 开始，要不试试这个时间？"


def _check_budget_overflow(new_poi: POI, route: List[RouteNode], ctx: Dict[str, Any]) -> int:
    """Return the overflow in yuan (>0 means over budget), or 0 if within.
    Uses ctx['max_budget'] * 1.2 as the hard ceiling — same threshold the warning
    path elsewhere uses for total_duration."""
    max_budget = ctx.get("max_budget", 0)
    if not max_budget or max_budget <= 0:
        return 0
    group_size = ctx.get("group_size", 1) or 1
    current = sum((n.poi.price_per_person or 0) for n in route) * group_size
    addition = (new_poi.price_per_person or 0) * group_size
    ceiling = int(max_budget * 1.2)
    over = int(current + addition - ceiling)
    return over if over > 0 else 0


def _task_targets_poi(task: Task, poi: POI) -> bool:
    params = task.params or {}
    return (
        params.get("poi_id") == poi.id
        or params.get("poi_name") == poi.name
        or params.get("restaurant_id") == poi.id
        or params.get("venue_id") == poi.id
    )


_PLAY_CATEGORIES = {
    "儿童乐园", "密室逃脱", "KTV", "剧本杀", "电影院", "轰趴馆", "户外拓展",
    "桌游", "电竞馆", "射箭", "保龄球", "陶艺", "猫咖", "VR体验", "台球",
    "水族馆", "动物园", "健身房", "博物馆", "公园", "书店", "商圈",
}


def _infer_activity_type(category: str) -> str:
    if category == "酒店":
        return "rest"
    if category in _PLAY_CATEGORIES:
        return "play"
    return "dine"


def _clone_task(t: Task) -> Task:
    cloned = Task(
        task_id=t.task_id,
        name=t.name,
        tool_name=t.tool_name,
        params=copy.deepcopy(t.params or {}),
        priority=getattr(t, "priority", 0),
        dependencies=list(t.dependencies or []),
        fallback_tool=getattr(t, "fallback_tool", None),
        fallback_params=copy.deepcopy(getattr(t, "fallback_params", None)),
    )
    cloned.status = t.status
    cloned.result = copy.deepcopy(t.result) if t.result else None
    return cloned


def _clone_node(n: RouteNode) -> RouteNode:
    return RouteNode(
        poi=n.poi,
        arrival_time=n.arrival_time,
        departure_time=n.departure_time,
        travel_time_from_prev=n.travel_time_from_prev,
        travel_distance_from_prev=n.travel_distance_from_prev,
        estimated_queue_time=n.estimated_queue_time,
        activity_type=n.activity_type,
    )
