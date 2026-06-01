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
import logging
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

# Demo 模式：静默 agent 日志
logging.basicConfig(level=logging.ERROR, format="%(message)s")
logging.getLogger("agent").setLevel(logging.ERROR)

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich.columns import Columns
from rich import box

from agent.main import create_agent

console = Console()


# ===== 动画工具 =====

async def animate_dots(text: str, duration: float = 0.8):
    """显示加载动画"""
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    end_time = time.time() + duration
    i = 0
    while time.time() < end_time:
        console.print(f"  [cyan]{frames[i % len(frames)]}[/] {text}", end="\r")
        await asyncio.sleep(0.08)
        i += 1
    console.print(" " * 60, end="\r")


async def run_with_spinner(coro, text: str):
    """带旋转动画运行异步任务"""
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    result = None
    done = False

    async def spin():
        i = 0
        while not done:
            console.print(f"  [cyan bold]{frames[i % len(frames)]}[/] {text}", end="\r")
            await asyncio.sleep(0.08)
            i += 1
        console.print(" " * 60, end="\r")

    spinner = asyncio.create_task(spin())
    try:
        result = await coro
    finally:
        done = True
        await spinner
    return result


# ===== 展示函数 =====

def print_banner():
    title = Text()
    title.append("美", style="bold red")
    title.append("团", style="bold yellow")
    title.append(" AI Agent", style="bold white")
    title.append(" — ", style="dim")
    title.append("剧本杀 Citywalk × 智能行程规划", style="bold cyan")

    subtitle = Text("不只是推荐去哪玩，而是把整座城市变成沉浸式游戏场", style="dim")

    console.print()
    console.print(Panel(
        Text.assemble(title, "\n", subtitle),
        border_style="bright_blue",
        padding=(1, 2),
        width=72,
    ))
    console.print()


def print_scenario_header(num: int, title: str):
    console.print()
    console.rule(f"[bold bright_blue] 场景{num}：{title} [/]", style="bright_blue")
    console.print()


def print_user_input(text: str):
    console.print(f"  [green bold]👤 用户：[/]{text}")
    console.print()


def print_plan_summary(summary: str):
    console.print(Panel(
        summary,
        title="[bold yellow]📋 方案摘要[/]",
        border_style="yellow",
        padding=(0, 2),
        width=70,
    ))


def print_route(route):
    if not route:
        return

    if isinstance(route, list):
        tree = Tree("[bold cyan]🗺  路线规划[/]", guide_style="cyan")
        for i, node in enumerate(route):
            name = node.get("poi_name", node.get("name", ""))
            arrive = node.get("arrival_time", "")
            depart = node.get("departure_time", "")
            category = node.get("category", "")
            travel = node.get("travel_time_from_prev", 0)

            # 品类颜色映射
            cat_colors = {
                "餐厅": "red", "咖啡馆": "yellow", "小吃街": "red",
                "儿童乐园": "green", "密室逃脱": "magenta", "KTV": "magenta",
                "剧本杀": "magenta", "轰趴馆": "bright_magenta", "会议室": "blue",
                "博物馆": "cyan", "书店": "cyan", "花店": "bright_green",
                "SPA": "bright_cyan", "电影院": "magenta", "甜品店": "yellow",
                "步行街": "white", "公园": "green", "户外拓展": "bright_green",
            }
            cat_color = cat_colors.get(category, "white")

            if i > 0 and travel:
                tree.add(f"[dim]🚶 步行 {travel} 分钟[/]")

            time_str = f"{arrive}-{depart}" if depart else arrive
            node_text = f"[bold {cat_color}]{name}[/] [dim]({category})[/]"
            time_text = f"[cyan]{time_str}[/]"

            if i == 0:
                tree.add(f"📍 {time_text}  {node_text}")
            else:
                tree.add(f"├─ {time_text}  {node_text}")

        console.print(tree)
    elif isinstance(route, dict):
        display = route.get("display", "")
        if display:
            console.print(f"  [cyan]{display}[/]")


