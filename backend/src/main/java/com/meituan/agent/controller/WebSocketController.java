package com.meituan.agent.controller;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.meituan.agent.model.AgentRequest;
import com.meituan.agent.model.AgentResponse;
import com.meituan.agent.service.AgentService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.messaging.handler.annotation.SendTo;
import org.springframework.stereotype.Controller;

/**
 * WebSocket 控制器
 * 支持实时通信
 */
@Slf4j
@Controller
public class WebSocketController {

    private final AgentService agentService;

    public WebSocketController(AgentService agentService) {
        this.agentService = agentService;
    }

    /**
     * 处理 WebSocket 消息
     *
     * 客户端发送到: /app/agent/chat
     * 订阅主题: /topic/agent/response
     */
    @MessageMapping("/agent/chat")
    @SendTo("/topic/agent/response")
    public AgentResponse handleChat(@Payload String message) {
        log.info("收到 WebSocket 消息: {}", message);

        try {
            // 解析消息
            JSONObject json = JSON.parseObject(message);
            String userInput = json.getString("userInput");
            String sessionId = json.getString("sessionId");
            String userId = json.getString("userId");

            // 构建请求
            AgentRequest request = AgentRequest.builder()
                    .userInput(userInput)
                    .sessionId(sessionId)
                    .userId(userId)
                    .build();

            // 执行任务
            AgentResponse response = agentService.execute(request);

            log.info("WebSocket 响应: status={}", response.getStatus());
            return response;

        } catch (Exception e) {
            log.error("WebSocket 处理失败", e);

            return AgentResponse.builder()
                    .status("error")
                    .errorMessage("消息处理失败: " + e.getMessage())
                    .build();
        }
    }
}
