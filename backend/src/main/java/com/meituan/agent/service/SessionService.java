package com.meituan.agent.service;

import com.meituan.agent.model.Session;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 会话管理服务
 */
@Service
public class SessionService {

    /**
     * 会话存储（生产环境应使用 Redis）
     */
    private final Map<String, Session> sessions = new ConcurrentHashMap<>();

    /**
     * 创建新会话
     */
    public Session createSession(String userId) {
        String sessionId = UUID.randomUUID().toString().replace("-", "");

        Session session = Session.builder()
                .sessionId(sessionId)
                .userId(userId)
                .status("active")
                .createdAt(LocalDateTime.now())
                .updatedAt(LocalDateTime.now())
                .build();

        sessions.put(sessionId, session);
        return session;
    }

    /**
     * 获取会话
     */
    public Session getSession(String sessionId) {
        return sessions.get(sessionId);
    }

    /**
     * 获取或创建会话
     */
    public Session getOrCreateSession(String sessionId, String userId) {
        if (sessionId != null && sessions.containsKey(sessionId)) {
            Session session = sessions.get(sessionId);
            if ("active".equals(session.getStatus())) {
                return session;
            }
        }
        return createSession(userId);
    }

    /**
     * 添加消息到会话
     */
    public void addMessage(String sessionId, String role, String content) {
        Session session = sessions.get(sessionId);
        if (session != null) {
            Session.Message message = Session.Message.builder()
                    .role(role)
                    .content(content)
                    .timestamp(LocalDateTime.now())
                    .build();

            session.getMessages().add(message);
            session.setUpdatedAt(LocalDateTime.now());
        }
    }

    /**
     * 更新会话状态
     */
    public void updateSessionStatus(String sessionId, String status) {
        Session session = sessions.get(sessionId);
        if (session != null) {
            session.setStatus(status);
            session.setUpdatedAt(LocalDateTime.now());
        }
    }

    /**
     * 更新当前计划
     */
    public void updateCurrentPlan(String sessionId, String plan) {
        Session session = sessions.get(sessionId);
        if (session != null) {
            session.setCurrentPlan(plan);
            session.setUpdatedAt(LocalDateTime.now());
        }
    }

    /**
     * 清理过期会话（简化版）
     */
    public void cleanExpiredSessions() {
        LocalDateTime expireTime = LocalDateTime.now().minusHours(2);
        sessions.entrySet().removeIf(entry ->
                entry.getValue().getUpdatedAt().isBefore(expireTime)
        );
    }
}