def print_story(story):
    if not story:
        return

    title = story.get("title", "")
    theme = story.get("theme", "")
    desc = story.get("description", "")

    # 标题面板
    header = Text()
    header.append(f"🎭 {title}", style="bold bright_magenta")
    if theme:
        header.append(f"\n主题：{theme}", style="dim")

    checkpoints = story.get("checkpoints", [])

    # 用表格展示 checkpoints
    if checkpoints:
        table = Table(
            show_header=True,
            header_style="bold bright_magenta",
            box=box.ROUNDED,
            border_style="magenta",
            width=68,
            padding=(0, 1),
        )
        table.add_column("关卡", style="bold yellow", width=6)
        table.add_column("地点", style="bold white", width=14)
        table.add_column("剧情 & 任务", width=44)

        for i, cp in enumerate(checkpoints, 1):
            poi = cp.get("poi_name", "")
            narrative = cp.get("narrative", "")
            task = cp.get("task", "")
            content = Text()
            content.append(f"📖 {narrative}\n", style="dim")
            content.append(f"🎯 {task}", style="bright_white")
            table.add_row(f"第{i}关", poi, content)

        console.print()
        console.print(table)
        console.print(f"  [dim]{desc}[/]")


def print_tasks_preview(tasks):
    if not tasks:
        return
    table = Table(
        show_header=True,
        header_style="bold",
        box=box.SIMPLE,
        border_style="dim",
        width=50,
    )
    table.add_column("ID", style="dim", width=5)
    table.add_column("任务", width=20)
    table.add_column("工具", style="cyan", width=16)

    for t in tasks:
        tid = t.get("task_id", "")
        name = t.get("name", "")
        tool = t.get("tool_name", "")
        table.add_row(tid, name, tool)

    console.print()
    console.print(table)


def print_execution_results(results):
    if not results:
        return

    table = Table(
        show_header=False,
        box=box.ROUNDED,
        border_style="green",
        width=68,
        padding=(0, 1),
    )
    table.add_column("", width=3)
    table.add_column("任务", style="bold", width=18)
    table.add_column("结果", width=43)

    for tid, tr in results.items():
        if not isinstance(tr, dict):
            continue
        name = tr.get("task_name", tid)
        detail = Text()

        if "booking_id" in tr:
            venue = tr.get("venue_name") or tr.get("restaurant_name", "")
            detail.append(f"→ {venue} 已预订", style="green")
        elif "my_number" in tr:
            detail.append(f"→ 排队号 {tr['my_number']}", style="green")
        elif "order_id" in tr:
            item = tr.get("item_name", "")
            price = tr.get("total_price", "")
            detail.append(f"→ {item} ¥{price}", style="green")
            detail.append(f"\n   订单号 {tr['order_id']}", style="dim")
        elif "condition" in tr:
            cond = tr.get("condition", "")
            temp = tr.get("temperature", "")
            suggestion = tr.get("suggestion", "")
            detail.append(f"→ {cond} {temp}°C", style="green")
            if suggestion:
                detail.append(f"\n   {suggestion}", style="dim")
        elif "results" in tr:
            count = tr.get("total", len(tr.get("results", [])))
            detail.append(f"→ 找到 {count} 个结果", style="green")
        else:
            detail.append("→ 完成", style="green")

        table.add_row("✓", name, detail)

    console.print()
    console.print(table)


def print_share_text(share_text):
    if not share_text:
        return
    console.print()
    console.print(Panel(
        f'"{share_text}"',
        title="[bold yellow]📤 微信分享文案[/]",
        border_style="yellow",
        padding=(0, 2),
        width=70,
    ))


def print_scenario_stats(results, elapsed: float):
    """场景结束统计"""
    if not results:
        return
    total = len(results)
    success = sum(1 for r in results.values() if isinstance(r, dict))

    console.print()
    stats = Text()
    stats.append(f"  ✅ {success}/{total} 任务成功", style="bold green")
    stats.append(f"  ⏱  耗时 {elapsed:.1f}s", style="dim")
    console.print(stats)


