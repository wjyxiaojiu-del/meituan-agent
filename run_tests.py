#!/usr/bin/env python3
"""
测试运行脚本
运行所有测试并生成报告
"""

import sys
import os
import asyncio
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))


def print_header(title):
    """打印标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_section(title):
    """打印章节"""
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def print_result(test_name, passed, error=None):
    """打印测试结果"""
    if passed:
        print(f"  ✅ {test_name}")
    else:
        print(f"  ❌ {test_name}")
        if error:
            print(f"     错误: {error}")


async def run_tools_tests():
    """运行工具测试"""
    print_section("工具模块测试")

    try:
        from tests.test_tools import (
            TestSearchPOITool,
            TestBookRestaurantTool,
            TestCheckQueueTool,
            TestOrderDeliveryTool,
            TestWeatherAPITool
        )

        passed = 0
        failed = 0

        # 测试 POI 搜索
        tool_tests = TestSearchPOITool()
        from agent.tools.search_poi import SearchPOITool
        tool = SearchPOITool()

        try:
            await tool_tests.test_search_kids_playground(tool)
            print_result("搜索儿童乐园", True)
            passed += 1
        except Exception as e:
            print_result("搜索儿童乐园", False, str(e))
            failed += 1

        try:
            await tool_tests.test_search_restaurant(tool)
            print_result("搜索餐厅", True)
            passed += 1
        except Exception as e:
            print_result("搜索餐厅", False, str(e))
            failed += 1

        # 测试餐厅预订
        booking_tests = TestBookRestaurantTool()
        from agent.tools.book_restaurant import BookRestaurantTool
        tool = BookRestaurantTool()

        try:
            await booking_tests.test_booking_success(tool)
            print_result("餐厅预订成功", True)
            passed += 1
        except Exception as e:
            print_result("餐厅预订成功", False, str(e))
            failed += 1

        try:
            await booking_tests.test_booking_full_restaurant(tool)
            print_result("餐厅满座检测", True)
            passed += 1
        except Exception as e:
            print_result("餐厅满座检测", False, str(e))
            failed += 1

        # 测试排队系统
        queue_tests = TestCheckQueueTool()
        from agent.tools.check_queue import CheckQueueTool
        tool = CheckQueueTool()

        try:
            await queue_tests.test_check_queue_status(tool)
            print_result("查询排队状态", True)
            passed += 1
        except Exception as e:
            print_result("查询排队状态", False, str(e))
            failed += 1

        try:
            await queue_tests.test_take_queue_number(tool)
            print_result("排队取号", True)
            passed += 1
        except Exception as e:
            print_result("排队取号", False, str(e))
            failed += 1

        # 测试即时配送
        delivery_tests = TestOrderDeliveryTool()
        from agent.tools.order_delivery import OrderDeliveryTool
        tool = OrderDeliveryTool()

        try:
            await delivery_tests.test_order_flowers(tool)
            print_result("鲜花配送", True)
            passed += 1
        except Exception as e:
            print_result("鲜花配送", False, str(e))
            failed += 1

        # 测试天气 API
        weather_tests = TestWeatherAPITool()
        from agent.tools.weather_api import WeatherAPITool
        tool = WeatherAPITool()

        try:
            await weather_tests.test_get_weather(tool)
            print_result("天气查询", True)
            passed += 1
        except Exception as e:
            print_result("天气查询", False, str(e))
            failed += 1

        try:
            await weather_tests.test_set_mock_weather_sunny(tool)
            print_result("设置晴天", True)
            passed += 1
        except Exception as e:
            print_result("设置晴天", False, str(e))
            failed += 1

        return passed, failed

    except Exception as e:
        print(f"  ❌ 工具测试加载失败: {e}")
        return 0, 1


async def run_integration_tests():
    """运行集成测试"""
    print_section("集成测试")

    try:
        from tests.test_integration import (
            TestCompleteFlow,
            TestEdgeCases,
            TestDataPersistence
        )

        from agent.main import create_agent
        agent = create_agent(llm_provider="mock")

        passed = 0
        failed = 0

        # 测试完整流程
        flow_tests = TestCompleteFlow()

        try:
            await flow_tests.test_family_outing(agent)
            print_result("家庭出游流程", True)
            passed += 1
        except Exception as e:
            print_result("家庭出游流程", False, str(e))
            failed += 1

        try:
            await flow_tests.test_couple_date(agent)
            print_result("情侣约会流程", True)
            passed += 1
        except Exception as e:
            print_result("情侣约会流程", False, str(e))
            failed += 1

        try:
            await flow_tests.test_friends_gathering(agent)
            print_result("朋友聚会流程", True)
            passed += 1
        except Exception as e:
            print_result("朋友聚会流程", False, str(e))
            failed += 1

        # 测试边界情况
        edge_tests = TestEdgeCases()

        try:
            await edge_tests.test_minimal_input(agent)
            print_result("最小输入", True)
            passed += 1
        except Exception as e:
            print_result("最小输入", False, str(e))
            failed += 1

        try:
            await edge_tests.test_complex_input(agent)
            print_result("复杂输入", True)
            passed += 1
        except Exception as e:
            print_result("复杂输入", False, str(e))
            failed += 1

        # 测试数据持久性
        data_tests = TestDataPersistence()

        try:
            await data_tests.test_results_structure(agent)
            print_result("结果结构", True)
            passed += 1
        except Exception as e:
            print_result("结果结构", False, str(e))
            failed += 1

        try:
            await data_tests.test_booking_id_format(agent)
            print_result("预订号格式", True)
            passed += 1
        except Exception as e:
            print_result("预订号格式", False, str(e))
            failed += 1

        return passed, failed

    except Exception as e:
        print(f"  ❌ 集成测试加载失败: {e}")
        return 0, 1


async def run_exception_tests():
    """运行异常测试"""
    print_section("异常场景测试")

    try:
        from tests.test_exception_scenarios import (
            TestFallbackScenario,
            TestReplanScenario,
            TestRetryScenario
        )

        from agent.main import create_agent
        agent = create_agent(llm_provider="mock")

        passed = 0
        failed = 0

        # 测试 Fallback
        fallback_tests = TestFallbackScenario()

        try:
            await fallback_tests.test_restaurant_full_fallback(agent)
            print_result("餐厅满座 Fallback", True)
            passed += 1
        except Exception as e:
            print_result("餐厅满座 Fallback", False, str(e))
            failed += 1

        try:
            await fallback_tests.test_fallback_mechanism(agent)
            print_result("Fallback 机制", True)
            passed += 1
        except Exception as e:
            print_result("Fallback 机制", False, str(e))
            failed += 1

        # 测试 Replan
        replan_tests = TestReplanScenario()

        try:
            await replan_tests.test_weather_change_detection(agent)
            print_result("天气变化检测", True)
            passed += 1
        except Exception as e:
            print_result("天气变化检测", False, str(e))
            failed += 1

        try:
            await replan_tests.test_replan_trigger(agent)
            print_result("Replan 触发", True)
            passed += 1
        except Exception as e:
            print_result("Replan 触发", False, str(e))
            failed += 1

        # 测试 Retry
        retry_tests = TestRetryScenario()

        try:
            await retry_tests.test_retry_mechanism(agent)
            print_result("重试机制", True)
            passed += 1
        except Exception as e:
            print_result("重试机制", False, str(e))
            failed += 1

        return passed, failed

    except Exception as e:
        print(f"  ❌ 异常测试加载失败: {e}")
        return 0, 1


async def run_llm_tests():
    """运行 LLM 测试"""
    print_section("LLM 集成测试")

    try:
        from tests.test_llm_integration import (
            TestLLMClientInit,
            TestLLMMockResponse,
            TestLLMIntentPrompts
        )

        passed = 0
        failed = 0

        # 测试客户端初始化
        init_tests = TestLLMClientInit()

        try:
            init_tests.test_mock_mode()
            print_result("Mock 模式初始化", True)
            passed += 1
        except Exception as e:
            print_result("Mock 模式初始化", False, str(e))
            failed += 1

        try:
            init_tests.test_deepseek_config()
            print_result("DeepSeek 配置", True)
            passed += 1
        except Exception as e:
            print_result("DeepSeek 配置", False, str(e))
            failed += 1

        # 测试 Mock 响应
        mock_tests = TestLLMMockResponse()
        from agent.llm.client import LLMClient
        client = LLMClient()

        try:
            await mock_tests.test_mock_response_family(client)
            print_result("家庭场景 Mock", True)
            passed += 1
        except Exception as e:
            print_result("家庭场景 Mock", False, str(e))
            failed += 1

        try:
            await mock_tests.test_mock_json_response(client)
            print_result("JSON 响应", True)
            passed += 1
        except Exception as e:
            print_result("JSON 响应", False, str(e))
            failed += 1

        # 测试提示词
        prompt_tests = TestLLMIntentPrompts()

        try:
            prompt_tests.test_intent_prompt_structure()
            print_result("意图提示词结构", True)
            passed += 1
        except Exception as e:
            print_result("意图提示词结构", False, str(e))
            failed += 1

        return passed, failed

    except Exception as e:
        print(f"  ❌ LLM 测试加载失败: {e}")
        return 0, 1


async def main():
    """主函数"""
    print_header("美团 AI Agent 测试套件")

    start_time = time.time()

    total_passed = 0
    total_failed = 0

    # 运行工具测试
    passed, failed = await run_tools_tests()
    total_passed += passed
    total_failed += failed

    # 运行集成测试
    passed, failed = await run_integration_tests()
    total_passed += passed
    total_failed += failed

    # 运行异常测试
    passed, failed = await run_exception_tests()
    total_passed += passed
    total_failed += failed

    # 运行 LLM 测试
    passed, failed = await run_llm_tests()
    total_passed += passed
    total_failed += failed

    # 计算耗时
    elapsed = time.time() - start_time

    # 打印总结
    print_header("测试总结")
    print(f"\n  总测试数: {total_passed + total_failed}")
    print(f"  ✅ 通过: {total_passed}")
    print(f"  ❌ 失败: {total_failed}")
    print(f"  ⏱️  耗时: {elapsed:.2f} 秒")

    if total_failed == 0:
        print(f"\n  🎉 所有测试通过！")
    else:
        print(f"\n  ⚠️  有 {total_failed} 个测试失败")

    return total_failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
