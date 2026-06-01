"""
Story-engine + patch path coupling tests:
- When the user runs an initial plan that includes a 剧本杀 story, then patches the route
  (replace / remove), the story.checkpoints must stay in sync:
  - 'replace' rewrites the checkpoint anchored to the old poi_id with the new POI
  - 'remove' drops the checkpoint for that poi_id
- These guard the demo: 评委 asks "换餐厅后剧情对得上吗" — yes.
"""

from dataclasses import dataclass, field
from typing import List

import pytest
from agent.main import create_agent
from agent.core.story_engine import StoryEngine, StoryRoute, StoryCheckpoint


# ===== Deterministic unit tests on remap_after_patch directly =====

@dataclass
class _POI:
    id: str
    name: str
    category: str = "餐厅"


@dataclass
class _Node:
    poi: _POI


def _build_story(items):
    cps = [StoryCheckpoint(poi_id=i, poi_name=n, narrative=f"📍 {n}：在这里寻找线索",
                           task="完成任务", hint="提示", reward="奖励") for i, n in items]
    return StoryRoute(title="测试剧本", theme="侦探", description="测试",
                      checkpoints=cps, total_duration=120, difficulty="medium")


def test_remap_replace_rewrites_checkpoint_name():
    engine = StoryEngine()
    story = _build_story([("P1", "海底捞"), ("P2", "星巴克")])
    new_nodes = [_Node(_POI("P9", "木屋烧烤")), _Node(_POI("P2", "星巴克", "咖啡馆"))]
    change_log = [{"type": "replace", "before": {"poi_id": "P1", "name": "海底捞"},
                   "after": {"poi_id": "P9", "name": "木屋烧烤"}}]

    result = engine.remap_after_patch(story, change_log, new_nodes)

    assert result is story
    ids = [cp.poi_id for cp in story.checkpoints]
    names = [cp.poi_name for cp in story.checkpoints]
    assert "P1" not in ids
    assert "P9" in ids
    assert "木屋烧烤" in names
    # narrative must mention the new POI, not the old one
    p9_cp = next(cp for cp in story.checkpoints if cp.poi_id == "P9")
    assert "木屋烧烤" in p9_cp.narrative
    assert "海底捞" not in p9_cp.narrative


def test_remap_remove_drops_checkpoint():
    engine = StoryEngine()
    story = _build_story([("P1", "海底捞"), ("P2", "星巴克"), ("P3", "桔子水晶")])
    new_nodes = [_Node(_POI("P1", "海底捞")), _Node(_POI("P2", "星巴克"))]
    change_log = [{"type": "remove", "removed": {"poi_id": "P3", "name": "桔子水晶"}}]

    engine.remap_after_patch(story, change_log, new_nodes)

    ids = [cp.poi_id for cp in story.checkpoints]
    assert ids == ["P1", "P2"]


def test_remap_insert_leaves_existing_checkpoints_intact():
    """Insert does NOT add a checkpoint (story stays minimal)."""
    engine = StoryEngine()
    story = _build_story([("P1", "海底捞"), ("P2", "星巴克")])
    new_nodes = [_Node(_POI("P1", "海底捞")), _Node(_POI("P9", "瑞幸")),
                 _Node(_POI("P2", "星巴克"))]
    change_log = [{"type": "insert", "inserted": {"poi_id": "P9", "name": "瑞幸"}}]

    engine.remap_after_patch(story, change_log, new_nodes)

    ids = [cp.poi_id for cp in story.checkpoints]
    assert ids == ["P1", "P2"]


def test_remap_shift_time_noop():
    engine = StoryEngine()
    story = _build_story([("P1", "海底捞"), ("P2", "星巴克")])
    change_log = [{"type": "shift_time", "new_start": "15:00"}]

    engine.remap_after_patch(story, change_log, [])

    ids = [cp.poi_id for cp in story.checkpoints]
    assert ids == ["P1", "P2"]


def test_remap_empty_story_returns_none():
    engine = StoryEngine()
    assert engine.remap_after_patch(None, [], []) is None


# ===== End-to-end smoke tests (integration with full agent) =====

def _has_story(session):
    sr = session.context.get("story_route")
    return sr is not None and getattr(sr, "checkpoints", None)


def _cp_ids(session):
    sr = session.context.get("story_route")
    if not sr:
        return []
    return [cp.poi_id for cp in sr.checkpoints]


def _cp_names(session):
    sr = session.context.get("story_route")
    if not sr:
        return {}
    return {cp.poi_id: cp.poi_name for cp in sr.checkpoints}