async def run_scenario(agent, scenario_num, title, user_input, quick=False):
    """运行一个完整演示场景"""
    print_scenario_header(scenario_num, title)
    print_user_input(user_input)

    # 1. 规划（带动画）
    console.print(f"  [cyan]⏳ 正在规划...[/]")
    t0 = time.time()
    plan = await run_with_spinner(
        agent.run(user_input),
        "正在解析意图、规划路线、生成任务..."
    )
    t_plan = time.time() - t0

    if plan.get("status") != "waiting_confirmation":
        console.print(f"  [red]❌ 规划失败: {plan.get('status')}[/]")
        return

    console.print(f"  [dim]规划完成 ({t_plan:.1f}s)[/]")
    console.print()

    # 展示方案
    print_plan_summary(plan.get("plan_summary", ""))
    print_route(plan.get("route"))
    print_story(plan.get("story"))
    print_tasks_preview(plan.get("tasks_preview", []))

    session_id = plan.get("session_id")

    if quick:
        console.print()
        console.print(f"  [dim]⚡ 快速模式：跳过执行步骤[/]")
        return plan

    # 2. 确认执行
    console.print()
    console.print(f"  [green bold]👤 用户：[/]确认，执行吧！")
    console.print(f"  [cyan]⚡ 正在执行...[/]")

    t0 = time.time()
    result = await run_with_spinner(
        agent.confirm_and_execute(session_id, confirmed=True),
        "正在执行预订、排队、配送等操作..."
    )
    t_exec = time.time() - t0

    # 3. 展示结果
    console.print(f"  [dim]执行完成 ({t_exec:.1f}s)[/]")

    status = result.get("status", "unknown")
    if status == "success":
        console.print()
        console.print(f"  [green bold]✅ 全部执行成功！[/]")

    print_execution_results(result.get("results", {}))
    print_share_text(result.get("share_text"))
    print_scenario_stats(result.get("results", {}), t_exec)

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
    parser.add_argument("--mock", action="store_true",
                        help="强制使用 Mock 模式（不调用真实 LLM）")
    parser.add_argument("--live", action="store_true",
                        help="强制使用真实 LLM（需要配置 API Key）")
    parser.add_argument("--timeout", type=float, default=15.0,
                        help="LLM 超时时间（秒），默认 15")
    args = parser.parse_args()

    # 设置环境变量
    if args.mock:
        import os
        os.environ["LLM_MODE"] = "mock"
    elif args.live:
        import os
        os.environ["LLM_MODE"] = "live"

    print_banner()

    # 初始化
    console.print(f"  [cyan]正在初始化 Agent...[/]")
    agent = create_agent(live=args.live)
    llm_config = agent.llm_client.config
    llm_config.timeout = args.timeout
    has_key = bool(llm_config.api_key)
    mode = f"{llm_config.provider}/{llm_config.model}" if has_key else "Mock（离线模式）"

    init_info = Text()
    init_info.append("  ✓ Agent 就绪", style="green bold")
    init_info.append(f"  [LLM: {mode}]", style="dim")
    if args.quick:
        init_info.append("  ⚡ 快速模式", style="yellow")
    if args.mock:
        init_info.append("  🧪 Mock 强制", style="yellow")
    console.print(init_info)
    console.print()

    # 选择要运行的场景
    if args.scenario:
        scenarios = [SCENARIOS[args.scenario - 1]]
    else:
        scenarios = SCENARIOS

    for num, title, user_input in scenarios:
        await run_scenario(agent, num, title, user_input, quick=args.quick)

    # 结束
    console.print()
    console.print(Panel(
        Text("演示完成！感谢观看", style="bold green", justify="center"),
        border_style="bright_blue",
        width=72,
    ))
    console.print()


if __name__ == "__main__":
    asyncio.run(main())
