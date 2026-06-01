"""
美团 AI Agent 主入口
演示完整的工作流程
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logging.info(f"已加载环境变量: {env_path}")
except ImportError:
    pass

# Windows 控制台编码修复
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from .core.planner import Planner
from .core.state_machine import StateMachine
from .core.exception_handler import ExceptionHandler
from .core.session import SessionManager
from .core.route_planner import RoutePlanner
from .core.poi_data import load_all_pois
from .core.scene_manager import SceneManager, SceneType
from .core.story_engine import StoryEngine
from .tools.base import ToolRegistry
from .tools.search_poi import SearchPOITool
from .tools.book_restaurant import BookRestaurantTool
from .tools.check_queue import CheckQueueTool
from .tools.order_delivery import OrderDeliveryTool
from .tools.weather_api import WeatherAPITool
from .tools.book_venue import BookVenueTool
from .llm.client import LLMClient, LLMConfig

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_agent(
    llm_provider: str = None,
    api_key: str = None,
    model: str = None,
    base_url: str = None,
    session_manager: SessionManager = None,
    live: bool = False,
) -> Planner:
    """
    创建 Agent 实例

    配置优先级：--live 参数 > LLM_MODE 环境变量 > 参数 > 环境变量 > config.json > Mock 降级

    Args:
        llm_provider: LLM 提供商 (mock/claude/openai/deepseek)
        api_key: API 密钥
        model: 模型名称
        base_url: API 端点
        session_manager: 共享的会话管理器
        live: 显式启用真实 LLM（跳过 mock 默认）
    """
    # 1. 从 config.json 读取默认配置（如果存在）
    config_from_file = {}
    config_path = Path(__file__).parent.parent / "config.json"
    if config_path.exists():
        try:
            import json
            with open(config_path, encoding="utf-8") as f:
                config_from_file = json.load(f)
            logger.info(f"已加载配置文件: {config_path}")
        except Exception as e:
            logger.warning(f"读取配置文件失败: {e}")

    # 2. LLM_MODE 控制：mock / live / auto（默认）
    llm_mode = os.environ.get("LLM_MODE", "auto").lower()

    # 如果显式 --live 或 LLM_MODE=live，强制使用真实 LLM
    if live or llm_mode == "live":
        llm_mode = "live"
    # 如果 LLM_MODE=mock，强制使用 mock
    elif llm_mode == "mock":
        pass
    # auto 模式：没有 API Key 就用 mock
    else:
        llm_mode = "auto"

    # 3. 配置优先级：参数 > 环境变量 > config.json > 默认值
    llm_provider = (
        llm_provider
        or os.environ.get("LLM_PROVIDER")
        or config_from_file.get("llm_provider")
        or "openai"
    )
    api_key = (
        api_key
        or os.environ.get("LLM_API_KEY")
        or config_from_file.get("llm_api_key")
        or ""
    )
    model = (
        model
        or os.environ.get("LLM_MODEL")
        or config_from_file.get("llm_model")
        or "mimo-v2.5-pro"
    )
    base_url = (
        base_url
        or os.environ.get("LLM_BASE_URL")
        or config_from_file.get("llm_base_url")
        or ""
    )

    # 4. 根据 llm_mode 决定最终 provider
    if llm_mode == "mock":
        llm_provider = "mock"
        logger.info("LLM 模式: Mock（显式指定）")
    elif not api_key and llm_provider != "mock":
        logger.warning(
            f"⚠️ 未配置 LLM API Key（provider={llm_provider}），将使用 Mock 模式。\n"
            f"请设置环境变量 LLM_API_KEY 或在 config.json 中配置 llm_api_key"
        )
        llm_provider = "mock"

    # 4. 初始化工具注册表
    tool_registry = ToolRegistry()
    tool_registry.register(SearchPOITool())
    tool_registry.register(BookRestaurantTool())
    tool_registry.register(CheckQueueTool())
    tool_registry.register(OrderDeliveryTool())
    tool_registry.register(WeatherAPITool())
    tool_registry.register(BookVenueTool())

    # 5. 初始化状态机
    state_machine = StateMachine()

    # 6. 初始化异常处理器
    exception_handler = ExceptionHandler(state_machine, tool_registry=tool_registry)

    # 7. 初始化 LLM 客户端
    if llm_provider == "mock":
        llm_client = LLMClient()  # Mock 模式
        logger.info("LLM 模式: Mock（离线）")
    else:
        llm_config = LLMConfig(
            provider=llm_provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
        llm_client = LLMClient(llm_config)
        logger.info(f"LLM 配置: provider={llm_provider}, model={model}")

    # 8. 初始化会话管理器（支持外部传入以共享 session 状态）
    if not session_manager:
        session_manager = SessionManager()

    # 9. 初始化路线规划引擎 + 加载 POI 数据
    route_planner = RoutePlanner()
    pois = load_all_pois()
    route_planner.load_mock_data(pois)
    logger.info(f"路线规划引擎已加载 {len(pois)} 个 POI")

    # 10. 初始化场景管理器
    scene_manager = SceneManager()

    # 11. 初始化剧本杀叙事引擎
    story_engine = StoryEngine(llm_client=llm_client)

    # 12. 创建规划引擎
    planner = Planner(
        tool_registry=tool_registry,
        state_machine=state_machine,
        exception_handler=exception_handler,
        llm_client=llm_client,
        session_manager=session_manager,
        route_planner=route_planner,
        scene_manager=scene_manager,
        story_engine=story_engine,
    )

    return planner


async def demo_normal_flow():
    """演示正常流程"""
    print("\n" + "=" * 60)
    print("场景一：正常流程 - 家庭周末出游")
    print("=" * 60)

    planner = create_agent()

    user_input = "这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜"

    print(f"\n用户输入: {user_input}")
    print("\n开始规划...\n")

    result = await planner.run(user_input)

    print("\n" + "-" * 40)
    print("执行结果:")
    print("-" * 40)

    if result.get("status") == "success":
        print("✅ 所有任务执行成功！")

        # 打印各任务结果
        for task_id, task_result in result.get("results", {}).items():
            print(f"\n📌 {task_id}:")
            if isinstance(task_result, dict):
                for key, value in task_result.items():
                    if key != "results":  # 跳过长列表
                        print(f"   {key}: {value}")
    else:
        print(f"⚠️ 执行状态: {result.get('status')}")


async def demo_fallback_flow():
    """演示备选方案流程"""
    print("\n" + "=" * 60)
    print("场景二：异常处理 - 餐厅满座自动切换")
    print("=" * 60)

    planner = create_agent()

    # 模拟 rest_002 满座的情况
    user_input = "带老婆吃海底捞，老婆在减肥，要有惊喜"

    print(f"\n用户输入: {user_input}")
    print("\n注意：海底捞已满座，将自动切换备选方案\n")

    result = await planner.run(user_input)

    print("\n" + "-" * 40)
    print("执行结果:")
    print("-" * 40)

    # 检查是否有任务使用了备选方案
    summary = result.get("summary", {})
    tasks = summary.get("tasks", [])
    for task in tasks:
        if task.get("status") == "FALLBACK":
            print(f"⚠️ 任务 {task['task_id']} 使用了备选方案")
            print(f"   原方案: {task.get('tool_name')}")
            print(f"   备选方案已自动切换")

    if result.get("status") == "success":
        print("\n✅ 所有任务执行成功（使用了备选方案）")


async def demo_replan_flow():
    """演示重新规划流程"""
    print("\n" + "=" * 60)
    print("场景三：重新规划 - 天气突变")
    print("=" * 60)

    planner = create_agent()

    # 设置天气为雨天
    weather_tool = planner.tool_registry.get("weather_api")
    if weather_tool:
        weather_tool.set_mock_weather("rainy")

    user_input = "这周六带老婆孩子出去玩，孩子5岁，老婆在减肥"

    print(f"\n用户输入: {user_input}")
    print("\n注意：检测到下午有雨，可能触发重新规划\n")

    result = await planner.run(user_input)

    print("\n" + "-" * 40)
    print("执行结果:")
    print("-" * 40)

    if result.get("status") == "replan_needed":
        print("🔄 触发重新规划")
        print(f"   原因: {result.get('reason')}")
        print(f"   通知: {result.get('notification')}")
    elif result.get("status") == "success":
        print("✅ 所有任务执行成功")
        # 检查天气结果
        weather_result = result.get("results", {}).get("T001", {})
        if weather_result.get("condition") == "阵雨":
            print("   已检测到雨天，行程已调整为室内活动")


async def demo_multi_turn():
    """演示多轮对话 - 7 步真实 patch 流"""
    print("\n" + "=" * 60)
    print("场景四：多轮对话 - 局部修改 + 偏好记忆 (v2.2)")
    print("=" * 60)

    planner = create_agent()

    # Step 1: 初次规划
    step1 = "周六全家三人去三里屯玩，预算 800，想吃点好的"
    print(f"\n[1/7] 用户: {step1}")
    res = await planner.run(step1)
    sid = res.get("session_id")
    route = (res.get("route") or [])
    names = " → ".join(r.get("poi_name", "?") for r in route)
    print(f"      方案 A: {names}")

    # Step 2: 换餐厅
    step2 = "把餐厅换成烧烤"
    print(f"\n[2/7] 用户: {step2}")
    res = await planner.continue_conversation(step2, sid)
    _print_change(res)

    # Step 3: 删最后一个
    step3 = "删掉最后那个"
    print(f"\n[3/7] 用户: {step3}")
    res = await planner.continue_conversation(step3, sid)
    _print_change(res)

    # Step 4: 加咖啡
    step4 = "再加一家咖啡"
    print(f"\n[4/7] 用户: {step4}")
    res = await planner.continue_conversation(step4, sid)
    _print_change(res)

    # Step 5: 调时间
    step5 = "晚一点开始"
    print(f"\n[5/7] 用户: {step5}")
    res = await planner.continue_conversation(step5, sid)
    _print_change(res)

    # Step 6: 偏好声明
    step6 = "下次别推三里屯了"
    print(f"\n[6/7] 用户: {step6}")
    res = await planner.continue_conversation(step6, sid)
    _print_change(res)

    # Step 7: 确认执行
    print(f"\n[7/7] 用户: 确认执行")
    res = await planner.confirm_and_execute(sid, confirmed=True)
    print(f"      状态: {res.get('status')}, 任务 {len(res.get('results', {}))} 项完成")


def _print_change(result):
    """打印 patch 路径的变更日志"""
    status = result.get("status")
    if status == "plan_modified":
        log = result.get("change_log", [])
        for entry in log:
            t = entry.get("type")
            if t == "replace":
                print(f"      ✓ {entry['before']['name']} → {entry['after']['name']}")
            elif t == "remove":
                print(f"      ✕ 删除 {entry['removed']['name']}")
            elif t == "insert":
                print(f"      ＋ 加入 {entry['inserted']['name']}")
            elif t == "shift_time":
                print(f"      🕐 调整到 {entry.get('new_start')}")
            elif t == "preference_noted":
                noted = entry.get("noted", {})
                tag = noted.get("category") or noted.get("location") or noted.get("tag")
                print(f"      📝 已记下偏好: 不推荐「{tag}」")
    elif status == "plan_modify_failed":
        print(f"      ⚠️ {result.get('reply', '修改失败')}")
    else:
        print(f"      💬 {result.get('reply', '')[:60]}")


async def main():
    """主演示入口"""
    print("\n" + "=" * 70)
    print("   美团 AI Agent 跨业务智能规划系统 - Demo")
    print("=" * 70)

    await demo_normal_flow()
    await demo_fallback_flow()
    await demo_replan_flow()
    await demo_multi_turn()

    print("\n" + "=" * 70)
    print("   Demo 完成")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
