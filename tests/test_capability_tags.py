"""
P5 capability_tags flow tests.

Guarantees the Meituan capability surface stays wired end-to-end:
- POI mock data populates capability_tags + deal_label
- Task plan service propagates them into task.params
- Patch service rewrites caps on replace + carries them on insert
- ResponseService aggregates and renders them in summary/share text
"""

from datetime import time, datetime, timedelta

import pytest

from agent.core.poi_data import (
    CAPABILITY_VOCAB,
    _derive_capabilities,
    load_all_pois,
)
from agent.core.route_planner import POI, RouteNode, RoutePlanner
from agent.core.services.modification_parser import ModificationAction
from agent.core.services import plan_patch_service as patch_svc
from agent.core.services.response_service import (
    aggregate_capabilities,
    format_capability_phrase,
)
from agent.core.state_machine import Task


# ===== _derive_capabilities (pure helper) =====

def _make_poi(category="餐厅", coupon=None, original=None):
    return POI(
        id="P001", name="测试", category=category, rating=4.5, review_count=100,
        location={"lat": 39.9, "lng": 116.4}, address="any",
        open_time=time(10), close_time=time(22),
        avg_duration=60, price_per_person=100, tags=[], peak_hours=[],
        queue_factor=1.0, capacity=50,
        coupon_price=coupon, original_price=original,
    )


def test_derive_caps_for_restaurant_with_coupon():
    poi = _make_poi("餐厅", coupon=99, original=120)
    caps, label = _derive_capabilities(poi)
    assert "团购券" in caps
    assert "积分" in caps
    assert "扫码点餐" in caps  # category-driven
    assert label == "团购券 ¥99（省 ¥21）"


def test_derive_caps_for_hotel_drops_scan():
    poi = _make_poi("酒店", coupon=238, original=280)
    caps, _ = _derive_capabilities(poi)
    assert "会员折扣" in caps
    assert "免预约" in caps
    assert "扫码点餐" not in caps


def test_derive_caps_no_coupon_skips_deal():
    poi = _make_poi("餐厅", coupon=None, original=None)
    caps, label = _derive_capabilities(poi)
    assert "团购券" not in caps
    assert label is None
    assert "扫码点餐" in caps  # category cap still applies


def test_derive_caps_coupon_equal_to_original_skips_团购券():
    """No real discount → no 团购券 tag."""
    poi = _make_poi("餐厅", coupon=100, original=100)
    caps, label = _derive_capabilities(poi)
    assert "团购券" not in caps
    assert label is None


def test_all_derived_tags_in_vocab():
    """Every tag we emit must be in the closed vocab."""
    for cat in ["餐厅", "酒店", "电影院", "KTV", "花店", "甜品店"]:
        caps, _ = _derive_capabilities(_make_poi(cat, coupon=50, original=70))
        for tag in caps:
            assert tag in CAPABILITY_VOCAB, f"{cat}: {tag} not in vocab"


# ===== load_all_pois enrichment =====

def test_mock_pois_have_capability_tags_after_load():
    pois = load_all_pois()
    # At least the coupon-bearing ones must have 团购券
    with_coupons = [p for p in pois if p.coupon_price and p.original_price
                    and p.coupon_price < p.original_price]
    assert with_coupons, "fixture sanity: expected coupon-bearing POIs"
    for p in with_coupons:
        assert "团购券" in p.capability_tags
        assert p.deal_label and "团购券" in p.deal_label


def test_mock_hotel_carries_member_discount():
    hotels = [p for p in load_all_pois() if p.category == "酒店"]
    assert hotels, "fixture sanity: expected hotel POIs"
    for h in hotels:
        assert "会员折扣" in h.capability_tags


# ===== aggregator + phrase =====

def _task(tid, caps=None):
    params = {}
    if caps is not None:
        params["capability_tags"] = caps
    return Task(tid, f"任务{tid}", "search_poi", params)


def test_aggregate_counts_per_task_dedup_within_task():
    tasks = [
        _task("T1", ["团购券", "团购券", "积分"]),  # dup ignored within one task
        _task("T2", ["团购券", "扫码点餐"]),
        _task("T3", ["闪送"]),
    ]
    counts = aggregate_capabilities(tasks)
    assert counts == {"团购券": 2, "积分": 1, "扫码点餐": 1, "闪送": 1}


