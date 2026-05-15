package com.meituan.agent.controller;

import com.meituan.agent.model.AgentRequest;
import com.meituan.agent.model.AgentResponse;
import com.meituan.agent.service.AgentService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * Agent API 控制器
 */
@Slf4j
@RestController
@RequestMapping("/api/agent")
@CrossOrigin(origins = "*")
public class AgentController {

    private final AgentService agentService;

    public AgentController(AgentService agentService) {
        this.agentService = agentService;
    }

    /**
     * 执行 Agent 任务
     *
     * POST /api/agent/execute
     *
     * Request Body:
     * {
     *     "userInput": "这周六带老婆孩子出去玩，孩子5岁，老婆在减肥，要有惊喜",
     *     "sessionId": "optional-session-id",
     *     "userId": "optional-user-id"
     * }
     */
    @PostMapping("/execute")
    public ResponseEntity<AgentResponse> execute(@RequestBody AgentRequest request) {
        log.info("收到 Agent 请求: {}", request.getUserInput());

        // 参数校验
        if (request.getUserInput() == null || request.getUserInput().trim().isEmpty()) {
            return ResponseEntity.badRequest().body(
                    AgentResponse.builder()
                            .status("error")
                            .errorMessage("请输入您的需求")
                            .build()
            );
        }

        // 执行任务
        AgentResponse response = agentService.execute(request);

        log.info("Agent 执行完成: status={}", response.getStatus());
        return ResponseEntity.ok(response);
    }

    /**
     * 健康检查
     *
     * GET /api/agent/health
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of(
                "status", "ok",
                "service", "meituan-agent-backend",
                "version", "1.0.0"
        ));
    }
}
