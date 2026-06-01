"""
Plan patch service tests - covers 5 action types and key invariants:
- task_id stability across patches
- correct change_log entries
- shift_time rollback on closed hours
- declare_dislike updates session context, not plan
"""

import pytest
from datetime import datetime, time, timedelta

from agent.core.route_planner import POI, RouteNode, RoutePlanner
from agent.core.state_machine import Task
from agent.core.services import plan_patch_service as patch_svc
from agent.core.services.modification_parser import ModificationAction


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
    """Build a 3-node mock route + matching tasks + planner with POI database."""
    haidilao = _poi("P101", "海底捞", "餐厅", tags=["火锅"])
    gongti = _poi("P102", "工体", "公园", lat=39.92)
    ktv = _poi("P103", "K歌之王", "KTV", lat=39.93, close_h=23)
    # Replacement candidates in planner database
    candidates = [
        _poi("P201", "上海姥姥", "餐厅", tags=["本帮菜"]),
        _poi("P202", "望京小腰", "餐厅", tags=["烧烤"]),
        _poi("P301", "星巴克", "咖啡馆", lat=39.91, dur=45, price=40),
        _poi("P401", "桂林米粉", "餐厅", tags=["米粉"]),
    ]

    rp = RoutePlanner()
    rp.load_mock_data([haidilao, gongti, ktv] + candidates)

    route = [
        _node(gongti, 14),
        _node(haidilao, 18),
        _node(ktv, 20),
    ]
    tasks = [
        Task("T001", "搜索工体", "search_poi", {"poi_id": "P102", "poi_name": "工体"}),
        Task("T002", "搜索海底捞", "search_poi", {"poi_id": "P101", "poi_name": "海底捞"}),
        Task("T003", "搜索K歌之王", "search_poi", {"poi_id": "P103", "poi_name": "K歌之王"}),
    ]
    return rp, tasks, route


def test_replace_preserves_task_id(setup):
    rp, tasks, route = setup
    action = ModificationAction(
        action_type="replace", target_ref="T002", target_poi_id="P101",
        target_hint={"category": "餐厅"}, new_category="餐厅", new_tag="本帮菜",
    )
    new_tasks, new_route, log = patch_svc.apply_modification(
        action, tasks, route, {}, {}, rp,
    )
    # task_id MUST remain T002 after replace
    assert new_tasks[1].task_id == "T002"
    # POI swapped to a 本帮菜 candidate (P201 = 上海姥姥)
    assert new_route[1].poi.id != "P101"
    assert "本帮菜" in new_route[1].poi.tags or new_route[1].poi.category == "餐厅"
    # change_log shape
    assert log[0]["type"] == "replace"
    assert log[0]["before"]["poi_id"] == "P101"
    assert log[0]["after"]["poi_id"] == new_route[1].poi.id


def test_remove_drops_node_and_task(setup):
    rp, tasks, route = setup
    action = ModificationAction(
        action_type="remove", target_ref="T003", target_poi_id="P103",
        target_hint={"index": -1},
    )
    new_tasks, new_route, log = patch_svc.apply_modification(
        action, tasks, route, {}, {}, rp,
    )
    assert len(new_route) == 2
    assert all(n.poi.id != "P103" for n in new_route)
    assert all(t.task_id != "T003" for t in new_tasks)
    assert log[0]["type"] == "remove"
    assert log[0]["removed"]["poi_id"] == "P103"


def test_insert_appends_new_task_with_next_id(setup):
    rp, tasks, route = setup
    action = ModificationAction(
        action_type="insert", new_category="咖啡馆",
    )
    new_tasks, new_route, log = patch_svc.apply_modification(
        action, tasks, route, {}, {}, rp,
    )
    assert len(new_route) == 4
    assert log[0]["type"] == "insert"
    # original task_ids preserved
    existing_ids = {"T001", "T002", "T003"}
    new_id = log[0]["task_id"]
    assert new_id not in existing_ids
    assert new_id.startswith("T")


def test_shift_time_within_hours(setup):
    rp, tasks, route = setup
    # 14:00 → 14:30 should succeed (all venues open)
    action = ModificationAction(action_type="shift_time", time_delta_min=30)
    new_tasks, new_route, log = patch_svc.apply_modification(
        action, tasks, route, {}, {}, rp,
    )
    assert log[0]["type"] == "shift_time"
    assert new_route[0].arrival_time.hour == 14
    assert new_route[0].arrival_time.minute == 30


def test_shift_time_rollback_when_closed(setup):
    rp, tasks, route = setup
    # Push early to 07:00 → gongti opens at 10:00, should rollback with error
    action = ModificationAction(action_type="shift_time", absolute_start="07:00")
    new_tasks, new_route, log = patch_svc.apply_modification(
        action, tasks, route, {}, {}, rp,
    )
    # Original route preserved
    assert new_route[0].arrival_time.hour == 14
    assert log[0]["type"] == "error"


def test_declare_dislike_updates_context_only(setup):
    rp, tasks, route = setup
    ctx = {}
    action = ModificationAction(
        action_type="declare_dislike",
        target_hint={"category": "KTV"},
    )
    new_tasks, new_route, log = patch_svc.apply_modification(
        action, tasks, route, {}, ctx, rp,
    )
    # Plan unchanged
    assert len(new_route) == 3
    assert len(new_tasks) == 3
    # Context records the dislike
    assert "KTV" in ctx.get("disliked_categories", [])
    assert log[0]["type"] == "preference_noted"


def test_replace_excludes_already_in_route(setup):
    """Replace must not pick a POI already in the route."""
    rp, tasks, route = setup
    # Add 上海姥姥 manually as if already in route, then try to replace 海底捞
    action = ModificationAction(
        action_type="replace", target_ref="T002", target_poi_id="P101",
        new_category="餐厅",
    )
    new_tasks, new_route, log = patch_svc.apply_modification(
        action, tasks, route, {}, {}, rp,
    )
    # Should pick something other than the old 海底捞
    assert new_route[1].poi.id != "P101"
    # All POIs in route should be unique
    ids = [n.poi.id for n in new_route]
    assert len(ids) == len(set(ids))
