# 美团 AI Agent — Claude Code 执行指令集

> 按优先级排序，直接复制粘贴给 Claude Code

---

## 第一轮：P0 致命 Bug（先全部跑通）

### 指令 1：修复截断的 `continue_conversation`

```text
请修复文件 agent/core/planner.py 第 1000 行被截断的 continue_conversation 方法。当前代码在 else: 处结束，缺少实现。

要求：
1. 如果 is_modification=True 且 session.current_plan 存在：调用 return await self.run(user_input, session_id) 重新规划
2. 否则（普通追问）：将用户消息追加到 session，用 LLM 生成对话回复，return 包含 status="conversation_continued"、plan_summary、session_id 的字典
3. 不要改变方法签名

修复后验证：python -c "from agent.core.planner import Planner; import inspect; print('continue_conversation' in [m for m in dir(Planner)])"
```

### 指令 2：修复并发状态竞争

```text
请修复 agent/api.py 和 agent/core/planner.py 中的并发安全问题：

1. 在 agent/api.py 中：删除第 28 行的全局 agent = create_agent()，改为在每个接口函数内部调用 agent = create_agent()
2. 在 agent/core/planner.py 中：
   - 删除 self._pending_route 和 self._last_route 这两个实例变量
   - 在 run() 方法中（第 746 行附近），将 self._pending_route 改为局部变量 pending_route
   - _plan_route_from_intent() 保持返回 (route, stats)，run() 用局部变量接收

验证：grep -n "_pending_route\|_last_route" agent/core/planner.py 应该无结果
```

### 指令 3：修复运算符优先级 Bug

```text
请修复 agent/core/route_planner.py 第 264 行的 bug：

原代码：current_location = start_location or valid_pois[0] if valid_pois else None
修改为：current_location = start_location or (valid_pois[0] if valid_pois else None)

同时检查整个文件中是否有类似的隐式优先级问题并一并修复。

验证：pytest tests/test_planner.py -v
```

### 指令 4：修复状态机引用错误

```text
请修复 agent/core/planner.py 第 702 行的状态判断 bug：

将：elif self.state_machine.all_tasks_completed():
改为：elif local_sm.all_tasks_completed():

同时检查 execute_plan() 方法中第 696-706 行的所有状态判断，确保都使用 local_sm 而不是 self.state_machine。

验证：pytest tests/test_exception_scenarios.py -v
```

---

## 第二轮：P1 功能缺陷（比赛核心能力）

### 指令 5：实现真正的 2-opt 算法

```text
请在 agent/core/route_planner.py 中补全 _two_opt() 方法（当前第 328-351 行只有空循环）。

要求：
1. 计算当前路线总距离（sum of calculate_distance between consecutive nodes）
2. 对于每一对 i, j (0 < i < j < len(route)-1)，尝试反转 i 到 j 之间的子序列
3. 如果反转后总距离减少，接受交换，标记 improved=True
4. 每次交换后，调用辅助方法 _recalculate_route_times(route, start_time) 重新计算各节点的 arrival_time/departure_time/travel_time
5. 限制迭代次数 max_iterations=50

在 tests/test_planner.py 中添加测试：构造 4 个正方形顶点的 POI，验证 2-opt 能优化掉交叉路线。

验证：pytest tests/test_planner.py::test_two_opt -v
```

### 指令 6：修复 DeepSeek 兼容性

```text
请修复 agent/llm/client.py 中 DeepSeek 不支持 response_format 的问题：

在 _call_openai() 方法中：
- 仅在 self.config.provider == "openai" 时才在 kwargs 中加入 response_format
- 当 provider 为 "deepseek" 时，不传 response_format 参数

在 chat_json() 方法中：
- 调用 chat() 时，对 deepseek provider 不传 response_format="json"
- 在 system_prompt 中追加："请只输出纯 JSON，不要 markdown 代码块，不要其他文字。"

验证：python -c "from agent.llm.client import LLMClient, LLMConfig; c=LLMClient(LLMConfig(provider='deepseek', api_key='test')); print('ok')"
```

### 指令 7：扩充 POI 数据

```text
请扩充 agent/core/poi_data.py 的 Mock 数据：

新增以下 POI（每个至少 2 个，坐标在上海市中心 lat:31.20-31.25, lng:121.45-121.50）：
- 剧本杀（已有1个，加2个）：不同主题（恐怖本、情感本）
- 花店（已有1个，加2个）
- 甜品店/奶茶店（新品类，至少2个）
- 夜市/步行街（新品类，至少1个）

要求：评分、价格、营业时间有区分度；tags 包含"浪漫"、"惊喜"、"约会"等场景标签；suitable_scenes 正确标注。

验证：pytest tests/test_tools.py -v
```

### 指令 8：补齐小程序 API 配置

```text
请检查并完善 miniprogram/utils/api.js（如不存在则创建）：

1. 定义 const BASE_URL = 'http://localhost:8080'（开发环境）
2. 封装三个 API 函数：execute(userInput)、confirm(sessionId)、healthCheck()
3. 每个请求设置 timeout: 10000
4. 错误处理：后端不可用时 wx.showToast({title: '服务连接失败'})
5. 在 app.js onLaunch 中调用 healthCheck()

确保前端能跑通：输入需求 → 获取方案 → 确认执行 → 查看结果。

验证：用微信开发者工具打开 miniprogram 目录，检查控制台无报错
```

### 指令 9：添加一键启动脚本

```text
请创建启动脚本：

1. start.bat（Windows）：
   - @echo off
   - 检查 python --version
   - pip install -r requirements.txt
   - 检查 .env 文件是否存在，不存在则复制 .env.example 并提示配置 API Key
   - 启动：python -m agent.api
   - echo 后端已启动：http://localhost:8080

2. start.sh（Mac/Linux，功能同上，加 chmod +x）

3. 更新 README.md，在"快速开始"后添加"5分钟启动"章节，说明双击 start.bat 即可。

验证：双击 start.bat 能正常启动后端
```

---

## 第三轮：P2 工程优化（有时间再做）

### 指令 10：pytest 配置

```text
创建 pytest.ini：
[pytest]
asyncio_mode = auto
testpaths = tests

验证：pytest tests/ --collect-only | tail -5
```

### 指令 11：Dockerfile

```text
创建 Dockerfile：
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["uvicorn", "agent.api:app", "--host", "0.0.0.0", "--port", "8080"]

创建 .dockerignore（排除 .env config.json __pycache__ *.pyc .git）

验证：docker build -t meituan-agent .
```

---

## 执行顺序建议

1. 先一次性把指令 1-4 丢给 Claude Code，等跑通测试
2. 再丢指令 5-9，强化核心能力
3. 最后有时间再丢 10-11

**验证总命令：**
```bash
cd ~/Desktop/vibe\ coding/meituan-agent
python -m pytest tests/ -v --tb=short
python run_demo.py --quick
```
