"""
Modification parser tests - covers 12 representative utterances.

Each test asserts the rule-based parser correctly classifies an action_type
and extracts the right fields (target hint, new category/name, time delta).
"""

import pytest
from dataclasses import dataclass
from agent.core.services import modification_parser as mp


# Lightweight stubs so we don't need a real RoutePlanner / POI database
@dataclass
class _POI:
    id: str
    name: str
    category: str
    tags: tuple = ()
    address: str = ""


@dataclass
class _Node:
    poi: _POI


@dataclass
class _Task:
    task_id: str
    name: str
    tool_name: str = "search_poi"
    params: dict = None


def _route():
    return [
        _Node(_POI("P1", "故宫博物院", "博物馆", ("文化",), "北京东城区景山前街")),
        _Node(_POI("P2", "海底捞", "餐厅", ("火锅",), "北京三里屯太古里")),
        _Node(_POI("P3", "K歌之王", "KTV", (), "北京工体北路")),
    ]


def _tasks():
    return [
        _Task("T001", "搜索故宫", params={"poi_id": "P1"}),
        _Task("T002", "搜索海底捞", params={"poi_id": "P2"}),
        _Task("T003", "搜索K歌之王", params={"poi_id": "P3"}),
    ]


@pytest.mark.parametrize("text,expected_type,checks", [
    # replace by category
    ("把餐厅换成本帮菜", "replace", {"new_category": "餐厅"}),
    # replace by position
    ("第二个换一家", "replace", {"target_hint_index": 1}),
    # replace by poi name
    ("把海底捞换成望京小腰", "replace", {"new_poi_name": "望京小腰"}),
    # remove by location
    ("不要去三里屯", "remove", {"target_hint_location": "三里屯"}),
    # remove by category
    ("不要KTV了", "remove", {"target_hint_category": "KTV"}),
    # remove last
    ("删掉最后那个", "remove", {"target_hint_index": -1}),
    # insert by category
    ("再加一家咖啡", "insert", {"new_category": "咖啡馆"}),
    # insert middle
    ("中间加个奶茶", "insert", {"new_category": "甜品店"}),
    # shift later
    ("晚一点开始", "shift_time", {"time_delta_min_positive": True}),
    # shift earlier
    ("早点开始", "shift_time", {"time_delta_min_negative": True}),
    # absolute time
    ("改成晚上7点", "shift_time", {"absolute_start": "19:00"}),
    # dislike
    ("下次别推三里屯了", "declare_dislike", {"target_hint_location": "三里屯"}),
    ("我不喜欢火锅", "declare_dislike", {"target_hint_category": "餐厅"}),
])
def test_parser_classifies_utterances(text, expected_type, checks):
    action = mp.parse(text, _tasks(), _route(), {})
    assert action is not None, f"parser returned None for: {text}"
    assert action.action_type == expected_type, (
        f"expected {expected_type} for '{text}', got {action.action_type}"
    )
    if "new_category" in checks:
        assert action.new_category == checks["new_category"]
    if "new_poi_name" in checks:
        assert action.new_poi_name == checks["new_poi_name"]
    if "target_hint_index" in checks:
        assert action.target_hint.get("index") == checks["target_hint_index"]
    if "target_hint_location" in checks:
        assert action.target_hint.get("location") == checks["target_hint_location"]
    if "target_hint_category" in checks:
        assert action.target_hint.get("category") == checks["target_hint_category"]
    if "time_delta_min_positive" in checks:
        assert action.time_delta_min is not None and action.time_delta_min > 0
    if "time_delta_min_negative" in checks:
        assert action.time_delta_min is not None and action.time_delta_min < 0
    if "absolute_start" in checks:
        assert action.absolute_start == checks["absolute_start"]


def test_parser_returns_none_for_non_modification():
    """Pure greetings / questions shouldn't match modification rules."""
    assert mp.parse("你好", _tasks(), _route(), {}) is None
    assert mp.parse("这个行程怎么样？", _tasks(), _route(), {}) is None


def test_parser_false_positive_avoidance():
    """'不要太贵' is a constraint, not a remove."""
    action = mp.parse("不要太贵", _tasks(), _route(), {})
    assert action is None or action.action_type != "remove"


def test_resolve_target_index():
    """Position hint resolves to correct poi_id + task_id."""
    action = mp.parse("第二个换一家", _tasks(), _route(), {})
    assert action.target_poi_id == "P2"
    assert action.target_ref == "T002"


def test_resolve_target_by_poi_name():
    """POI name hint resolves directly."""
    action = mp.parse("把海底捞换成望京小腰", _tasks(), _route(), {})
    assert action.target_poi_id == "P2"
    assert action.target_ref == "T002"


def test_resolve_target_by_category():
    """Category hint resolves to first matching POI in route."""
    action = mp.parse("把餐厅换成本帮菜", _tasks(), _route(), {})
    assert action.target_poi_id == "P2"


def test_replace_tag_extracted():
    """'换成火锅' should set tag=火锅 within 餐厅 category."""
    action = mp.parse("把餐厅换成火锅", _tasks(), _route(), {})
    assert action.action_type == "replace"
    assert action.new_category == "餐厅"
    assert action.new_tag == "火锅"
