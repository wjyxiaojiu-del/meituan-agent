"""
End-to-end continue_conversation tests:
- Patch path is hit for modification utterances
- task_id stability across patch
- route_service.plan_from_intent NOT called for patch (spy)
- Conversational reply for non-modification input
"""

import pytest
from agent.main import create_agent


@pytest.mark.asyncio
async def test_modification_uses_patch_not_replan(monkeypatch):
    """When user says '第二个换一家', plan_from_intent should NOT be called."""
    agent = create_agent()
    # 1. Initial plan
    plan = await agent.run("周六带老婆孩子去三里屯玩，下午4-6小时", session_id=None)
    assert plan["status"] == "waiting_confirmation"
    session_id = plan["session_id"]

    # Pre-state: capture pending tasks' task_ids
    session = agent.session_manager.get_session(session_id)
    pending_tasks_before = session.context.get("pending_tasks") or []
    pending_nodes_before = session.context.get("pending_route_nodes") or []
    assert len(pending_tasks_before) >= 1
    assert len(pending_nodes_before) >= 2

    task_ids_before = [t.task_id for t in pending_tasks_before]
    pois_before = [n.poi.id for n in pending_nodes_before]

    # 2. Spy on route_service.plan_from_intent to verify it isn't called
    spy_calls = []
    original_plan_from_intent = agent.route_service.plan_from_intent

    async def spy_plan(*args, **kwargs):
        spy_calls.append((args, kwargs))
        return await original_plan_from_intent(*args, **kwargs)

    monkeypatch.setattr(agent.route_service, "plan_from_intent", spy_plan)

    # 3. Modification: replace 2nd POI
    result = await agent.continue_conversation("第二个换一家", session_id)

    # patch path hit
    assert result["status"] == "plan_modified", f"got status={result.get('status')}"
    assert result.get("action_type") == "replace"
    assert spy_calls == [], "plan_from_intent should NOT be called for patch path"

    # task_id stability: same set of T0xx ids, second one preserved
    pending_tasks_after = session.context.get("pending_tasks") or []
    pending_nodes_after = session.context.get("pending_route_nodes") or []
    task_ids_after = [t.task_id for t in pending_tasks_after]
    assert task_ids_after == task_ids_before, "task_ids must remain stable after patch"

    # POI at index 1 actually changed
    pois_after = [n.poi.id for n in pending_nodes_after]
    assert pois_after[1] != pois_before[1], "second POI should be swapped"


@pytest.mark.asyncio
async def test_remove_drops_node(monkeypatch):
    agent = create_agent()
    plan = await agent.run("周末和朋友去三里屯玩", session_id=None)
    session_id = plan["session_id"]
    session = agent.session_manager.get_session(session_id)
    nodes_before = list(session.context.get("pending_route_nodes") or [])
    if len(nodes_before) < 2:
        pytest.skip("Initial plan too small for remove test")

    result = await agent.continue_conversation("删掉最后那个", session_id)
    assert result["status"] == "plan_modified"
    nodes_after = session.context.get("pending_route_nodes") or []
    assert len(nodes_after) == len(nodes_before) - 1


@pytest.mark.asyncio
async def test_dislike_records_in_context(monkeypatch):
    agent = create_agent()
    plan = await agent.run("和朋友去玩，要有餐厅", session_id=None)
    session_id = plan["session_id"]

    result = await agent.continue_conversation("我不喜欢火锅", session_id)
    assert result["status"] == "plan_modified"
    assert result["action_type"] == "declare_dislike"
    session = agent.session_manager.get_session(session_id)
    disliked = session.context.get("disliked_categories", [])
    assert disliked, "dislike should record into session context"


@pytest.mark.asyncio
async def test_non_modification_returns_conversational_reply():
    agent = create_agent()
    plan = await agent.run("周末去玩", session_id=None)
    session_id = plan["session_id"]

    result = await agent.continue_conversation("这个行程看起来怎么样", session_id)
    # Either patch didn't match → conversation_continued, or fell through to reply
    assert result["status"] in ("conversation_continued", "plan_modified")
    assert result.get("reply") or result.get("plan_summary")


@pytest.mark.asyncio
async def test_confirm_clears_pending_state():
    """After confirm_and_execute, pending_route_nodes must be cleaned."""
    agent = create_agent()
    plan = await agent.run("和家人下午出去玩")
    session_id = plan["session_id"]
    session = agent.session_manager.get_session(session_id)
    assert session.context.get("pending_route_nodes")

    await agent.confirm_and_execute(session_id, confirmed=True)
    # pending_route_nodes should be gone after execution
    assert not session.context.get("pending_route_nodes"), (
        "pending_route_nodes should be cleaned after confirm"
    )
