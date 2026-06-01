# Changelog

## v2.3.0 — 演示打磨 + 安全加固 (2026-06-01)

### 演示打磨
- 结构化错误路径：`reason_code` + `suggestions` chip，前端/小程序双端渲染错误卡片
- POI capability_tags 美团味：团购券/闪送/会员折扣/积分/扫码点餐/免预约，task card 双端 chip
- Capability-aware 分享文案 + plan summary（"用到了 团购券×2、闪送"）
- Inspector overlay 新增 caps aggregation 行 + 错误原因行
- 小程序多轮对话完整实现：chat.js dispatch + WXML diff 高亮 + caps chip + 错误卡片
- `/api/agent/continue` 响应补全 `params` 字段（修复 caps 渲染空白）

### 前端体验
- Web 前端消息时间戳（HH:MM 格式，用户/AI 消息均显示）
- 移动端键盘自适应：`visualViewport` resize 监听自动滚动
- 小程序 input `cursor-spacing` + `adjust-position` 优化

### 安全加固
- Pydantic 输入校验：`userInput` 500 字上限 + `sessionId` 非空
- API 限流：100 req/min per IP，localhost 豁免，环境变量 `RATE_LIMIT` 可配
- 验证异常统一返回 400（非 422）

### 测试
- 全套 314 测试通过（+75 从 v2.2 的 239）

---

## v2.2.0 — 真正的多轮对话 (2026-05-31)

### 核心：plan patch 路径
- 新增规则解析器 `modification_parser.py`：覆盖 12+ 类修改表达（replace/remove/insert/shift_time/declare_dislike），confidence=1.0
- 新增 plan patch 服务 `plan_patch_service.py`：在 `pending_tasks`/`pending_route` 上局部增删改，**task_id 全程保持稳定**（前端 diff key 不失效）
- `continue_conversation()` 优先走 patch，未命中且检测出修改意图才回退到 `run()` 重规划
- LLM 兜底 `_llm_fallback_parse`：规则未命中时调 LLM 输出 ModificationAction JSON（confidence=0.6），任何异常都安全降级到普通对话回复

### RoutePlanner 黑名单
- `RouteConstraints` 新增 `excluded_poi_ids` 字段，`plan_route` 在筛选阶段排除黑名单 POI
- `RouteService.plan_from_intent` 自动合入 `session.context["disliked_poi_ids"]` / `disliked_categories`（仅本会话生效）

### shift_time 营业时间校验
- 整体时间调整后逐节点 `check_open`，任一不通过 → 回滚 + 返回错误（不闷头报错）

### 前端
- `STATE` + `localStorage` 持久化（key: `mt_state_v2`）：刷新后 sid 和 lastPlan 自动恢复
- 多轮对话分支：已有 plan 时走 `/api/agent/continue`（非流式），无 plan 时走原 `/api/agent/execute/stream`
- Diff 高亮：替换节点黄底脉冲、删除节点红色删除线、新增节点绿色滑入；变更摘要 bubble 实时呈现
- 历史会话侧栏：拉取 `GET /api/agent/sessions` 列出最近 20 个会话
- 路线节点 DOM 新增 `data-poi-id`，前端可定位单个节点叠加 diff class

### API
- 新增 `POST /api/agent/continue`：返回 status / actionType / changeLog / planSummary / reply / route / tasks
- 新增 `GET /api/agent/sessions?limit=20`：历史会话列表

### 测试
- `test_modification.py`：19 个用例（13 类 utterance + 指代解析 + 误报规避）
- `test_plan_patch.py`：7 个用例（5 个 action_type + task_id 稳定性 + 唯一性 + 营业回滚）
- `test_continue_conversation.py`：5 个用例（patch 不重规划 spy / remove / dislike / 普通对话 / confirm 清理）
- 全套 239 passed，2 skipped，无回归

### Demo
- `demo_multi_turn()` 扩展为 7 步真实 patch 流：换餐厅 → 删最后 → 加咖啡 → 调时间 → 偏好记忆 → 确认执行

---

## v2.1.0 — 优化重构 (2026-05-30)

### 代码质量
- 合并重复后端：废弃 `backend_simple.py`，统一使用 FastAPI (`agent/api.py`)
- 删除空脚手架目录 `meituan-agent/`（Java/小程序模板）
- 删除 Java Spring Boot 后端 `backend/`（已由 Python FastAPI 替代）
- FastAPI 后端新增：静态文件服务、Unicode 清理、GBK 编码回退

### 算法增强
- 2-opt 时间窗口校验：从始终返回 True 改为真正的营业时间校验
- 2-opt 搜索范围扩展：从 2 位扩大到 4 位，距离阈值从 20% 放宽到 10%
- POI 评分确定性：随机扰动改为基于 POI id 的 hash，同批次结果一致
- 修正评分函数文档：实际权重 35/15/20/15/15

### 前端
- 拆分 48KB 单文件 `index.html` 为 HTML + CSS + JS 三文件

### 架构
- 会话持久化：新增 SQLite 存储后端，重启不丢数据
- LLM 计划生成接入：`_llm_create_plan` 从死代码变为可用（LLM 可用时优先使用，失败回退规则引擎）

---

## v2.0.0 — 美团 AI Agent 大赛完整实现 (2026-05-15)

### 核心功能
- ReAct 规划引擎：LLM 意图解析 → 路线规划 → 任务生成 → 确认执行
- 贪心 + 2-opt 路线优化：Haversine 距离、营业时间、预算约束、类别多样性
- 剧本杀叙事引擎：11 个主题模板，22+ 故事线，检查点映射到路线 POI
- 三层异常处理：Retry（指数退避）→ Fallback（工具替换）→ Replan（环境变化）
- 6 个 Mock 工具：天气查询、POI 搜索、餐厅预订、排队取号、场地预订、即时配送
- 6 种场景识别：家庭、朋友、约会、团建、独行、亲子
- 多轮对话：修改检测、意图合并、上下文记忆
- 确认执行流程：规划 → 等待确认 → 依赖顺序执行 → 分享文案生成

### 测试
- 185+ 测试用例，全部通过
- 覆盖：工具单元测试、规划器测试、API 测试、集成测试、异常场景测试、LLM 测试、叙事引擎测试

### 前端
- 暗色主题 SPA：美团黄 (#FFD100) 强调色
- 聊天界面：消息气泡、加载动画、6 场景快捷卡片
- 路线卡片：时间线展示、步行距离、任务状态
- 确认/取消流程、微信分享文案

### 技术栈
- Python + FastAPI + 微信小程序
- LLM：Claude / OpenAI / DeepSeek / MiMo（Mock 模式兜底）
- 路线规划：贪心算法 + 2-opt 局部优化
- 叙事引擎：模板池 + LLM 生成 + 类别适配器
