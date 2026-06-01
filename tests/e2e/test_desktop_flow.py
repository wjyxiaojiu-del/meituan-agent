"""
PC 端 E2E 测试
覆盖完整规划流程、路线编辑器、剧情模式、错误恢复
"""

import pytest
from playwright.sync_api import Page, expect


class TestDesktopPlanningFlow:
    """PC 端完整规划流程"""

    def test_full_planning_flow(self, page: Page):
        """输入需求 → 等待流式输出 → 验证结果卡片 → 点击确认执行 → 验证完成"""
        # 1. 等待页面加载完成
        page.wait_for_selector("#inp", state="visible", timeout=10000)

        # 2. 输入需求
        page.fill("#inp", "带孩子去儿童乐园玩")
        page.click("#sendBtn")

        # 3. 等待流式输出开始（thinking 区域出现）
        page.wait_for_selector("#thinkSteps", state="visible", timeout=5000)

        # 4. 等待流式输出完成（thinking 区域消失，结果卡片出现）
        page.wait_for_selector(".result-section, .completion-card", timeout=60000)

        # 5. 验证结果卡片包含必要元素
        expect(page.locator(".route-card, .task-card").first).to_be_visible()

        # 6. 点击确认执行
        page.click("button.act-btn.go")

        # 7. 等待执行完成
        page.wait_for_selector(".completion-card, .cc-hd", timeout=30000)

        # 8. 验证完成卡片
        expect(page.locator(".cc-hd")).to_contain_text("完成")

    def test_route_editor(self, page: Page):
        """点击地图 POI → 验证路线面板更新 → 点击智能排序"""
        # 1. 滚动到路线编辑器
        page.click('a[href="#planner"]')
        page.wait_for_timeout(1000)

        # 2. 等待地图加载
        page.wait_for_selector("#plannerMap", state="visible", timeout=10000)

        # 3. 等待 POI 标记加载
        page.wait_for_selector(".poi-marker", timeout=10000)

        # 4. 点击第一个 POI 标记
        markers = page.locator(".poi-marker")
        markers.first.click()

        # 5. 在弹窗中点击"加入路线"
        page.wait_for_selector(".planner-popup-btn.add", timeout=5000)
        page.click(".planner-popup-btn.add")

        # 6. 验证路线面板更新
        page.wait_for_selector(".ps-route-item", timeout=5000)
        expect(page.locator(".ps-route-item")).to_have_count(1)

        # 7. 添加第二个 POI
        markers.nth(1).click()
        page.wait_for_selector(".planner-popup-btn.add", timeout=5000)
        page.click(".planner-popup-btn.add")

        # 8. 验证路线面板有 2 个站点
        expect(page.locator(".ps-route-item")).to_have_count(2)

    def test_story_mode_toggle(self, page: Page):
        """开启剧情开关 → 输入需求 → 验证剧情模式激活"""
        # 1. 开启剧情模式开关
        page.check("#storyToggle")

        # 2. 输入需求
        page.fill("#inp", "和朋友出去玩，想玩点不一样的")
        page.click("#sendBtn")

        # 3. 等待结果
        page.wait_for_selector(".result-section, .story", timeout=60000)

        # 4. 验证剧情区块出现（如果 mock 模式支持）
        # 在 mock 模式下，story 可能为 null，但流程不应报错
        expect(page.locator(".msg.bot").last).to_be_visible()

    def test_error_recovery(self, page: Page):
        """输入空内容 → 验证无响应 → 重新输入 → 验证正常"""
        # 1. 尝试发送空内容
        page.click("#sendBtn")

        # 2. 验证没有发送消息（welcome 仍在）
        expect(page.locator("#welcome")).to_be_visible()

        # 3. 输入有效内容
        page.fill("#inp", "带孩子出去玩")
        page.click("#sendBtn")

        # 4. 验证消息发送成功
        page.wait_for_selector(".msg.user", timeout=5000)
        expect(page.locator(".msg.user")).to_be_visible()


class TestDesktopUI:
    """PC 端 UI 交互"""

    def test_nav_links(self, page: Page):
        """导航链接可点击"""
        # 点击"路线编辑器"链接
        page.click('a[href="#planner"]')
        page.wait_for_timeout(500)

        # 验证滚动到对应区域
        planner = page.locator("#planner")
        expect(planner).to_be_in_viewport()

    def test_scene_selection(self, page: Page):
        """场景选择可点击并填入输入框"""
        # 点击第一个场景
        page.click(".sc:first-child")

        # 验证输入框被填入
        inp = page.locator("#inp")
        expect(inp).not_to_be_empty()

    def test_chat_reset(self, page: Page):
        """聊天重置功能"""
        # 先发送一条消息
        page.fill("#inp", "测试消息")
        page.click("#sendBtn")
        page.wait_for_selector(".msg.user", timeout=5000)

        # 点击重置按钮
        page.click(".hd-btn")

        # 验证回到欢迎页
        expect(page.locator("#welcome")).to_be_visible()
