# 系统架构设计文档

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    前端展示层                                 │
│   ┌──────────────────┐  ┌──────────────────┐               │
│   │  Web SPA (静态)   │  │  微信小程序       │               │
│   │  HTML + CSS + JS  │  │  原生小程序       │               │
│   └────────┬─────────┘  └────────┬─────────┘               │
└────────────┼─────────────────────┼──────────────────────────┘
             │ HTTP                │ HTTP
             ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI 后端服务 (agent/api.py)                  │
│   - REST API 网关     - 静态文件服务    - CORS               │
│   - 会话管理（SQLite） - Unicode 清理                        │
└───────────────────────────┬─────────────────────────────────┘
                            │ 内部调用
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Python Agent 智能体核心层                        │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Planning    │  │ Route       │  │ Story       │         │
│  │ Engine      │  │ Planner     │  │ Engine      │         │
│  │ (规划引擎)  │  │ (路线规划)  │  │ (剧情引擎)  │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                  │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐         │
│  │ State       │  │ Exception   │  │ Scene       │         │
│  │ Machine     │  │ Handler     │  │ Manager     │         │
│  │ (状态机)    │  │ (异常处理)  │  │ (场景识别)  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Mock API Layer (模拟接口层)                │
│   - Search_POI      - Check_Queue    - Book_Restaurant       │
│   - Order_Delivery  - Weather_API    - Book_Venue            │
└─────────────────────────────────────────────────────────────┘
```

## 二、核心模块设计

### 2.1 Planning Engine (规划引擎)

采用 **LLM + 规则双通道** 架构：

```
用户输入
  → 第一层：路线规划引擎（算法驱动）
      候选 POI 筛选 → 综合评分排序 → 贪心构建路线 → 2-opt 优化
  → 第二层：LLM 任务生成（AI 驱动）
      意图 + 路线 + 工具列表 → LLM 生成任务 DAG
  → 兜底：规则引擎（LLM 失败时自动回退）
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

### 2.4 Story Engine (剧情引擎)

关键词触发 → 模板匹配 → Checkpoint 映射到路线节点

- 4 套故事模板覆盖：家庭、情侣、朋友、团建
- 关键词检测：仅在用户输入包含剧情相关词汇时激活
- Checkpoint 动态适配：路线节点多/少于模板时自动调整

### 2.5 Route Planner (路线规划)

- 贪心算法构建初始路线
- 2-opt 优化（带时间窗口校验）
- 确定性评分：基于 POI id 的 hash 扰动，保证同输入同输出

## 三、技术选型

| 组件 | 技术 | 理由 |
|------|------|------|
| 后端框架 | FastAPI | 异步支持好，自动文档，Pydantic 验证 |
| 会话存储 | SQLite | 零配置，持久化，单文件部署 |
| LLM | DeepSeek / Claude / OpenAI | 多 provider 支持，Mock 兜底 |
| 前端 | 原生 HTML/CSS/JS | 零构建依赖，静态文件服务 |
| 测试 | pytest + pytest-asyncio | 异步测试支持，185+ 测试用例 |

## 四、API 接口

### 4.1 规划请求

```
POST /api/agent/execute
Body: {"userInput": "带老婆吃火锅", "sessionId": null}
Response: {
  "status": "waiting_confirmation",
  "sessionId": "abc123",
  "planSummary": "...",
  "route": {...},
  "story": {...},
  "tasks": [...]
}
```

### 4.2 确认执行

```
POST /api/agent/confirm
Body: {"sessionId": "abc123", "confirmed": true}
Response: {
  "status": "success",
  "sessionId": "abc123",
  "results": {...},
  "shareText": "...",
  "route": {...},
  "tasks": [...]
}
```

### 4.3 健康检查

```
GET /api/agent/health
Response: {
  "status": "ok",
  "service": "meituan-agent-backend",
  "version": "2.1.0",
  "llm_provider": "mock"
}
```

## 五、目录结构

```
meituan-agent/
├── agent/                      # Python Agent 核心
│   ├── api.py                  # FastAPI 后端（统一入口）
│   ├── main.py                 # Agent 入口
│   ├── core/
│   │   ├── planner.py          # 规划引擎（LLM + 规则双通道）
│   │   ├── route_planner.py    # 路线规划（贪心 + 2-opt）
│   │   ├── scene_manager.py    # 场景识别（6 种场景）
│   │   ├── story_engine.py     # 剧本杀叙事引擎
│   │   ├── session.py          # 会话管理（SQLite 持久化）
│   │   ├── state_machine.py    # 状态机
│   │   ├── exception_handler.py # 异常处理
│   │   └── poi_data.py         # POI 数据（16 品类 50+ 条）
│   ├── llm/
│   │   ├── client.py           # LLM 客户端（多 provider）
│   │   └── prompts.py          # 提示词
│   └── tools/
│       ├── search_poi.py       # POI 搜索
│       ├── book_restaurant.py  # 餐厅预订
│       ├── book_venue.py       # 场地预订
│       ├── check_queue.py      # 排队取号
│       ├── order_delivery.py   # 即时配送
│       └── weather_api.py      # 天气查询
├── static/                     # Web 前端
│   ├── index.html              # HTML 结构
│   ├── styles.css              # CSS 样式
│   └── app.js                  # JavaScript 逻辑
├── miniprogram/                # 微信小程序
├── tests/                      # 测试（185+ 个）
├── data/                       # SQLite 数据库（gitignore）
├── run_demo.py                 # 演示脚本
├── DESIGN.md                   # 详细设计文档
└── CHANGELOG.md                # 版本变更记录
```

## 六、数据流

```
用户输入 "带老婆孩子出去玩"
  │
  ▼
意图解析 (LLM / 规则)
  → 识别场景: FAMILY
  → 识别约束: 儿童友好、低卡饮食
  → 识别需求: 娱乐 + 餐饮 + 惊喜
  │
  ▼
路线规划 (贪心 + 2-opt)
  → 候选 POI 评分 → 构建路线 → 优化顺序
  → 输出: [儿童乐园, 餐厅, ...] + 时间线
  │
  ▼
任务生成 (LLM / 规则)
  → 天气查询 → POI 搜索 → 餐厅预订 → 排队 → 配送
  → 输出: Task DAG (带依赖关系)
  │
  ▼
用户确认
  → 展示方案 → 等待确认
  │
  ▼
任务执行 (按依赖顺序)
  → 逐个调用工具 → 异常处理 → 结果汇总
  │
  ▼
输出结果 + 分享文案
```
