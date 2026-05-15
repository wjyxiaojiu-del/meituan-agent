package com.meituan.agent.model;

import lombok.Data;
import lombok.Builder;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

/**
 * Agent 请求模型
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AgentRequest {

    /**
     * 用户输入的自然语言
     */
    private String userInput;

    /**
     * 会话 ID（可选，用于多轮对话）
     */
    private String sessionId;

    /**
     * 用户 ID（可选）
     */
    private String userId;
}
