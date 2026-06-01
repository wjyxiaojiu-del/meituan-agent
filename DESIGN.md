# 设计文档

## 1. Planning 策略

### 1.1 双层规划架构

```
用户输入
  → 第一层：路线规划引擎（算法驱动）
      候选 POI 筛选 → 综合评分排序 → 贪心构建路线 → 2-opt 优化
  → 第二层：LLM 任务生成（AI 驱动）
      意图 + 路线 + 工具列表 → LLM 生成任务 DAG
  → 兜底：规则引擎（LLM 失败时）
```

### 1.2 POI 评分函数

综合评分 = 评分×35% + 品类匹配×15% + 预算适配×20% + 多样性×15% + 个性化×15%

- 评分：`rating * 20`（0-70）
- 品类匹配：POI 品类与用户需求的匹配度（0-30）
- 预算适配：越接近预算上限越好，超出则减分（0-40）
- 多样性：基于 POI id 的确定性扰动，保证同输入同输出（0-30）
- 个性化：根据情绪标签匹配 POI 标签（0-30）

### 1.3 约束处理

| 约束类型 | 处理方式 | 示例 |
|----------|----------|------|
| 营业时间 | 硬约束，不营业则跳过 | 10:00-22:00 |
| 预算 | 硬约束，超出停止追加 | 人均 200 |
| 时间窗口 | 软约束，允许微小偏移 | 总时长 ≤ 6h |
| 步行距离 | 通过交通时间体现 | 5km/h |

### 1.4 场景识别

6 种场景：FAMILY / PARENT_CHILD / DATE / FRIENDS / TEAM_BUILDING / SOLO

识别规则：
1. 关键词优先（"团建" → TEAM_BUILDING）
2. 角色组合（child + wife → FAMILY）
3. 人数辅助（≥3 朋友 → FRIENDS）

## 2. 工具调用链路

```
Planner.create_plan(intent)
  ├── route_planner.plan_route(candidates, constraints)
  │     └── 贪心 + 2-opt → List[RouteNode]
  ├── llm.chat(prompt) → List[Task]
  │     └── 每个 Task 包含: task_id, tool_name, params, dependencies
  └── _ensure_weather_task(tasks) → 保证天气任务存在

Planner.execute_plan(tasks)
  ├── state_machine.reset()
  ├── while not all_completed:
  │     pending = get_pending_tasks()  # 依赖已满足的任务
  │     for task in pending:
  │         resolved_params = resolve_params(task.params, results)
  │         tool_result = await tool(resolved_params)
  │         if success → results[task_id] = tool_result
  │         if failed → exception_handler.handle_error()
  └── return results

参数动态引用：
  {T001.results[0].id}  → 从 T001 的执行结果中取第一个元素的 id 字段
```

### 工具清单

| 工具 | 功能 | 关键参数 |
|------|------|----------|
| weather_api | 天气查询 | date, time |
| search_poi | POI 搜索 | category, keywords, rating_min |
| book_restaurant | 餐厅预订 | restaurant_id, time, party_size |
| book_venue | 场地预订 | venue_id, date, start_time, end_time |
| check_queue | 排队取号 | restaurant_id, action, party_size |
| order_delivery | 即时配送 | item_type, item_name, deliver_to |

## 3. 异常处理机制

### 3.1 三层处理

| 层级 | 策略 | 触发条件 | 示例 |
|------|------|----------|------|
| L1 Retry | 指数退避重试 | 网络超时、API 限流 | 天气查询失败 1s→2s→4s |
| L2 Fallback | 切换备选方案 | 业务性失败 | 餐厅满座 → 推荐相似餐厅 |
| L3 Replan | 重新规划 | 环境剧变 | 暴雨 → 室内替代方案 |

### 3.2 状态机

```
PLANNING → EXECUTING → COMPLETED
              ↓
            ERROR → Retry/Fallback → EXECUTING
              ↓
            ERROR → Replan → PLANNING
```

- PLANNING：解析意图、生成计划
- EXECUTING：按依赖顺序执行任务
- COMPLETED：所有任务完成（终态）
- ERROR：任务失败，进入异常处理

### 3.3 确认流程

```
run(user_input)
  → 解析意图 → 路线规划 → 任务生成
  → 保存 pending_tasks 到 session
  → 返回 waiting_confirmation

confirm_and_execute(session_id, confirmed=True)
  → 读取 pending_tasks
  → execute_plan(tasks)
  → 生成分享文案
  → 返回 success + results + share_text

confirm_and_execute(session_id, confirmed=False)
  → 返回 cancelled
```

## 4. 数据规模

- POI 数据：28 个，覆盖 16 个品类
- Mock 工具数据：50+ 条搜索结果、8 家餐厅、3 个场地
- 测试：185+ 个，覆盖单元/集成/边界场景
