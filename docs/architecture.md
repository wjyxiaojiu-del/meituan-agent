# 系统架构设计文档

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    微信小程序 (前端展示)                      │
│   - 行程卡片展示   - 实时状态更新   - 确认交互界面            │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP/WebSocket
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Java Spring Boot (后端服务层)                    │
│   - API 网关        - 用户会话管理    - 订单状态同步          │
│   - 消息推送服务    - 数据持久化       - 缓存管理             │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST API / gRPC
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Python Agent (智能体核心层)                      │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Planning    │  │ Tool        │  │ State       │         │
│  │ Engine      │  │ Orchestrator│  │ Machine     │         │
│  │ (规划引擎)  │  │ (工具编排)  │  │ (状态机)    │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                  │
│         └────────────────┼────────────────┘                  │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Exception Handler (异常处理器)           │    │
│  │   - Self-Correction  - Fallback  - Retry             │    │
│  └─────────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Mock API Layer (模拟接口层)                │
│   - Search_POI      - Check_Queue    - Book_Restaurant       │
│   - Order_Delivery  - Weather_API    - Traffic_API           │
└─────────────────────────────────────────────────────────────┘
```

## 二、核心模块设计

### 2.1 Planning Engine (规划引擎)

采用 **ReAct (Reasoning + Acting)** 架构：

```python
# 核心流程
User Input → Intent Recognition → Task Decomposition → Tool Selection → Execution → Response

# 具体步骤
1. 解析用户意图（带娃、减肥、惊喜）
2. 拆解子任务（按时间线 + 按人员需求）
3. 生成执行计划（带优先级和依赖关系）
4. 逐步调用工具执行
5. 动态调整计划（遇到异常时）
```

### 2.2 State Machine (状态机)

```
                    ┌──────────────┐
                    │   PLANNING   │ ← 初始状态
                    └──────┬───────┘
                           │ 计划生成完成
                           ▼
                    ┌──────────────┐
            ┌────── │   EXECUTING  │ ← 执行中
            │       └──────┬───────┘
            │              │ 遇到异常
            │              ▼
            │       ┌──────────────┐
            │       │   ERROR      │ ← 错误处理
            │       └──────┬───────┘
            │              │ 重试/回退成功
            │              ▼
            └──────→ ┌──────────────┐
                     │   COMPLETED  │ ← 完成
                     └──────────────┘
```

**状态转换规则：**
- PLANNING → EXECUTING: 所有子任务规划完成
- EXECUTING → ERROR: 工具调用失败
- ERROR → EXECUTING: 重试成功或回退到备选方案
- ERROR → PLANNING: 需要重新规划（严重异常）
- EXECUTING → COMPLETED: 所有任务执行成功

### 2.3 Exception Handler (异常处理器)

**三层异常处理机制：**

| 层级 | 策略 | 示例 |
|------|------|------|
| L1 Retry | 自动重试（指数退避） | 网络超时、API限流 |
| L2 Fallback | 自动切换备选方案 | 餐厅满座→推荐相似餐厅 |
| L3 Replan | 重新规划 | 天气突变→室内替代方案 |

## 三、工具调用链设计

### 场景：小明的周末家庭日

```
用户输入: "这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜"

Step 1: Intent Recognition
├── 识别人员: 小明、老婆、5岁孩子
├── 识别需求: 娱乐、餐饮、惊喜元素
└── 识别约束: 适合儿童、低卡饮食

Step 2: Task Decomposition (按时间线)
├── T1 [14:00-16:30] 儿童游乐场
│   └── Tool: Search_POI(category="儿童乐园", location="商场", age_range="3-6")
├── T2 [17:00-18:30] 晚餐
│   └── Tool: Search_POI(category="餐厅", feature="低卡", nearby=T1.location)
├── T3 [17:00] 预订餐厅
│   └── Tool: Book_Restaurant(restaurant_id, time="17:00", party_size=3)
├── T4 [17:00] 云排队
│   └── Tool: Check_Queue_Status(restaurant_id) → 自动取号
├── T5 [17:30] 惊喜配送
│   └── Tool: Order_Delivery(item="鲜花", deliver_to=T2.location, time="17:30")
└── T6 [随时] 天气监控
    └── Tool: Weather_API(date="周六") → 异常时触发 Replan

