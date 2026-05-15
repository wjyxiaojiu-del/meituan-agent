# 美团 AI Agent 后端服务

## 技术栈

- Java 17
- Spring Boot 3.2
- WebSocket (STOMP)
- FastJSON2

## 项目结构

```
backend/
├── pom.xml
└── src/main/java/com/meituan/agent/
    ├── AgentApplication.java          # 应用入口
    ├── controller/
    │   ├── AgentController.java       # REST API
    │   └── WebSocketController.java   # WebSocket
    ├── service/
    │   ├── AgentService.java          # Agent 服务
    │   └── SessionService.java        # 会话管理
    ├── model/
    │   ├── AgentRequest.java          # 请求模型
    │   ├── AgentResponse.java         # 响应模型
    │   └── Session.java               # 会话模型
    └── config/
        └── WebSocketConfig.java       # WebSocket 配置
```

## API 接口

### 1. 执行 Agent 任务

```
POST /api/agent/execute

Request:
{
    "userInput": "这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜",
    "sessionId": "optional-session-id",
    "userId": "optional-user-id"
}

Response:
{
    "status": "success",
    "sessionId": "xxx",
    "tasks": [...],
    "results": {...},
    "notification": "任务执行成功！"
}
```

### 2. 健康检查

```
GET /api/agent/health

Response:
{
    "status": "ok",
    "service": "meituan-agent-backend",
    "version": "1.0.0"
}
```

### 3. WebSocket

- 端点: `/ws`
- 发送: `/app/agent/chat`
- 订阅: `/topic/agent/response`

## 运行方式

```bash
# 1. 确保 Python Agent 可用
cd ../agent
pip install -r requirements.txt

# 2. 编译后端
cd ../backend
mvn clean package

# 3. 运行
java -jar target/agent-backend-1.0.0.jar

# 或者使用 Maven
mvn spring-boot:run
```

## 测试

```bash
# 健康检查
curl http://localhost:8080/api/agent/health

# 执行任务
curl -X POST http://localhost:8080/api/agent/execute \
  -H "Content-Type: application/json" \
  -d '{"userInput": "这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜"}'
```