@pytest.mark.asyncio
async def test_replace_remaps_checkpoint_poi_reference():
    """Replace a POI that owns a story checkpoint → checkpoint must point at the new POI."""
    agent = create_agent()
    plan = await agent.run(
        "和朋友周末去三里屯玩，想体验剧本杀那种沉浸式剧情",
        session_id=None,
        enable_story=True,
    )
    session_id = plan["session_id"]
    session = agent.session_manager.get_session(session_id)

    if not _has_story(session):
        pytest.skip("Initial plan did not produce a story — environment-dependent")

    pending_nodes = session.context.get("pending_route_nodes") or []
    if len(pending_nodes) < 2:
        pytest.skip("Plan too small for replace test")

    # Find the first POI that owns a checkpoint
    cp_ids_before = set(_cp_ids(session))
    target_poi_id = None
    target_index = None
    for i, n in enumerate(pending_nodes):
        if n.poi.id in cp_ids_before:
            target_poi_id = n.poi.id
            target_index = i
            break
    if target_poi_id is None:
        pytest.skip("No checkpoint anchored to current route — cannot exercise remap")

    # Use a hint that targets that index
    ordinal = {0: "第一个", 1: "第二个", 2: "第三个"}.get(target_index)
    if not ordinal:
        pytest.skip("Target index too far for ordinal phrase")

    result = await agent.continue_conversation(f"{ordinal}换一家", session_id)
    if result["status"] != "plan_modified":
        pytest.skip(f"Replace patch couldn't find a candidate (status={result['status']})")
    assert result.get("action_type") == "replace"

    # Checkpoint that referenced old poi_id must now reference new poi_id
    cp_ids_after = set(_cp_ids(session))
    assert target_poi_id not in cp_ids_after, "old POI's checkpoint still references the removed POI"
    new_pending = session.context.get("pending_route_nodes") or []
    new_poi_id = new_pending[target_index].poi.id
    assert new_poi_id in cp_ids_after, "checkpoint was not remapped to the new POI"

    # Name must match the new POI's name
    names_after = _cp_names(session)
    assert names_after.get(new_poi_id) == new_pending[target_index].poi.name


@pytest.mark.asyncio
async def test_remove_drops_orphaned_checkpoint():
    """Remove a POI that owns a story checkpoint → checkpoint must be deleted."""
    agent = create_agent()
    plan = await agent.run(
        "和朋友去玩，想要剧情体验那种",
        session_id=None,
        enable_story=True,
    )
    session_id = plan["session_id"]
    session = agent.session_manager.get_session(session_id)

    if not _has_story(session):
        pytest.skip("Initial plan did not produce a story")

    pending_nodes = session.context.get("pending_route_nodes") or []
    if len(pending_nodes) < 2:
        pytest.skip("Plan too small for remove test")

    cp_ids_before = set(_cp_ids(session))
    last_poi_id = pending_nodes[-1].poi.id

    result = await agent.continue_conversation("删掉最后那个", session_id)
    assert result["status"] == "plan_modified"
    assert result.get("action_type") == "remove"

    cp_ids_after = set(_cp_ids(session))
    if last_poi_id in cp_ids_before:
        assert last_poi_id not in cp_ids_after, (
            "removed POI still owns a checkpoint after patch"
        )
    # All remaining checkpoints must still anchor to surviving route nodes
    surviving_ids = {n.poi.id for n in session.context["pending_route_nodes"]}
    for cp_id in cp_ids_after:
        assert cp_id in surviving_ids, f"orphan checkpoint {cp_id} not in route after remove"


@pytest.mark.asyncio
async def test_shift_time_does_not_touch_story():
    """shift_time only adjusts timestamps — checkpoints must be untouched."""
    agent = create_agent()
    plan = await agent.run(
        "周末去玩，沉浸式剧情",
        session_id=None,
        enable_story=True,
    )
    session_id = plan["session_id"]
    session = agent.session_manager.get_session(session_id)

    if not _has_story(session):
        pytest.skip("Initial plan did not produce a story")

    cp_ids_before = _cp_ids(session)
    names_before = _cp_names(session)

    result = await agent.continue_conversation("晚一点开始", session_id)
    # shift_time may succeed or roll back depending on business hours — either way no story change
    if result["status"] == "plan_modified":
        assert result.get("action_type") == "shift_time"

    cp_ids_after = _cp_ids(session)
    names_after = _cp_names(session)
    assert cp_ids_after == cp_ids_before, "shift_time should not alter checkpoint anchors"
    assert names_after == names_before, "shift_time should not alter checkpoint names"


@pytest.mark.asyncio
async def test_patch_response_includes_story_payload():
    """The /continue-style payload must surface the synced story so the frontend can render it."""
    agent = create_agent()
    plan = await agent.run("周六和朋友出去玩，想要剧本杀风格", enable_story=True)
    session_id = plan["session_id"]
    session = agent.session_manager.get_session(session_id)

    if not _has_story(session):
        pytest.skip("Initial plan did not produce a story")

    pending_nodes = session.context.get("pending_route_nodes") or []
    if len(pending_nodes) < 2:
        pytest.skip("Plan too small")

    result = await agent.continue_conversation("第一个换一家", session_id)
    if result["status"] != "plan_modified":
        pytest.skip(f"Patch did not match (status={result.get('status')})")
    story = result.get("story")
    assert story is not None, "/continue response missing story payload"
    assert "checkpoints" in story
    assert isinstance(story["checkpoints"], list)
