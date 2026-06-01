"""
LLM fallback robustness tests for Planner._build_action_from_llm + coercion helpers.

These guard the LLM fallback path in agent/core/planner.py:_llm_fallback_parse.
The LLM may return numbers as strings, target_hint as a bare poi name, action_type
not in the whitelist, etc. — coercion must squeeze it into a clean ModificationAction
or reject with None.
"""

import pytest

from agent.core.planner import (
    _coerce_time_delta,
    _coerce_hhmm,
    _coerce_target_hint,
    Planner,
)
from agent.core.services.modification_parser import ModificationAction


# ===== _coerce_time_delta =====

@pytest.mark.parametrize("value,expected", [
    (None, None),
    (30, 30),
    (-30, -30),
    (0, 0),
    (30.0, 30),
    ("30", 30),
    ("-30", -30),
    ("30 分钟", 30),
    ("推迟 90 分钟", 90),
    ("提前-15分钟", -15),
    ("abc", None),
    ("", None),
    (True, None),         # bool must not slip through as int
    (False, None),
    ([], None),
    ({}, None),
])
def test_coerce_time_delta(value, expected):
    assert _coerce_time_delta(value) == expected


# ===== _coerce_hhmm =====

@pytest.mark.parametrize("value,expected", [
    ("19:00", "19:00"),
    ("9:30", "09:30"),       # zero-padded
    ("23:59", "23:59"),
    ("00:00", "00:00"),
    (" 19:00 ", "19:00"),    # stripped
    ("24:00", None),         # hour out of range
    ("19:60", None),         # minute out of range
    ("晚上7点", None),
    ("19", None),
    ("19:0", None),          # need 2-digit minutes
    (None, None),
    (1900, None),
    ("", None),
])
def test_coerce_hhmm(value, expected):
    assert _coerce_hhmm(value) == expected


# ===== _coerce_target_hint =====

def test_coerce_target_hint_dict_passthrough():
    assert _coerce_target_hint({"index": 1}) == {"index": 1}
    assert _coerce_target_hint({}) == {}


def test_coerce_target_hint_string_wraps_as_poi_name():
    assert _coerce_target_hint("海底捞") == {"poi_name": "海底捞"}
    assert _coerce_target_hint("  星巴克  ") == {"poi_name": "星巴克"}


def test_coerce_target_hint_empty_string_drops():
    assert _coerce_target_hint("") == {}
    assert _coerce_target_hint("   ") == {}


def test_coerce_target_hint_other_types_drop():
    assert _coerce_target_hint(None) == {}
    assert _coerce_target_hint(123) == {}
    assert _coerce_target_hint([1, 2]) == {}


# ===== Planner._build_action_from_llm — schema validation + coercion =====

def test_build_action_valid_replace():
    result = {
        "action_type": "replace",
        "target_hint": {"index": 1},
        "new_category": "火锅",
    }
    action = Planner._build_action_from_llm(result, "把第二个换成火锅")
    assert isinstance(action, ModificationAction)
    assert action.action_type == "replace"
    assert action.target_hint == {"index": 1}
    assert action.new_category == "火锅"
    assert action.confidence == 0.6
    assert action.raw == "把第二个换成火锅"


def test_build_action_shift_time_string_minutes():
    """LLM returns time_delta_min as a string — coercion squeezes to int."""
    result = {"action_type": "shift_time", "time_delta_min": "90"}
    action = Planner._build_action_from_llm(result, "晚一个半小时")
    assert action.time_delta_min == 90


def test_build_action_shift_time_absolute_invalid_dropped():
    """Bad HH:MM is silently dropped — caller will fall through to error."""
    result = {"action_type": "shift_time", "absolute_start": "晚上7点"}
    action = Planner._build_action_from_llm(result, "改成晚上7点")
    assert action.absolute_start is None


def test_build_action_shift_time_absolute_valid():
    result = {"action_type": "shift_time", "absolute_start": "19:00"}
    action = Planner._build_action_from_llm(result, "改成晚上7点")
    assert action.absolute_start == "19:00"


def test_build_action_invalid_action_type_returns_none():
    result = {"action_type": "modify", "target_hint": {"index": 0}}
    action = Planner._build_action_from_llm(result, "改一下第一个")
    assert action is None


def test_build_action_missing_action_type_returns_none():
    assert Planner._build_action_from_llm({}, "x") is None
    assert Planner._build_action_from_llm({"target_hint": {}}, "x") is None


def test_build_action_non_dict_returns_none():
    assert Planner._build_action_from_llm("not a dict", "x") is None
    assert Planner._build_action_from_llm(None, "x") is None
    assert Planner._build_action_from_llm([], "x") is None


def test_build_action_target_hint_string_wrapped():
    """LLM emits bare POI name as target_hint string — must wrap as {poi_name:...}."""
    result = {"action_type": "remove", "target_hint": "海底捞"}
    action = Planner._build_action_from_llm(result, "不要海底捞了")
    assert action.target_hint == {"poi_name": "海底捞"}


def test_build_action_empty_string_fields_become_none():
    """LLM sometimes emits empty strings — treat as None to avoid downstream surprises."""
    result = {
        "action_type": "replace",
        "target_hint": {"index": 0},
        "new_category": "",
        "new_poi_name": "",
    }
    action = Planner._build_action_from_llm(result, "x")
    assert action.new_category is None
    assert action.new_poi_name is None


def test_build_action_declare_dislike():
    result = {"action_type": "declare_dislike", "target_hint": {"location": "三里屯"}}
    action = Planner._build_action_from_llm(result, "下次别推三里屯")
    assert action.action_type == "declare_dislike"
    assert action.target_hint == {"location": "三里屯"}


def test_build_action_chat_json_error_payload_returns_none():
    """chat_json returns {'error': '解析失败', 'raw_response': ...} on parse failure.
    No action_type → must reject, not raise."""
    result = {"error": "解析失败", "raw_response": "garbage"}
    assert Planner._build_action_from_llm(result, "x") is None
