"""
Plan-patch error path tests — guard the structured error contract.

Every error entry MUST have:
- type: "error"
- reason_code: one of {no_candidate, busy_hours, over_budget, location_mismatch, unknown}
- message: a human-facing string
- suggestions: a list of {label, hint} dicts (may be empty for unknown)

Tests cover all 4 user-actionable reason_codes plus the contract shape itself.
"""

import pytest
from datetime import datetime, time, timedelta

from agent.core.route_planner import POI, RouteNode, RoutePlanner
from agent.core.state_machine import Task
from agent.core.services import plan_patch_service as patch_svc
from agent.core.services.modification_parser import ModificationAction


# ===== fixtures =====

def _poi(pid, name, cat, *, lat=39.9, lng=116.4, tags=None, dur=60, price=80,
         open_h=10, close_h=22):
    return POI(
        id=pid, name=name, category=cat, rating=4.5, review_count=100,
        location={"lat": lat, "lng": lng}, address=f"{name} 地址",
        open_time=time(open_h), close_time=time(close_h),
        avg_duration=dur, price_per_person=price,
        tags=tags or [], peak_hours=[],
        queue_factor=1.0, capacity=50,
    )


def _node(poi, hour, minute=0):
    arr = datetime(2026, 1, 1, hour, minute)
    dep = arr + timedelta(minutes=poi.avg_duration)
    return RouteNode(
        poi=poi, arrival_time=arr, departure_time=dep,
        travel_time_from_prev=0, travel_distance_from_prev=0,
        estimated_queue_time=0, activity_type="play",
    )


@pytest.fixture
def setup():
    """3-node route + planner with only 餐厅/咖啡馆 candidates (no KTV alternatives)."""
    haidilao = _poi("P101", "海底捞", "餐厅", tags=["火锅"], price=200)
    gongti = _poi("P102", "工体", "公园", lat=39.92, price=0)
    ktv = _poi("P103", "K歌之王", "KTV", lat=39.93, close_h=23, price=300)
    # No KTV / no 日料 candidates → no_candidate reachable
    candidates = [
        _poi("P201", "上海姥姥", "餐厅", tags=["本帮菜"]),
        _poi("P301", "星巴克", "咖啡馆", lat=39.91, dur=45, price=40),
        _poi("P302", "贵价餐厅", "餐厅", tags=["西餐"], price=2000),  # for over_budget test
    ]
    rp = RoutePlanner()
    rp.load_mock_data([haidilao, gongti, ktv] + candidates)
    route = [_node(gongti, 14), _node(haidilao, 18), _node(ktv, 20)]
    tasks = [
        Task("T001", "搜索工体", "search_poi", {"poi_id": "P102"}),
        Task("T002", "搜索海底捞", "search_poi", {"poi_id": "P101"}),
        Task("T003", "搜索K歌之王", "search_poi", {"poi_id": "P103"}),
    ]
    return rp, tasks, route


def _is_error(entry, reason_code):
    """Shape assertion: entry conforms to the structured-error contract."""
    return (
        entry.get("type") == "error"
        and entry.get("reason_code") == reason_code
        and isinstance(entry.get("message"), str) and entry["message"]
        and isinstance(entry.get("suggestions"), list)
    )


# ===== no_candidate =====

def test_replace_no_candidate_for_unknown_tag(setup):
    """Request 日料 when the planner DB has none → no_candidate."""
    rp, tasks, route = setup
    action = ModificationAction(
        action_type="replace", target_ref="T002", target_poi_id="P101",
        new_category="餐厅", new_tag="日料",
    )
    _, _, log = patch_svc.apply_modification(action, tasks, route, {}, {}, rp)
    assert len(log) == 1
    assert _is_error(log[0], patch_svc.REASON_NO_CANDIDATE)
    assert len(log[0]["suggestions"]) >= 2
    for s in log[0]["suggestions"]:
        assert "label" in s and "hint" in s


def test_insert_no_candidate_for_unknown_category(setup):
    """Request to insert a 桌游 — planner has none → no_candidate."""
    rp, tasks, route = setup
    action = ModificationAction(action_type="insert", new_category="桌游")
    _, _, log = patch_svc.apply_modification(action, tasks, route, {}, {}, rp)
    assert _is_error(log[0], patch_svc.REASON_NO_CANDIDATE)
    assert len(log[0]["suggestions"]) >= 1


# ===== busy_hours =====

def test_shift_time_before_open_hours_returns_busy_hours(setup):
    """Shift everything to 06:00 → public 10:00 open → busy_hours, rolled back."""
    rp, tasks, route = setup
    original_first_arrival = route[0].arrival_time
    action = ModificationAction(action_type="shift_time", absolute_start="06:00")
    _, new_route, log = patch_svc.apply_modification(action, tasks, route, {}, {}, rp)
    assert _is_error(log[0], patch_svc.REASON_BUSY_HOURS)
    # Rollback: route times unchanged
    assert new_route[0].arrival_time == original_first_arrival
    # Suggestions must include an actionable HH:MM-style hint
    assert any(":" in s["hint"] for s in log[0]["suggestions"])


# ===== over_budget =====