Step 3: Execution with Monitoring
└── 每个 Tool 执行后更新状态，异常时触发 Exception Handler
```

## 四、异常处理演示场景

### 场景 A：餐厅满座

```
触发: Book_Restaurant 返回 "座位已满"
处理:
  1. 捕获异常，标记当前任务为 FAILED
  2. 调用 Search_POI 查找备选餐厅（距离<500m，评分>4.5，有低卡选项）
  3. 向用户推送通知: "XX餐厅已满座，为您推荐YY餐厅，距离200米，评分4.7，已为您自动预订"
  4. 更新状态机为 EXECUTING，继续后续任务
```

### 场景 B：天气突变

```
触发: Weather_API 返回 "14:00-16:00 有雨"
处理:
  1. 识别受影响任务: T1 (儿童乐园，原计划室外区域)
  2. 检查是否有室内替代: 室内游乐区 → 有，继续
  3. 若无室内替代: Search_POI(category="室内儿童乐园") → 替换 T1
  4. 自动调整后续任务时间（可能延迟30分钟）
  5. 向用户推送: "检测到下午有雨，已将游乐场调整为室内区域"
```

### 场景 C：配送延迟

```
触发: Order_Delivery 返回 "预计延迟30分钟"
处理:
  1. 计算新配送时间: 17:30 → 18:00
  2. 检查是否影响主流程: 餐厅预订17:00，用餐约1.5小时，18:00仍在用餐 → OK
  3. 更新配送时间，向用户推送: "鲜花将在18:00送达，届时您仍在用餐，完美惊喜"
```

## 五、技术选型

### Python Agent 层

```python
# requirements.txt
anthropic>=0.18.0          # Claude API
langchain>=0.1.0           # Agent 框架（可选）
pydantic>=2.0              # 数据模型验证
fastapi>=0.100.0           # 内部 API 服务
redis>=5.0                 # 状态缓存
```

### Java 后端层

```xml
<!-- pom.xml 核心依赖 -->
<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-websocket</artifactId>
    </dependency>
    <dependency>
        <groupId>com.alibaba</groupId>
        <artifactId>fastjson</artifactId>
        <version>2.0.x</version>
    </dependency>
</dependencies>
```

### 小程序前端

```json
{
  "dependencies": {
    "weui-miniprogram": "^1.0.0",
    "wx-promise-pro": "^3.0.0"
  }
}
```

## 六、目录结构详细设计

```
meituan-agent/
├── agent/
│   ├── __init__.py
│   ├── main.py                    # Agent 入口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── planner.py             # ReAct 规划引擎
│   │   ├── state_machine.py       # 状态机管理
│   │   └── exception_handler.py   # 异常处理器
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py                # 工具基类
│   │   ├── search_poi.py          # 搜索兴趣点
│   │   ├── book_restaurant.py     # 餐厅预订
│   │   ├── check_queue.py         # 排队查询
│   │   ├── order_delivery.py      # 即时配送
│   │   ├── weather_api.py         # 天气查询
│   │   └── traffic_api.py         # 交通查询
│   ├── prompts/
│   │   ├── system_prompt.txt      # 系统提示词
│   │   ├── planning_prompt.txt    # 规划提示词
│   │   └── error_prompt.txt       # 错误处理提示词
│   └── utils/
│       ├── __init__.py
│       ├── logger.py              # 日志工具
│       └── config.py              # 配置管理
├── backend/
│   ├── src/main/java/com/meituan/agent/
│   │   ├── AgentApplication.java
│   │   ├── controller/
│   │   │   ├── AgentController.java      # Agent API
│   │   │   └── WebSocketController.java  # 实时通信
│   │   ├── service/
│   │   │   ├── SessionService.java       # 会话管理
│   │   │   └── OrderService.java         # 订单服务
│   │   └── model/
│   │       ├── Session.java
│   │       └── PlanResult.java
│   └── pom.xml
├── miniprogram/
│   ├── pages/
│   │   ├── index/                 # 首页
│   │   ├── chat/                  # 对话页
│   │   └── plan/                  # 行程卡片页
│   ├── components/
│   │   ├── plan-card/             # 行程卡片组件
│   │   └── status-badge/          # 状态标签组件
│   ├── app.js
│   ├── app.json
│   └── app.wxss
├── mock/
│   ├── api_server.py              # Mock API 服务器
│   └── data/
│       ├── restaurants.json       # 餐厅数据
│       ├── entertainment.json     # 娱乐场所数据
│       └── delivery.json          # 配送数据
├── docs/
│   ├── architecture.md            # 本文档
│   └── design_proposal.md         # 2页设计文档
└── tests/
    ├── test_planner.py
    ├── test_state_machine.py
    └── test_exception_handler.py
```
