# 快速开始指南

## 环境要求

- Python 3.10+
- pip

## Step 1: 安装依赖（2分钟）

```bash
cd meituan-agent
pip install -r requirements.txt
```

## Step 2: 运行演示（Mock 模式，无需 API Key）

```bash
python run_demo.py
```

预期输出：
```
======================================================================
   美团 AI Agent 跨业务智能规划系统 - Demo
======================================================================

场景一：正常流程 - 家庭周末出游
✅ 所有任务执行成功！

场景二：异常处理 - 餐厅满座自动切换
✅ 所有任务执行成功（使用了备选方案）

场景三：重新规划 - 天气突变
✅ 所有任务执行成功
```

## Step 3: 配置真实 LLM（可选）

#### 方案 A: DeepSeek（推荐，国内可访问）

1. 访问 https://platform.deepseek.com 注册并获取 API Key
2. 复制配置模板并填入 Key：

```bash
cp config.example.json config.json
# 编辑 config.json，填入 api_key
```

#### 方案 B: Claude API

```bash
$env:LLM_API_KEY="sk-ant-api03-xxxxx"
$env:LLM_PROVIDER="claude"
$env:LLM_MODEL="claude-sonnet-4-20250514"
```

#### 方案 C: OpenAI / 通义千问

```bash
# OpenAI
$env:LLM_API_KEY="sk-xxxxx"
$env:LLM_PROVIDER="openai"
$env:LLM_MODEL="gpt-4o"

# 通义千问（阿里）
$env:LLM_API_KEY="sk-xxxxx"
$env:LLM_PROVIDER="openai"
$env:LLM_MODEL="qwen-turbo"
$env:LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
```

#### 方案 D: Mock 模式（默认）

不设置任何环境变量即可，系统自动使用 Mock 模式。

## Step 4: 启动 Web 服务（可选）

```bash
# 启动 FastAPI 后端（含前端页面）
python -m agent.api

# 浏览器访问 http://localhost:8080
```

## Step 5: 运行测试

```bash
# 运行全部测试（185 个）
pytest tests/ -v

# 运行指定模块
pytest tests/test_api.py -v           # API 测试
pytest tests/test_tools.py -v         # 工具测试
pytest tests/test_story_engine.py -v  # 剧情引擎测试
```

---

## 常见问题

### Q1: LLM API 调用失败怎么办？

```bash
# 检查配置
echo $env:LLM_API_KEY

# 回退到 Mock 模式
$env:LLM_PROVIDER="mock"
```

### Q2: 依赖安装失败？

```bash
# 升级 pip
python -m pip install --upgrade pip

# 使用清华镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q3: 端口被占用？

```bash
# 使用其他端口
python -m uvicorn agent.api:app --port 8081
```

---

## 文件结构速查

```
meituan-agent/
├── agent/                  # Python Agent 核心
│   ├── api.py              # FastAPI 后端（含静态文件服务）
│   ├── main.py             # Agent 入口
│   ├── core/
│   │   ├── planner.py      # 规划引擎（LLM + 规则双通道）
│   │   ├── route_planner.py # 路线规划（贪心 + 2-opt）
│   │   ├── scene_manager.py # 场景识别（6 种场景）
│   │   ├── story_engine.py  # 剧本杀叙事引擎
│   │   ├── session.py      # 会话管理（SQLite 持久化）
│   │   ├── state_machine.py # 状态机
│   │   └── exception_handler.py # 异常处理
│   ├── llm/                # LLM 集成
│   └── tools/              # 工具实现
├── static/                 # 前端页面
│   ├── index.html          # HTML 结构
│   ├── styles.css          # CSS 样式
│   └── app.js              # JavaScript 逻辑
├── miniprogram/            # 微信小程序
├── tests/                  # 测试（185 个）
├── run_demo.py             # 演示脚本
└── DESIGN.md               # 设计文档
```

---

## 相关文档

- `README.md` - 项目概述
- `DESIGN.md` - 详细设计文档
- `CHANGELOG.md` - 版本变更记录
