# 快速开始指南

## 立即行动（今天）

### Step 1: 配置 LLM API（10分钟）

#### 方案 A: 使用 Claude API（推荐）

1. 访问 https://console.anthropic.com
2. 注册账号并创建 API Key
3. 设置环境变量：

```bash
# Windows PowerShell
$env:LLM_API_KEY="sk-ant-api03-xxxxx"
$env:LLM_PROVIDER="claude"
$env:LLM_MODEL="claude-sonnet-4-20250514"
```

#### 方案 B: 使用 OpenAI API

1. 访问 https://platform.openai.com
2. 注册账号并创建 API Key
3. 设置环境变量：

```bash
$env:LLM_API_KEY="sk-xxxxx"
$env:LLM_PROVIDER="openai"
$env:LLM_MODEL="gpt-4o"
```

#### 方案 C: 使用国产 API（如果无法访问国外）

**通义千问（阿里）**：
```bash
$env:LLM_API_KEY="sk-xxxxx"
$env:LLM_PROVIDER="openai"
$env:LLM_MODEL="qwen-turbo"
$env:LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
```

#### 方案 D: 继续使用 Mock 模式

如果不方便获取 API Key，可以继续使用 Mock 模式：
```bash
$env:LLM_PROVIDER="mock"
```

---

### Step 2: 测试 LLM 集成（5分钟）

```bash
cd "C:\Users\wangjunyi\Desktop\vibe coding\meituan-agent"

# 测试意图识别
python -c "
import asyncio
from agent.main import create_agent

async def test():
    agent = create_agent()
    result = await agent.run('这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜')
    print('测试成功！')
    print('状态:', result.get('status'))
    print('任务数:', len(result.get('results', {})))

asyncio.run(test())
"
```

---

### Step 3: 运行完整 Demo（5分钟）

```bash
# 运行演示
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

---

### Step 4: 测试 Java 后端（5分钟）

```bash
# 启动后端
cd backend
mvn spring-boot:run

# 新开终端测试
curl http://localhost:8080/api/agent/health
```

---

### Step 5: 测试小程序（10分钟）

1. 下载并安装 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
2. 打开微信开发者工具
3. 选择"导入项目"
4. 选择目录：`C:\Users\wangjunyi\Desktop\vibe coding\meituan-agent\miniprogram`
5. 点击"编译"按钮

---

## 演示准备（明天）

### 准备演示脚本

```python
# demo_showcase.py
import asyncio
from agent.main import create_agent

async def showcase():
    agent = create_agent()
    
    print("\n" + "="*60)
    print("场景一：家庭周末出游")
    print("="*60)
    
    user_input = "这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜"
    print(f"\n用户输入: {user_input}")
    
    result = await agent.run(user_input)
    
    print("\n执行结果:")
    for task_id, task_result in result.get("results", {}).items():
        print(f"  [{task_id}] {task_result}")

if __name__ == "__main__":
    asyncio.run(showcase())
```

### 准备演示 PPT

参考 `P0_IMPLEMENTATION.md` 中的 PPT 结构。

---

## 常见问题

### Q1: LLM API 调用失败怎么办？

```bash
# 检查 API Key 是否正确
echo $env:LLM_API_KEY

# 检查网络连接
curl https://api.anthropic.com/v1/messages

# 使用 Mock 模式
$env:LLM_PROVIDER="mock"
```

### Q2: Maven 命令找不到？

```bash
# 添加 Maven 到 PATH
export PATH="/c/maven/bin:$PATH"

# 或者使用 Python 后端
python backend_simple.py
```

### Q3: 小程序无法连接后端？

1. 检查后端是否运行：`curl http://localhost:8080/api/agent/health`
2. 检查小程序配置：`miniprogram/app.json` 中的 `baseUrl`
3. 在微信开发者工具中勾选"不校验合法域名"

### Q4: 如何修改 Mock 数据？

编辑以下文件：
- `agent/tools/search_poi.py` - 搜索结果
- `agent/tools/book_restaurant.py` - 餐厅数据
- `agent/tools/weather_api.py` - 天气数据

---

## 文件结构速查

```
meituan-agent/
├── agent/                  # Python Agent 核心
│   ├── core/
│   │   ├── planner.py      # 规划引擎
│   │   ├── state_machine.py
│   │   └── exception_handler.py
│   ├── tools/              # 工具实现
│   ├── llm/                # LLM 集成
│   └── main.py             # 入口
├── backend/                # Java 后端
│   └── src/main/java/...
├── miniprogram/            # 小程序
│   ├── pages/
│   └── app.json
├── tests/                  # 测试
├── run_demo.py             # 演示脚本
└── ROADMAP.md              # 优化路线图
```

---

## 联系与支持

如有问题，请参考：
- `ROADMAP.md` - 完整优化计划
- `P0_IMPLEMENTATION.md` - P0 实施细节
- `docs/architecture.md` - 架构设计文档
