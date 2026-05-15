# 美团 AI Agent 项目总结

## 项目概述

基于 Python + Java + 微信小程序的混合架构，实现跨业务场景的智能规划与执行。

## 已完成功能

### Step 1: LLM 集成 ✅

- 创建 `agent/llm/client.py` - LLM 客户端，支持 Claude/OpenAI API
- 创建 `agent/llm/prompts.py` - 提示词模板
- 修改 `agent/core/planner.py` - 使用 LLM 进行意图解析
- 支持 Mock 模式（无需 API Key 即可运行）

### Step 2: 异常场景完善 ✅

- 创建 `tests/test_exception_scenarios.py` - 完整的异常场景测试
- 测试 Fallback（备选方案）机制
- 测试 Replan（重新规划）机制
- 测试 Retry（重试）机制
- 测试用户通知生成

### Step 3: Java 后端服务 ✅

- 创建 Spring Boot 项目结构
- 实现 REST API（`/api/agent/execute`）
- 实现 WebSocket 支持
- 实现会话管理服务
- 创建数据模型（Request/Response/Session）

### Step 4: 小程序前端 ✅

- 创建微信小程序项目结构
- 实现首页（快捷入口、输入框）
- 实现对话页面（消息列表、实时交互）
- 实现行程详情页面（任务列表、状态展示）
- 封装 API 请求工具

## 项目结构

```
meituan-agent/
├── agent/                          # Python Agent 核心
│   ├── core/
│   │   ├── planner.py              # ReAct 规划引擎
│   │   ├── state_machine.py        # 状态机管理
│   │   └── exception_handler.py    # 三层异常处理
│   ├── tools/
│   │   ├── search_poi.py           # 搜索工具
│   │   ├── book_restaurant.py      # 餐厅预订
│   │   ├── check_queue.py          # 排队取号
│   │   ├── order_delivery.py       # 即时配送
│   │   └── weather_api.py          # 天气查询
│   ├── llm/
│   │   ├── client.py               # LLM 客户端
│   │   └── prompts.py              # 提示词模板
│   └── main.py                     # 入口文件
├── backend/                        # Java 后端服务
│   ├── pom.xml
│   └── src/main/java/com/meituan/agent/
│       ├── AgentApplication.java
│       ├── controller/
│       ├── service/
│       ├── model/
│       └── config/
├── miniprogram/                    # 微信小程序
│   ├── app.json
│   ├── app.js
│   ├── app.wxss
│   ├── utils/
│   │   └── api.js
│   └── pages/
│       ├── index/                  # 首页
│       ├── chat/                   # 对话页
│       └── plan/                   # 行程详情页
├── tests/                          # 测试文件
│   ├── test_planner.py
│   └── test_exception_scenarios.py
├── docs/                           # 设计文档
│   ├── architecture.md
│   └── design_proposal.md
├── requirements.txt
├── run_demo.py
└── README.md
```

## 核心功能

### 1. ReAct 规划引擎

```
用户输入 → LLM 意图解析 → 任务拆解 → 工具调用 → 结果返回
```

### 2. 三层异常处理

```
Layer 1: Retry (自动重试) - 网络超时、API 限流
Layer 2: Fallback (备选方案) - 餐厅满座、商品售罄
Layer 3: Replan (重新规划) - 天气突变、环境变化
```

### 3. 跨业务工具调用链

```
Search_POI → Book_Restaurant → Check_Queue → Order_Delivery
```

## 运行方式

### 1. Python Agent

```bash
cd meituan-agent
pip install -r requirements.txt
python run_demo.py
```

### 2. Java 后端

```bash
cd meituan-agent/backend
mvn clean package
java -jar target/agent-backend-1.0.0.jar
```

### 3. 小程序

使用微信开发者工具打开 `miniprogram` 目录。

## 测试

```bash
# 运行单元测试
python -m pytest tests/

# 运行异常场景测试
python tests/test_exception_scenarios.py
```

## 技术亮点

1. **LLM 驱动的意图理解** - 使用大模型进行自然语言理解
2. **ReAct 架构** - 推理与行动交替进行
3. **状态机管理** - 清晰的任务状态流转
4. **三层异常处理** - 高容错的弹性执行
5. **跨业务编排** - 打通美团多个业务线

## 商业价值

1. **交叉销售** - 到店综合 + 到店餐饮 + 即时零售
2. **用户体验** - 从 30 分钟手动规划 → 1 分钟自然语言描述
3. **决策质量** - AI 基于大数据推荐最优组合

## 下一步建议

1. 集成真实 LLM API（需要 API Key）
2. 完善 Mock API 数据
3. 添加更多业务场景
4. 优化用户体验
5. 性能测试和优化
