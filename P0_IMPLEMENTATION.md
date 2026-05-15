# P0 实施计划 - 竞赛提交前必须完成

## 任务 1: 集成真实 LLM API

### 步骤

#### 1.1 获取 API Key

**Claude API (推荐)**：
1. 访问 https://console.anthropic.com
2. 注册/登录账号
3. 创建 API Key

**OpenAI API**：
1. 访问 https://platform.openai.com
2. 注册/登录账号
3. 创建 API Key

**国产替代 (如果无法访问国外)**：
- 通义千问：https://dashscope.aliyun.com
- 文心一言：https://cloud.baidu.com
- 智谱 AI：https://open.bigmodel.cn

#### 1.2 配置环境变量

```bash
# Windows PowerShell
$env:LLM_API_KEY="your-api-key"
$env:LLM_PROVIDER="claude"
$env:LLM_MODEL="claude-sonnet-4-20250514"

# 或创建 .env 文件
echo "LLM_API_KEY=your-api-key" > .env
echo "LLM_PROVIDER=claude" >> .env
```

#### 1.3 修改代码支持环境变量

**文件**: `agent/main.py`

```python
import os

def create_agent(
    llm_provider: str = None,
    api_key: str = None,
    model: str = None,
) -> Planner:
    # 从环境变量读取配置
    llm_provider = llm_provider or os.environ.get("LLM_PROVIDER", "mock")
    api_key = api_key or os.environ.get("LLM_API_KEY", "")
    model = model or os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514")
    
    # ... 其余代码
```

#### 1.4 测试 LLM 集成

```bash
# 运行测试
python -c "
from agent.main import create_agent
import asyncio

agent = create_agent()
result = asyncio.run(agent.run('带老婆孩子出去玩，孩子5岁'))
print(result)
"
```

### 预期结果
- 意图识别更准确
- 支持复杂表达（如"老婆最近心情不好，想给她惊喜"）
- 支持多轮对话上下文

---

## 任务 2: 完善 Demo 场景演示

### 2.1 优化 Demo 脚本

**文件**: `run_demo.py`

```python
async def demo_scenario_1():
    """场景一：家庭出游（正常流程）"""
    print("\n" + "="*60)
    print("场景一：家庭周末出游")
    print("="*60)
    
    user_input = "这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜"
    
    print(f"\n用户输入: {user_input}")
    print("\nAgent 思考过程:")
    print("  1. 识别人员: 老婆、5岁孩子、自己")
    print("  2. 识别需求: 娱乐、餐饮、惊喜")
    print("  3. 识别约束: 适合儿童、低卡饮食")
    print("\n执行任务:")
    
    result = await agent.run(user_input)
    
    # 格式化输出
    print("\n" + "-"*40)
    print("执行结果:")
    print("-"*40)
    
    for task_id, task_result in result.get("results", {}).items():
        print(f"\n[{task_id}] {get_task_name(task_id)}")
        if isinstance(task_result, dict):
            for key, value in task_result.items():
                if key != "results":
                    print(f"  - {key}: {value}")
```

### 2.2 补充 Mock 数据

**文件**: `agent/tools/search_poi.py`

```python
MOCK_DATA = {
    "儿童乐园": [
        {
            "id": "kids_001",
            "name": "奇乐儿儿童主题乐园",
            "rating": 4.8,
            "address": "万达广场3楼",
            "distance": 120,
            "price": "88-168元",
            "features": ["室内", "适合3-8岁", "有家长休息区"],
            "queue_count": 5
        },
        # ... 更多数据
    ],
    # ... 更多类别
}
```

### 2.3 添加演示脚本

**文件**: `demo_showcase.py`

```python
"""
竞赛演示脚本
自动运行 3 个场景，展示核心能力
"""

async def showcase():
    print("\n" + "="*70)
    print("   美团 AI Agent 跨业务智能规划系统 - 竞赛演示")
    print("="*70)
    
    # 场景一：正常流程
    await demo_scenario_1()
    
    # 场景二：异常处理 (Fallback)
    await demo_scenario_2_fallback()
    
    # 场景三：重新规划 (Replan)
    await demo_scenario_3_replan()
    
    print("\n" + "="*70)
    print("   演示完成！感谢观看！")
    print("="*70)
```

---

## 任务 3: 小程序界面美化

### 3.1 全局样式优化

**文件**: `miniprogram/app.wxss`

