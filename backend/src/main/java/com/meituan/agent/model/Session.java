package com.meituan.agent.model;

import lombok.Data;
import lombok.Builder;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;
import java.util.ArrayList;

/**
 * 会话模型
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Session {

    /**
     * 会话 ID
     */
    private String sessionId;

    /**
     * 用户 ID
     */
    private String userId;

    /**
     * 会话状态: active, completed, expired
     */
    private String status;

    /**
     * 对话历史
     */
    @Builder.Default
    private List<Message> messages = new ArrayList<>();

    /**
     * 当前执行计划
     */
    private String currentPlan;

    /**
     * 创建时间
     */
    private LocalDateTime createdAt;

    /**
     * 最后更新时间
     */
    private LocalDateTime updatedAt;

    /**
     * 消息模型
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Message {
        private String role;  // user, assistant, system
        private String content;
        private LocalDateTime timestamp;
    }
}
