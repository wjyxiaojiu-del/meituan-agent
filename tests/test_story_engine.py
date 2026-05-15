"""
Day 4 测试：场景管理器 + 剧本杀叙事引擎
"""

import pytest
import sys

sys.path.insert(0, ".")

from agent.core.scene_manager import SceneManager, SceneType
from agent.core.story_engine import StoryEngine, StoryRoute, StoryCheckpoint, STORY_TEMPLATES
from agent.core.route_planner import POI
from datetime import time


# ===== 场景管理器测试 =====

class TestSceneManager:
    """场景管理器测试"""

    @pytest.fixture
    def mgr(self):
        return SceneManager()

    def test_detect_family(self, mgr):
        intent = {
            "people": [{"role": "child", "age": 5}, {"role": "wife"}, {"role": "self"}],
            "raw_input": "带老婆孩子出去玩",
        }
        assert mgr.detect_scene(intent) == SceneType.FAMILY

    def test_detect_parent_child(self, mgr):
        intent = {
            "people": [{"role": "child", "age": 5}, {"role": "self"}],
            "raw_input": "带孩子出去玩",
        }
        assert mgr.detect_scene(intent) == SceneType.PARENT_CHILD

    def test_detect_date(self, mgr):
        intent = {
            "people": [{"role": "wife"}, {"role": "self"}],
            "raw_input": "和老婆约会",
        }
        assert mgr.detect_scene(intent) == SceneType.DATE

    def test_detect_friends(self, mgr):
        intent = {
            "people": [{"role": "friend"}, {"role": "friend"}, {"role": "friend"}, {"role": "self"}],
            "raw_input": "和朋友出去玩",
        }
        assert mgr.detect_scene(intent) == SceneType.FRIENDS

    def test_detect_solo(self, mgr):
        intent = {
            "people": [{"role": "self"}],
            "raw_input": "自己出去逛逛",
        }
        assert mgr.detect_scene(intent) == SceneType.SOLO

    def test_detect_team_building(self, mgr):
        intent = {
            "people": [{"role": "colleague"}, {"role": "colleague"}, {"role": "self"}],
            "raw_input": "公司团建",
        }
        assert mgr.detect_scene(intent) == SceneType.TEAM_BUILDING

    def test_get_scene_config(self, mgr):
        config = mgr.get_scene_config(SceneType.FAMILY)
        assert "poi_types" in config
        assert "default_budget_per_person" in config
        assert "儿童乐园" in config["poi_types"]

    def test_get_default_pois(self, mgr):
        mock_db = {
            "kids_001": POI(
                id="kids_001", name="奇乐儿", category="儿童乐园",
                rating=4.8, review_count=2300,
                location={"lat": 31.23, "lng": 121.47}, address="万达广场3楼",
                open_time=time(10, 0), close_time=time(21, 0), avg_duration=150,
                price_per_person=128, tags=["室内"],
                peak_hours=[(14, 16)], queue_factor=1.5,
            ),
            "rest_001": POI(
                id="rest_001", name="新元素", category="餐厅",
                rating=4.7, review_count=3100,
                location={"lat": 31.23, "lng": 121.47}, address="万达广场4楼",
                open_time=time(11, 0), close_time=time(22, 0), avg_duration=90,
                price_per_person=120, tags=["轻食"],
                peak_hours=[(12, 14)], queue_factor=1.3,
            ),
            "escape_001": POI(
                id="escape_001", name="X先生密室", category="密室逃脱",
                rating=4.8, review_count=1500,
                location={"lat": 31.23, "lng": 121.47}, address="南京东路",
                open_time=time(10, 0), close_time=time(23, 0), avg_duration=120,
                price_per_person=168, tags=["沉浸式"],
                peak_hours=[(14, 17)], queue_factor=1.8,
            ),
        }
        family_pois = mgr.get_default_pois(SceneType.FAMILY, mock_db)
        assert "kids_001" in family_pois
        assert "rest_001" in family_pois
        assert "escape_001" not in family_pois

        friends_pois = mgr.get_default_pois(SceneType.FRIENDS, mock_db)
        assert "escape_001" in friends_pois


# ===== 叙事引擎测试 =====