def test_aggregate_ignores_non_list_and_non_string():
    tasks = [
        _task("T1", "not-a-list"),  # bad type → skipped
        _task("T2", [123, None, "团购券"]),  # non-strings filtered
        _task("T3", None),
    ]
    counts = aggregate_capabilities(tasks)
    assert counts == {"团购券": 1}


def test_format_phrase_handles_singular_and_plural():
    assert format_capability_phrase({}) == ""
    assert format_capability_phrase({"团购券": 1}) == "用到了 团购券"
    assert format_capability_phrase({"团购券": 2, "闪送": 1}) == "用到了 团购券×2、闪送"


# ===== patch service: replace swaps caps =====

def _poi_with_caps(pid, name, cat, caps, deal=None):
    p = POI(
        id=pid, name=name, category=cat, rating=4.5, review_count=100,
        location={"lat": 39.9, "lng": 116.4}, address=f"{name} 地址",
        open_time=time(10), close_time=time(22),
        avg_duration=60, price_per_person=80, tags=[], peak_hours=[],
        queue_factor=1.0, capacity=50,
    )
    p.capability_tags = caps
    p.deal_label = deal
    return p


def _node(poi, hour):
    arr = datetime(2026, 1, 1, hour, 0)
    return RouteNode(
        poi=poi, arrival_time=arr,
        departure_time=arr + timedelta(minutes=poi.avg_duration),
        travel_time_from_prev=0, travel_distance_from_prev=0,
        estimated_queue_time=0, activity_type="play",
    )


def test_replace_rewrites_task_capability_tags():
    """Swap a 餐厅 → 餐厅 with different caps; task.params must update."""
    old = _poi_with_caps("P101", "海底捞", "餐厅", ["团购券", "积分", "扫码点餐"],
                        "团购券 ¥158（省 ¥42）")
    new = _poi_with_caps("P102", "上海姥姥", "餐厅", ["扫码点餐"], None)
    rp = RoutePlanner()
    rp.load_mock_data([old, new])
    route = [_node(old, 18)]
    tasks = [Task("T001", "搜索海底捞", "search_poi",
                  {"poi_id": "P101", "poi_name": "海底捞",
                   "capability_tags": ["团购券", "积分", "扫码点餐"],
                   "deal_label": "团购券 ¥158（省 ¥42）"})]
    action = ModificationAction(
        action_type="replace", target_ref="T001", target_poi_id="P101",
        new_poi_name="上海姥姥",
    )
    new_tasks, _, log = patch_svc.apply_modification(action, tasks, route, {}, {}, rp)
    assert log[0]["type"] == "replace"
    p = new_tasks[0].params
    assert p["capability_tags"] == ["扫码点餐"]
    assert "deal_label" not in p  # cleared because new poi has none


def test_replace_to_poi_without_caps_clears_label():
    old = _poi_with_caps("P101", "海底捞", "餐厅", ["团购券", "积分"],
                        "团购券 ¥158（省 ¥42）")
    new_no_caps = _poi_with_caps("P201", "野菜馆", "餐厅", [], None)
    rp = RoutePlanner()
    rp.load_mock_data([old, new_no_caps])
    route = [_node(old, 18)]
    tasks = [Task("T001", "x", "search_poi",
                  {"poi_id": "P101", "poi_name": "海底捞",
                   "capability_tags": ["团购券"], "deal_label": "团购券 ¥158"})]
    action = ModificationAction(action_type="replace", target_ref="T001",
                                target_poi_id="P101", new_poi_name="野菜馆")
    new_tasks, _, _ = patch_svc.apply_modification(action, tasks, route, {}, {}, rp)
    p = new_tasks[0].params
    assert "capability_tags" not in p
    assert "deal_label" not in p


def test_insert_carries_caps_into_new_task():
    """Newly inserted task should pick up the chosen POI's caps."""
    existing = _poi_with_caps("P101", "海底捞", "餐厅", ["团购券"], "团购券 ¥158")
    fresh = _poi_with_caps("P301", "星巴克", "咖啡馆", ["扫码点餐"], None)
    rp = RoutePlanner()
    rp.load_mock_data([existing, fresh])
    route = [_node(existing, 18)]
    tasks = [Task("T001", "x", "search_poi", {"poi_id": "P101"})]
    action = ModificationAction(action_type="insert", new_category="咖啡馆")
    new_tasks, _, log = patch_svc.apply_modification(action, tasks, route, {}, {}, rp)
    assert log[0]["type"] == "insert"
    inserted = next(t for t in new_tasks if t.task_id == log[0]["task_id"])
    assert inserted.params.get("capability_tags") == ["扫码点餐"]
