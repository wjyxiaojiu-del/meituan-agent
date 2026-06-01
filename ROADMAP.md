# 美团 AI Agent 项目优化路线图

## 当前状态（v2.3）

| 模块 | 完成度 | 说明 |
|------|--------|------|
| Python Agent 核心 | 97% | LLM + 规则双通道，Mock 兜底，capability_tags |
| 多轮对话 patch 路径 | 97% | 12 类修改 utterance + task_id 稳定 + 偏好记忆 + 结构化错误 |
| FastAPI 后端 | 97% | SQLite 持久化，SSE 流式，/continue，输入校验+限流 |
| 路线规划引擎 | 92% | 贪心 + 2-opt，时间窗口校验，excluded_poi_ids 黑名单 |
| 剧本杀叙事引擎 | 87% | 4 套模板，关键词触发，checkpoint patch 联动 |
| 异常处理 | 92% | 三层处理：Retry/Fallback/Replan + 结构化错误建议 |
| 测试覆盖 | 95% | 314 个测试，单元/集成/边界/capability/error path |
| Web 前端 | 92% | localStorage、diff 高亮、历史侧栏、SSE 流式、时间戳、caps chip |
| 小程序前端 | 85% | 多轮对话、diff 高亮、caps chip、错误卡片、键盘适配 |
| 安全 | 85% | 输入长度校验、API 限流、Pydantic 验证 |
| 文档 | 87% | 架构/设计/快速开始/变更日志/Swagger 自动生成 |

---

## 已完成

### v2.0 - 架构升级
- [x] 合并后端：FastAPI 统一入口，删除 Java Spring Boot
- [x] SQLite 会话持久化
- [x] LLM 计划生成（LLM + 规则双通道）
- [x] 2-opt 时间窗口校验（真正的实现）
- [x] 确定性 POI 评分（hash 扰动替代 random）
- [x] 前端 SPA 拆分（HTML + CSS + JS）

### v2.1 - 质量提升
- [x] 剧本杀叙事引擎（4 套故事模板）
- [x] 6 种场景识别（FAMILY/DATE/FRIENDS/...）
- [x] 场地预订工具（book_venue）
- [x] 16 品类 50+ POI 数据
- [x] 185 个测试用例

### v2.2 - 真正的多轮对话
- [x] 规则解析器（12 类修改 utterance）
- [x] Plan patch 服务（task_id 稳定的局部修改）
- [x] RoutePlanner 黑名单参数 + dislike 偏好（仅本会话）
- [x] LLM 兜底解析（confidence=0.6）
- [x] shift_time 营业时间校验 + 整体回滚
- [x] `/api/agent/continue` 端点 + `/api/agent/sessions` 历史列表
- [x] 前端 localStorage 持久化 + diff 高亮 + 历史侧栏
- [x] 31 个新测试 + 全套 239 通过

### v2.3 - 演示打磨 + 安全加固
- [x] 结构化错误路径（reason_code + suggestions chip）
- [x] POI capability_tags 美团味（团购券/闪送/会员折扣/积分/扫码点餐/免预约）
- [x] Capability-aware 分享文案 + plan summary
- [x] Inspector overlay caps 行 + 错误原因行
- [x] 小程序多轮对话（chat.js dispatch + WXML diff + caps chip + 错误卡片）
- [x] `/api/agent/continue` 响应补全 params（caps 渲染修复）
- [x] Web 前端消息时间戳 + 移动端键盘自适应
- [x] 小程序 input cursor-spacing + adjust-position
- [x] Pydantic 输入校验（500 字上限 + sessionId 非空）
- [x] API 限流（100 req/min，localhost 豁免）
- [x] 全套 314 测试通过

---

## 待做

### P1 - 竞赛加分项

#### 1. 前端体验优化
- [x] 添加消息时间戳显示
- [x] 移动端聊天输入框适配（软键盘弹出）
- [ ] 加载骨架屏替代 spinner
- [ ] 路线卡片地图预览（高德/腾讯静态图 API）

#### 2. 多轮对话支持 ✅ v2.2 已完成
- [x] 支持 "把餐厅换成火锅" 类修改请求
- [x] 上下文理解：引用之前的搜索结果（POI 名 / 序号 / 类别 / 位置）
- [x] 对话历史本地存储（localStorage）

#### 3. 流式响应 ✅ v2.2 已完成
- [x] SSE (Server-Sent Events) 推送 Agent 思考过程
- [x] 前端逐字显示效果

### P2 - 技术完善

#### 4. 测试补全
- [x] SQLite 持久化集成测试
- [x] LLM 计划生成单元测试
- [x] 剧本杀引擎边界测试

#### 5. 文档完善
- [x] API 接口文档（FastAPI 自动生成 Swagger）
- [ ] 部署指南（Docker / 云服务器）

#### 6. 安全加固
- [x] 输入长度校验
- [x] API 限流
- [ ] 敏感信息过滤

### P3 - 锦上添花

#### 7. 小程序完善
- [ ] WebSocket 实时状态推送
- [ ] 行程卡片 Canvas 绘制 + 分享
- [ ] 微信登录集成

#### 8. 高级功能
- [ ] 语音输入支持
- [ ] 地图路线可视化
- [ ] 用户偏好学习
- [ ] 多人协作规划

---

## 技术债务

| 项目 | 优先级 | 说明 |
|------|--------|------|
| `test_select_template_team` 失败 | 中 | 剧本杀模板选择逻辑与测试期望不一致 |
| SQLite 线程安全 | 低 | 当前用 `threading.local()`，异步场景需评估 |
| 前端统计数据 | 低 | `app.js` 中的统计数字硬编码，不随代码更新 |

---

## 版本规划

| 版本 | 目标 | 重点 |
|------|------|------|
| v2.2 | 前端体验 | 骨架屏、地图预览、移动端适配 |
| v2.3 | 多轮对话 | 修改请求、上下文理解 |
| v3.0 | 生产就绪 | Docker 部署、API 文档、安全加固 |
