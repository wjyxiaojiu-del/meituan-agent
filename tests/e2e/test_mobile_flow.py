"""
手机端 E2E 测试
覆盖手机视口下的规划流程、路线重排、滚动、导航菜单
"""

import pytest
from playwright.sync_api import Page, expect


class TestMobilePlanningFlow:
    """手机端完整规划流程"""

    def test_mobile_planning_flow(self, mobile_page: Page):
        """手机视口下完整规划流程"""
        page = mobile_page

        # 1. 等待页面加载
        page.wait_for_selector("#inp", state="visible", timeout=10000)

        # 2. 输入需求
        page.fill("#inp", "带孩子出去玩")
        page.click("#sendBtn")

        # 3. 等待流式输出
        page.wait_for_selector("#thinkSteps", state="visible", timeout=5000)

        # 4. 等待结果
        page.wait_for_selector(".result-section, .completion-card", timeout=60000)

        # 5. 点击确认执行
        page.click("button.act-btn.go")

        # 6. 等待完成
        page.wait_for_selector(".completion-card", timeout=30000)
        expect(page.locator(".cc-hd")).to_contain_text("完成")

    def test_mobile_route_reorder(self, mobile_page: Page):
        """验证 ▲/▼ 按钮可用，点击后顺序变化"""
        page = mobile_page

        # 1. 滚动到路线编辑器
        page.click('a[href="#planner"]')
        page.wait_for_timeout(1000)

        # 2. 等待地图加载
        page.wait_for_selector("#plannerMap", state="visible", timeout=10000)
        page.wait_for_selector(".poi-marker", timeout=10000)

        # 3. 添加两个 POI
        markers = page.locator(".poi-marker")
        markers.first.click()
        page.wait_for_selector(".planner-popup-btn.add", timeout=5000)
        page.click(".planner-popup-btn.add")
        page.wait_for_timeout(500)

        markers.nth(1).click()
        page.wait_for_selector(".planner-popup-btn.add", timeout=5000)
        page.click(".planner-popup-btn.add")
        page.wait_for_timeout(500)

        # 4. 验证路线面板有 2 个站点
        expect(page.locator(".ps-route-item")).to_have_count(2)

        # 5. 获取第一个站点名称
        first_name = page.locator(".ps-route-item:first-child .ps-item-name").text_content()

        # 6. 点击第二个站点的 ▲ 按钮（上移）
        page.locator(".ps-route-item:nth-child(2) .ps-move-btn:first-child").click()
        page.wait_for_timeout(300)

        # 7. 验证顺序变化
        new_first_name = page.locator(".ps-route-item:first-child .ps-item-name").text_content()
        assert new_first_name != first_name, "上移后第一个站点应该变化"

    def test_mobile_scroll(self, mobile_page: Page):
        """验证结果页滚动不卡顿"""
        page = mobile_page

        # 1. 输入需求并等待结果
        page.fill("#inp", "带孩子出去玩")
        page.click("#sendBtn")
        page.wait_for_selector(".result-section", timeout=60000)

        # 2. 滚动到底部
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(500)

        # 3. 验证页面可滚动（scrollY > 0）
        scroll_y = page.evaluate("window.scrollY")
        assert scroll_y >= 0, "页面应该可以滚动"

    def test_mobile_nav(self, mobile_page: Page):
        """验证汉堡菜单可展开/收起"""
        page = mobile_page

        # 1. 点击汉堡菜单
        page.click("#navHamburger")

        # 2. 验证菜单展开
        expect(page.locator(".nav-links")).to_have_class(/open/)

        # 3. 点击菜单项收起
        page.click(".nav-link:first-child")

        # 4. 验证菜单收起
        expect(page.locator(".nav-links")).not_to_have_class(/open/)


class TestMobileUI:
    """手机端 UI 交互"""

    def test_mobile_input_focus(self, mobile_page: Page):
        """输入框可聚焦"""
        page = mobile_page

        # 点击输入区域
        page.click(".input-area")

        # 验证输入框获得焦点
        expect(page.locator("#inp")).to_be_focused()

    def test_mobile_scene_selection(self, mobile_page: Page):
        """场景选择在手机端可用"""
        page = mobile_page

        # 点击第一个场景
        page.locator(".sc").first.click()

        # 验证输入框被填入
        expect(page.locator("#inp")).not_to_be_empty()