def test_insert_blows_past_budget_ceiling(setup):
    """Insert 2000元 西餐 with budget=200 → over_budget."""
    rp, tasks, route = setup
    ctx = {"max_budget": 200, "group_size": 1}
    action = ModificationAction(action_type="insert", new_category="餐厅", new_tag="西餐")
    _, _, log = patch_svc.apply_modification(action, tasks, route, {}, ctx, rp)
    assert _is_error(log[0], patch_svc.REASON_OVER_BUDGET)
    # Suggestions must include both "loosen budget" and "cheaper alternative"
    labels = [s["label"] for s in log[0]["suggestions"]]
    assert any("预算" in lab for lab in labels)
    assert any("便宜" in lab for lab in labels)


def test_insert_within_budget_does_not_trip_over_budget(setup):
    """Plenty of room → no over_budget error."""
    rp, tasks, route = setup
    ctx = {"max_budget": 10000, "group_size": 1}
    action = ModificationAction(action_type="insert", new_category="咖啡馆")
    _, _, log = patch_svc.apply_modification(action, tasks, route, {}, ctx, rp)
    # Insert succeeded — change_log entry is type:'insert', not 'error'
    assert log[0]["type"] == "insert"


def test_insert_with_no_budget_set_does_not_check(setup):
    """ctx has no max_budget → over_budget gate is skipped entirely."""
    rp, tasks, route = setup
    action = ModificationAction(action_type="insert", new_category="餐厅", new_tag="西餐")
    _, _, log = patch_svc.apply_modification(action, tasks, route, {}, {}, rp)
    assert log[0]["type"] == "insert"


# ===== location_mismatch =====

def test_replace_location_mismatch_when_hint_unresolvable(setup):
    """No target_ref / target_poi_id, target_hint can't resolve → location_mismatch."""
    rp, tasks, route = setup
    action = ModificationAction(
        action_type="replace",
        target_hint={"poi_name": "不存在的店"},
        new_category="餐厅",
    )
    _, _, log = patch_svc.apply_modification(action, tasks, route, {}, {}, rp)
    assert _is_error(log[0], patch_svc.REASON_LOCATION_MISMATCH)
    # Must offer at least one concrete suggestion
    assert len(log[0]["suggestions"]) >= 1
    assert any("第一个" in s["label"] or "第一个" in s["hint"]
               for s in log[0]["suggestions"])


def test_remove_location_mismatch_when_hint_unresolvable(setup):
    rp, tasks, route = setup
    action = ModificationAction(
        action_type="remove",
        target_hint={"poi_name": "不存在的店"},
    )
    _, _, log = patch_svc.apply_modification(action, tasks, route, {}, {}, rp)
    assert _is_error(log[0], patch_svc.REASON_LOCATION_MISMATCH)


# ===== unknown =====

def test_shift_time_with_no_time_returns_unknown(setup):
    """No absolute_start, no time_delta_min → unknown."""
    rp, tasks, route = setup
    action = ModificationAction(action_type="shift_time")
    _, _, log = patch_svc.apply_modification(action, tasks, route, {}, {}, rp)
    assert _is_error(log[0], patch_svc.REASON_UNKNOWN)


def test_shift_time_on_empty_route_returns_unknown():
    """No route at all → unknown."""
    rp = RoutePlanner()
    rp.load_mock_data([])
    action = ModificationAction(action_type="shift_time", time_delta_min=30)
    _, _, log = patch_svc.apply_modification(action, [], [], {}, {}, rp)
    assert _is_error(log[0], patch_svc.REASON_UNKNOWN)


# ===== shape contract =====

def test_every_error_entry_has_required_fields(setup):
    """Sweep all the error-producing paths and check the shape contract."""
    rp, tasks, route = setup
    cases = [
        ModificationAction(action_type="replace", target_poi_id="P101",
                           new_category="餐厅", new_tag="日料"),  # no_candidate
        ModificationAction(action_type="replace",
                           target_hint={"poi_name": "不存在的店"}),  # location_mismatch
        ModificationAction(action_type="remove",
                           target_hint={"poi_name": "不存在的店"}),  # location_mismatch
        ModificationAction(action_type="shift_time",
                           absolute_start="06:00"),  # busy_hours
        ModificationAction(action_type="shift_time"),  # unknown
    ]
    for action in cases:
        _, _, log = patch_svc.apply_modification(action, tasks, route, {}, {}, rp)
        entry = log[0]
        assert entry["type"] == "error"
        assert entry["reason_code"] in {
            patch_svc.REASON_NO_CANDIDATE,
            patch_svc.REASON_BUSY_HOURS,
            patch_svc.REASON_OVER_BUDGET,
            patch_svc.REASON_LOCATION_MISMATCH,
            patch_svc.REASON_UNKNOWN,
        }
        assert isinstance(entry["message"], str) and entry["message"]
        assert isinstance(entry["suggestions"], list)
        for s in entry["suggestions"]:
            assert isinstance(s, dict)
            assert "label" in s and "hint" in s
            assert isinstance(s["label"], str) and s["label"]
            assert isinstance(s["hint"], str) and s["hint"]
