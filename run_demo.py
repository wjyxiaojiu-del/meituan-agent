#!/usr/bin/env python3
"""
美团 AI Agent 竞赛演示脚本
3 个场景，展示核心能力：
  1. 家庭出游 — 基础功能全覆盖（天气+搜索+预订+配送）
  2. 剧本杀 Citywalk — 差异化亮点（剧情引擎+路线规划）
  3. 企业团建 — 高价值场景（场地预订+多人+预算控制）

用法：
  python run_demo.py                # 运行全部 3 个场景
  python run_demo.py --scenario 2   # 只运行场景 2
  python run_demo.py --quick        # 快速模式（跳过确认步骤）
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from agent.main import create_agent


# ===== 终端颜色 =====

class C:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'
    GRAY = '\033[90m'
    WHITE = '\033[97m'


def print_banner():
    print(f"\n{C.CYAN}{'='*70}{C.END}")
    print(f"{C.BOLD}{C.YELLOW}   美团 AI Agent — 剧本杀 Citywalk × 智能行程规划{C.END}")
    print(f"{C.GRAY}   不只是推荐去哪玩，而是把整座城市变成沉浸式游戏场{C.END}")
    print(f"{C.CYAN}{'='*70}{C.END}")


def print_divider(title="", char="─"):
    if title:
        print(f"\n{C.BOLD}{C.BLUE}{char*60}{C.END}")
        print(f"{C.BOLD}  {title}{C.END}")
        print(f"{C.BOLD}{C.BLUE}{char*60}{C.END}")
    else:
        print(f"{C.GRAY}{char*60}{C.END}")


def print_user(text):
    print(f"\n  {C.GREEN}{C.BOLD}👤 用户:{C.END} {text}")


def print_agent(text, color=C.YELLOW):
    print(f"  {C.BOLD}{color}🤖 Agent:{C.END} {text}")


def print_plan_summary(plan):
    summary = plan.get("plan_summary", "")
    if summary:
        for line in summary.split("\n"):
            print(f"  {C.YELLOW}{line}{C.END}")


def print_route(route):
    if not route:
        return
    print(f"\n  {C.CYAN}{C.BOLD}🗺  路线规划:{C.END}")
    if isinstance(route, list):
        for i, node in enumerate(route):
            name = node.get("poi_name", node.get("name", ""))
            arrive = node.get("arrival_time", "")
            depart = node.get("departure_time", "")
            category = node.get("category", "")
            prefix = "📍" if i == 0 else "├─"
            travel = node.get("travel_time_from_prev", 0)
            if i > 0 and travel:
                print(f"  {C.GRAY}   🚶 {travel}分钟{C.END}")
            print(f"  {C.CYAN}   {prefix} {arrive}-{depart} {name} ({category}){C.END}")
    elif isinstance(route, dict):
        display = route.get("display", "")
        if display:
            for line in display.split("\n"):
                print(f"  {C.CYAN}   {line}{C.END}")


def print_story(story):
    if not story:
        return
    print(f"\n  {C.BOLD}{C.HEADER}🎭 剧情模式:{C.END}")
    print(f"  {C.BOLD}{C.WHITE}{story.get('title', '')}{C.END}")
    theme = story.get("theme", "")
    desc = story.get("description", "")
    if theme:
        print(f"  {C.GRAY}主题：{theme}{C.END}")
    if desc:
        print(f"  {C.GRAY}{desc}{C.END}")
    checkpoints = story.get("checkpoints", [])
    if checkpoints:
        print(f"\n  {C.WHITE}📍 任务节点:{C.END}")
        for i, cp in enumerate(checkpoints, 1):
            poi = cp.get("poi_name", "")
            narrative = cp.get("narrative", "")
            task = cp.get("task", "")
            print(f"  {C.YELLOW}   第{i}关：{poi}{C.END}")
            if narrative:
                print(f"  {C.GRAY}     📖 {narrative}{C.END}")
            if task:
                print(f"  {C.GRAY}     🎯 {task}{C.END}")


def print_tasks_preview(tasks):
    if not tasks:
        return
    print(f"\n  {C.GRAY}📋 任务列表:{C.END}")
    for t in tasks:
        tid = t.get("task_id", "")
        name = t.get("name", "")
        tool = t.get("tool_name", "")
        print(f"  {C.GRAY}   {tid}: {name} ({tool}){C.END}")


def print_execution_results(results):
    if not results:
        return
    print(f"\n  {C.GREEN}{C.BOLD}⚡ 执行结果:{C.END}")
    for tid, tr in results.items():
        if not isinstance(tr, dict):
            continue
        name = tr.get("task_name", tid)
        status_icon = f"{C.GREEN}✓{C.END}"
        extra = ""
        if "booking_id" in tr:
            extra = f" → 预订号 {tr['booking_id']}"
            venue = tr.get("venue_name") or tr.get("restaurant_name", "")
            if venue:
                extra = f" → {venue} 已预订"
        elif "my_number" in tr:
            extra = f" → 排队号 {tr['my_number']}"
        elif "order_id" in tr:
            item = tr.get("item_name", "")
            price = tr.get("total_price", "")
            extra = f" → {item} ¥{price} 订单{tr['order_id']}"
        elif "condition" in tr:
            cond = tr.get("condition", "")
            temp = tr.get("temperature", "")
            suggestion = tr.get("suggestion", "")
            extra = f" → {cond} {temp}°C"
            if suggestion:
                extra += f"（{suggestion}）"
        elif "results" in tr:
            count = tr.get("total", len(tr.get("results", [])))
            extra = f" → 找到 {count} 个结果"
        print(f"    {status_icon} {name}{extra}")


def print_share_text(share_text):
    if not share_text:
        return
    print(f"\n  {C.YELLOW}{C.BOLD}📤 分享文案:{C.END}")
    print(f"  {C.YELLOW}\"{share_text}\"{C.END}")


async def run_scenario(agent, scenario_num, title, user_input, quick=False):
    """运行一个完整演示场景"""
    print_divider(f"场景{scenario_num}：{title}")
    print_user(user_input)

    # 1. 规划
    print(f"\n  {C.CYAN}⏳ 正在规划...{C.END}")
    plan = await agent.run(user_input)

    if plan.get("status") != "waiting_confirmation":
        print(f"  {C.RED}❌ 规划失败: {plan.get('status')}{C.END}")
        return

    # 展示方案
    print_plan_summary(plan)
    print_route(plan.get("route"))
    print_story(plan.get("story"))
    print_tasks_preview(plan.get("tasks_preview", []))

    session_id = plan.get("session_id")

    if quick:
        # 快速模式：直接展示方案，跳过执行
        print(f"\n  {C.GRAY}[快速模式：跳过执行步骤]{C.END}")
        return plan

    # 2. 确认执行
    print(f"\n  {C.GREEN}{C.BOLD}👤 用户:{C.END} 确认，执行吧！")
    print(f"\n  {C.CYAN}⚡ 正在执行...{C.END}")

    result = await agent.confirm_and_execute(session_id, confirmed=True)

    # 3. 展示结果
    print(f"\n  {C.GREEN}{C.BOLD}✅ 执行完成！状态：{result.get('status', 'unknown')}{C.END}")
    print_execution_results(result.get("results", {}))
    print_share_text(result.get("share_text"))

    return result


SCENARIOS = [
    ("一", "家庭周末出游（基础功能全覆盖）",
     "这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜"),
    ("二", "朋友聚会 + 剧本杀 Citywalk（差异化亮点）",
     "周末和4个朋友一起出去玩，想玩点不一样的，要有剧情有挑战"),
    ("三", "企业团建（高价值场景）",
     "公司20人团建，要会议室和聚餐，预算人均200"),
]


async def main():
    parser = argparse.ArgumentParser(description="美团 AI Agent 演示脚本")
    parser.add_argument("--scenario", type=int, choices=[1, 2, 3],
                        help="只运行指定场景（1/2/3）")
    parser.add_argument("--quick", action="store_true",
                        help="快速模式：只展示规划，跳过执行步骤")
    args = parser.parse_args()

    print_banner()

    # 初始化
    print(f"\n  {C.CYAN}正在初始化 Agent...{C.END}")
    agent = create_agent()
    llm_config = agent.llm_client.config
    has_key = bool(llm_config.api_key)
    mode = f"{llm_config.provider}/{llm_config.model}" if has_key else "Mock（离线模式）"
    print(f"  {C.GREEN}✓ Agent 就绪{C.END}  {C.GRAY}[LLM: {mode}]{C.END}")

    if args.quick:
        print(f"  {C.YELLOW}⚡ 快速模式：只展示规划结果{C.END}")

    # 选择要运行的场景
    if args.scenario:
        scenarios = [SCENARIOS[args.scenario - 1]]
    else:
        scenarios = SCENARIOS

    for num, title, user_input in scenarios:
        await run_scenario(agent, num, title, user_input, quick=args.quick)

    # 结束
    print(f"\n{C.CYAN}{'='*70}{C.END}")
    print(f"{C.BOLD}{C.GREEN}   演示完成！感谢观看{C.END}")
    print(f"{C.CYAN}{'='*70}{C.END}\n")


if __name__ == "__main__":
    asyncio.run(main())