```css
/* 美团品牌色 */
:root {
  --primary-color: #FFD100;
  --primary-dark: #F5C000;
  --text-primary: #1A1A1A;
  --text-secondary: #666666;
  --bg-primary: #F5F5F5;
  --bg-card: #FFFFFF;
}

/* 全局按钮 */
.btn-primary {
  background: linear-gradient(135deg, #FFD100 0%, #FFC000 100%);
  color: #1A1A1A;
  border-radius: 48rpx;
  font-weight: 600;
  box-shadow: 0 4rpx 16rpx rgba(255, 209, 0, 0.3);
}

/* 卡片样式 */
.card {
  background: var(--bg-card);
  border-radius: 24rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.05);
}
```

### 3.2 首页优化

**文件**: `miniprogram/pages/index/index.wxml`

```html
<!-- 欢迎区域 -->
<view class="welcome-section">
  <view class="welcome-bg"></view>
  <view class="welcome-content">
    <text class="greeting">你好，我是美团 AI 助手</text>
    <text class="subtitle">告诉我你的需求，我来帮你规划行程</text>
  </view>
</view>

<!-- 快捷入口 -->
<view class="quick-entry">
  <view class="section-title">快捷场景</view>
  <view class="entry-grid">
    <view class="entry-item" wx:for="{{quickEntries}}" wx:key="title">
      <view class="entry-icon-wrapper">
        <image class="entry-icon" src="{{item.icon}}"></image>
      </view>
      <text class="entry-title">{{item.title}}</text>
      <text class="entry-desc">{{item.desc}}</text>
    </view>
  </view>
</view>
```

### 3.3 添加图标资源

创建 `miniprogram/images/` 目录，添加图标：
- home.png / home-active.png
- chat.png / chat-active.png
- send.png
- loading.png

### 3.4 对话页面优化

**文件**: `miniprogram/pages/chat/chat.wxml`

```html
<!-- 消息气泡优化 -->
<view class="message {{item.role}}">
  <view class="message-avatar">
    <image wx:if="{{item.role === 'user'}}" src="/images/user-avatar.png"/>
    <image wx:else src="/images/ai-avatar.png"/>
  </view>
  <view class="message-bubble">
    <text class="message-text">{{item.content}}</text>
    <text class="message-time">{{item.time}}</text>
  </view>
</view>
```

---

## 任务 4: 演示 PPT 准备

### 4.1 PPT 结构

```
1. 封面
   - 项目名称
   - 团队信息
   - 日期

2. 问题与背景 (1页)
   - 美团业务现状
   - 用户痛点
   - 机会点

3. 解决方案 (1页)
   - AI Agent 架构
   - 核心创新点
   - 技术选型

4. 系统架构 (1页)
   - 整体架构图
   - 模块划分
   - 数据流

5. 核心功能演示 (3页)
   - 场景一：正常流程
   - 场景二：异常处理
   - 场景三：重新规划

6. 商业价值 (1页)
   - 交叉销售
   - 用户体验提升
   - 预期收益

7. 技术亮点 (1页)
   - ReAct 架构
   - 三层异常处理
   - 跨业务编排

8. 未来规划 (1页)
   - 功能扩展
   - 场景拓展
   - 技术演进

9. Q&A
```

### 4.2 关键数据准备

```python
# 预期提升数据
metrics = {
    "跨业务转化率": {"当前": "15%", "预期": "35%", "提升": "+133%"},
    "客单价": {"当前": "¥180", "预期": "¥280", "提升": "+56%"},
    "用户满意度": {"当前": "4.2", "预期": "4.7", "提升": "+12%"},
    "规划时间": {"当前": "30分钟", "预期": "1分钟", "提升": "-97%"},
}
```

---

## 验收清单

### P0 完成标准

- [ ] LLM API 集成成功，意图识别准确
- [ ] 3 个 Demo 场景运行流畅
- [ ] 小程序界面美观，交互流畅
- [ ] 演示 PPT 完成
- [ ] 核心功能无 Bug

### 测试用例

```bash
# 1. 测试 LLM 集成
python -c "from agent.main import create_agent; agent = create_agent(); print('LLM OK')"

# 2. 测试正常流程
python run_demo.py

# 3. 测试异常场景
python tests/test_exception_scenarios.py

# 4. 测试 API
curl http://localhost:8080/api/agent/health

# 5. 测试小程序
# 使用微信开发者工具打开 miniprogram 目录
```

---

## 时间安排

| 任务 | 时间 | 负责 |
|------|------|------|
| LLM API 集成 | 2小时 | 开发者 |
| Demo 场景完善 | 2小时 | 开发者 |
| 小程序美化 | 3小时 | 开发者 |
| 演示 PPT | 2小时 | 开发者 |
| 测试验收 | 1小时 | 开发者 |
| **总计** | **10小时** | - |

---

## 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| LLM API 不可用 | 无法展示真实效果 | 使用 Mock 模式 + 视频演示 |
| 网络问题 | API 调用失败 | 准备离线 Demo |
| 时间不足 | 功能不完整 | 优先核心场景 |