class TestStoryEngine:
    """叙事引擎测试"""

    @pytest.fixture
    def engine(self):
        return StoryEngine()

    def test_detect_story_preference_true(self, engine):
        assert engine.detect_story_preference("想玩点不一样的，要有剧情") is True
        assert engine.detect_story_preference("周末去玩剧本杀") is True
        assert engine.detect_story_preference("想闯关挑战一下") is True

    def test_detect_story_preference_false(self, engine):
        assert engine.detect_story_preference("带孩子出去玩") is False
        assert engine.detect_story_preference("和老婆吃饭") is False

    def test_select_template_family(self, engine):
        intent = {
            "people": [{"role": "child", "age": 5}, {"role": "wife"}, {"role": "self"}],
            "raw_input": "带孩子出去玩",
            "surprise": False,
        }
        assert engine.select_template(intent) == "亲子冒险"

    def test_select_template_team(self, engine):
        intent = {
            "people": [{"role": "colleague"}, {"role": "self"}],
            "raw_input": "公司团建",
            "surprise": False,
        }
        assert engine.select_template(intent) == "团建大作战"

    def test_select_template_date_with_surprise(self, engine):
        intent = {
            "people": [{"role": "wife"}, {"role": "self"}],
            "raw_input": "和老婆出去",
            "surprise": True,
        }
        assert engine.select_template(intent) == "浪漫逃亡"

    def test_select_template_default(self, engine):
        intent = {
            "people": [{"role": "self"}],
            "raw_input": "自己出去逛",
            "surprise": False,
        }
        assert engine.select_template(intent) == "美食侦探"

    @pytest.mark.asyncio
    async def test_generate_story_route(self, engine):
        """测试为路线生成剧情"""
        # 构造模拟路线节点
        mock_poi = POI(
            id="snack_001", name="城隍庙小吃街", category="小吃街",
            rating=4.4, review_count=8900,
            location={"lat": 31.22, "lng": 121.49}, address="豫园",
            open_time=time(10, 0), close_time=time(22, 0), avg_duration=90,
            price_per_person=60, tags=["老字号"],
            peak_hours=[(12, 14)], queue_factor=2.2,
        )

        class MockNode:
            def __init__(self, poi):
                self.poi = poi

        route = [MockNode(mock_poi)]
        intent = {
            "people": [{"role": "friend"}, {"role": "self"}],
            "raw_input": "和朋友出去玩",
            "surprise": False,
        }

        story = await engine.generate_story_route(intent, route)

        assert isinstance(story, StoryRoute)
        assert story.title is not None
        assert len(story.checkpoints) >= 1
        assert story.checkpoints[0].poi_name == "城隍庙小吃街"

    def test_format_story_for_display(self, engine):
        story = StoryRoute(
            title="《测试剧情》",
            theme="测试",
            description="这是一个测试",
            checkpoints=[
                StoryCheckpoint(
                    poi_id="test_001",
                    poi_name="测试地点",
                    narrative="测试剧情文本",
                    task="完成测试",
                    hint="没有提示",
                    reward="获得奖励",
                ),
            ],
            total_duration=120,
            difficulty="easy",
        )
        text = engine.format_story_for_display(story)
        assert "测试剧情" in text
        assert "测试地点" in text
        assert "完成测试" in text

    def test_story_templates_count(self):
        assert len(STORY_TEMPLATES) >= 4
        assert "美食侦探" in STORY_TEMPLATES
        assert "浪漫逃亡" in STORY_TEMPLATES
        assert "团建大作战" in STORY_TEMPLATES
        assert "亲子冒险" in STORY_TEMPLATES

    def test_template_structure(self):
        for name, tmpl in STORY_TEMPLATES.items():
            assert "title" in tmpl, f"{name} 缺少 title"
            assert "theme" in tmpl, f"{name} 缺少 theme"
            assert "description" in tmpl, f"{name} 缺少 description"
            assert "difficulty" in tmpl, f"{name} 缺少 difficulty"
            assert "checkpoints" in tmpl, f"{name} 缺少 checkpoints"
            assert len(tmpl["checkpoints"]) >= 2, f"{name} 至少需要 2 个 checkpoint"
            for cp in tmpl["checkpoints"]:
                assert "narrative" in cp, f"{name} checkpoint 缺少 narrative"
                assert "task" in cp, f"{name} checkpoint 缺少 task"
                assert "hint" in cp, f"{name} checkpoint 缺少 hint"
                assert "reward" in cp, f"{name} checkpoint 缺少 reward"

    @pytest.mark.asyncio
    async def test_route_more_nodes_than_checkpoints(self, engine):
        """路线节点多于 checkpoint 数量时，多余节点不生成故事"""
        mock_poi_a = POI(
            id="a", name="地点A", category="餐厅",
            rating=4.5, review_count=1000,
            location={"lat": 31.23, "lng": 121.47}, address="地址A",
            open_time=time(10, 0), close_time=time(22, 0), avg_duration=60,
            price_per_person=100, tags=[], peak_hours=[], queue_factor=1.0,
        )
        mock_poi_b = POI(
            id="b", name="地点B", category="咖啡馆",
            rating=4.5, review_count=1000,
            location={"lat": 31.23, "lng": 121.47}, address="地址B",
            open_time=time(10, 0), close_time=time(22, 0), avg_duration=60,
            price_per_person=50, tags=[], peak_hours=[], queue_factor=1.0,
        )
        mock_poi_c = POI(
            id="c", name="地点C", category="书店",
            rating=4.5, review_count=1000,
            location={"lat": 31.23, "lng": 121.47}, address="地址C",
            open_time=time(10, 0), close_time=time(22, 0), avg_duration=60,
            price_per_person=50, tags=[], peak_hours=[], queue_factor=1.0,
        )
        mock_poi_d = POI(
            id="d", name="地点D", category="电影院",
            rating=4.5, review_count=1000,
            location={"lat": 31.23, "lng": 121.47}, address="地址D",
            open_time=time(10, 0), close_time=time(22, 0), avg_duration=120,
            price_per_person=80, tags=[], peak_hours=[], queue_factor=1.0,
        )

        class MockNode:
            def __init__(self, poi):
                self.poi = poi

        route = [MockNode(mock_poi_a), MockNode(mock_poi_b), MockNode(mock_poi_c), MockNode(mock_poi_d)]
        intent = {"people": [{"role": "friend"}, {"role": "self"}], "raw_input": "和朋友出去玩", "surprise": False}

        story = await engine.generate_story_route(intent, route)
        # 美食侦探模板有3个checkpoint，但路线有4个节点
        assert len(story.checkpoints) == 3
        assert story.total_duration == 60 + 60 + 60 + 120

    @pytest.mark.asyncio
    async def test_route_fewer_nodes_than_checkpoints(self, engine):
        """路线节点少于 checkpoint 数量时，只生成对应数量的故事"""
        mock_poi = POI(
            id="x", name="唯一地点", category="餐厅",
            rating=4.5, review_count=1000,
            location={"lat": 31.23, "lng": 121.47}, address="地址",
            open_time=time(10, 0), close_time=time(22, 0), avg_duration=90,
            price_per_person=100, tags=[], peak_hours=[], queue_factor=1.0,
        )

        class MockNode:
            def __init__(self, poi):
                self.poi = poi

        route = [MockNode(mock_poi)]
        intent = {"people": [{"role": "friend"}, {"role": "self"}], "raw_input": "和朋友出去玩", "surprise": False}

        story = await engine.generate_story_route(intent, route)
        assert len(story.checkpoints) == 1
        assert story.checkpoints[0].poi_name == "唯一地点"

    @pytest.mark.asyncio
    async def test_empty_route(self, engine):
        """空路线应返回空 checkpoint 列表"""
        intent = {"people": [{"role": "self"}], "raw_input": "出去逛逛", "surprise": False}
        story = await engine.generate_story_route(intent, [])
        assert len(story.checkpoints) == 0
        assert story.total_duration == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ===== 集成测试 =====

class TestIntegration:
    """验证新模块正确集成到 create_agent"""

    def test_create_agent_has_scene_manager(self):
        from agent.main import create_agent
        agent = create_agent(llm_provider="mock")
        assert hasattr(agent, "scene_manager")
        assert agent.scene_manager is not None

    def test_create_agent_has_story_engine(self):
        from agent.main import create_agent
        agent = create_agent(llm_provider="mock")
        assert hasattr(agent, "story_engine")
        assert agent.story_engine is not None

    @pytest.mark.asyncio
    async def test_story_preference_triggers_in_run(self):
        """输入含剧情关键词时，返回结果应包含 story 字段"""
        from agent.main import create_agent
        agent = create_agent(llm_provider="mock")
        result = await agent.run("和朋友出去玩，想玩点不一样的，要有剧情")
        # story 可能为 None（Mock 模式下路线可能为空），但字段应该存在
        assert "story" in result
