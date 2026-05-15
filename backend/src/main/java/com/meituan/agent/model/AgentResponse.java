package com.meituan.agent.model;

import lombok.Data;
import lombok.Builder;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

import java.util.List;
import java.util.Map;

/**
 * Agent 响应模型
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AgentResponse {

    /**
     * 响应状态: success, partial, error, replan_needed
     */
    private String status;

    /**
     * 会话 ID
     */
    private String sessionId;

    /**
     * 任务执行摘要
     */
    private List<TaskSummary> tasks;

    /**
     * 执行结果
     */
    private Map<String, Object> results;

    /**
     * 用户通知消息
     */
    private String notification;

    /**
     * 错误信息（如果有）
     */
    private String errorMessage;

    /**
     * 任务摘要
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class TaskSummary {
        private String taskId;
        private String name;
        private String status;
        private String result;
    }
}
