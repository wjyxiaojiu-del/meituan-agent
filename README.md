> **中文** | [English](README_en.md)

# 美团 AI Agent — 剧本杀 Citywalk × 智能行程规划

> 不只是推荐去哪玩，而是把整座城市变成沉浸式游戏场，Agent 做你的 DM（主持人）。

## 核心能力

- **智能路线规划**：多 POI 串联，贪心 + 2-opt 优化，考虑距离/时间/营业约束
- **LLM 任务生成**：DeepSeek 驱动，自动选择工具、填充参数、声明依赖
- **剧本杀叙事引擎**：4 套故事模板，把普通 Citywalk 变成沉浸式剧情冒险
- **一键执行**：用户确认后自动执行预订、排队、配送等操作
- **三层异常处理**：Retry → Fallback → Replan

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行演示（Mock 模式，无需 API Key）
python run_demo.py

# 运行演示（真实 LLM）
# 1. 复制配置模板
cp config.example.json config.json
# 2. 填入 DeepSeek API Key
# 3. 运行
python run_demo.py
```

## 演示场景

```bash
python run_demo.py                # 全部 3 个场景
python run_demo.py --scenario 2   # 只跑剧本杀场景
python run_demo.py --quick        # 快速模式（跳过执行）
```

| 场景 | 输入 | 展示能力 |
|------|------|----------|
| 家庭出游 | 带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜 | 天气+搜索+预订+排队+配送 |
| 剧本杀 Citywalk | 和4个朋友出去玩，想玩点不一样的，要有剧情 | 剧情引擎+路线规划+密室预订 |
| 企业团建 | 公司20人团建，要会议室和聚餐，预算人均200 | 场地预订+多人+预算控制 |

## 后端 API

```bash
# 启动 FastAPI 后端
python -m agent.api

# 健康检查
GET  /api/agent/health

# 规划请求（生成方案，等待确认）
POST /api/agent/execute
Body: {"userInput": "带老婆吃火锅"}

# 确认执行
POST /api/agent/confirm
Body: {"sessionId": "xxx", "confirmed": true}
```

## 测试

```bash
# 运行全部测试（185+ 个）
pytest tests/ -v

# 运行指定测试
pytest tests/test_api.py -v           # API 测试
pytest tests/test_tools.py -v         # 工具测试
pytest tests/test_day11_integration.py -v  # 集成测试
```

## 项目结构

```
meituan-agent/
├── run_demo.py              # 演示脚本
├── config.json              # LLM 配置（不提交）
├── config.example.json      # 配置模板
├── agent/
│   ├── api.py               # FastAPI 后端
│   ├── main.py              # Agent 入口
│   ├── core/
│   │   ├── planner.py       # 规划引擎（LLM + 规则双层）
│   │   ├── route_planner.py # 路线规划（贪心 + 2-opt）
│   │   ├── scene_manager.py # 场景识别（6 种场景）
│   │   ├── story_engine.py  # 剧本杀叙事引擎
│   │   ├── state_machine.py # 状态机
│   │   ├── exception_handler.py # 异常处理
│   │   ├── session.py       # 会话管理
│   │   └── poi_data.py      # POI 数据
│   ├── llm/
│   │   ├── client.py        # LLM 客户端
│   │   └── prompts.py       # 提示词
│   └── tools/
│       ├── search_poi.py    # POI 搜索（16 品类 50+ 条）
│       ├── book_restaurant.py # 餐厅预订
│       ├── book_venue.py    # 场地预订
│       ├── check_queue.py   # 排队取号
│       ├── order_delivery.py # 即时配送
│       └── weather_api.py   # 天气查询
├── miniprogram/             # 微信小程序前端
└── tests/                   # 测试（185+ 个）
```

## 技术亮点

1. **双层规划**：路线规划引擎（算法）+ LLM 任务生成（AI），兼顾确定性和灵活性
2. **剧情引擎**：关键词触发 → 模板匹配 → Checkpoint 映射到路线节点
3. **确认流程**：`run()` 返回 `waiting_confirmation` → 用户确认 → `confirm_and_execute()` 执行
4. **动态参数引用**：`{T001.results[0].id}` 格式，任务间传递搜索结果
5. **Mock 兜底**：无 API Key 时自动降级，Demo 不依赖网络
