"""
Playwright E2E 测试配置
提供 browser、page、mobile_page 等 fixture
"""

import os
import pytest
from playwright.sync_api import sync_playwright, Browser, Page

# 测试服务器地址
BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8080")


@pytest.fixture(scope="session")
def browser():
    """Session 级别的浏览器实例"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        yield browser
        browser.close()


@pytest.fixture
def page(browser: Browser):
    """PC 端页面（1280x720）"""
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()
    page.goto(BASE_URL)
    yield page
    context.close()


@pytest.fixture
def mobile_page(browser: Browser):
    """手机端页面（375x812，iPhone 13 尺寸）"""
    context = browser.new_context(
        viewport={"width": 375, "height": 812},
        is_mobile=True,
        has_touch=True,
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
    )
    page = context.new_page()
    page.goto(BASE_URL)
    yield page
    context.close()


@pytest.fixture(autouse=True)
def screenshot_on_failure(request, page):
    """测试失败时自动保存截图"""
    yield
    if request.node.rep_call and request.node.rep_call.failed:
        screenshot_dir = os.path.join(os.path.dirname(__file__), "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        screenshot_path = os.path.join(screenshot_dir, f"{request.node.name}.png")
        page.screenshot(path=screenshot_path)
        print(f"\n截图已保存: {screenshot_path}")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """为 screenshot_on_failure fixture 提供测试结果"""
    import pluggy
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
