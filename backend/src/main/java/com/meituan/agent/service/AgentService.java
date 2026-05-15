package com.meituan.agent.service;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.meituan.agent.model.AgentRequest;
import com.meituan.agent.model.AgentResponse;
import com.meituan.agent.model.Session;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * Agent 服务
 * 调用 Python Agent 执行任务
 */
@Slf4j
@Service
public class AgentService {

    @Value("${agent.python.script:python}")
    private String pythonScript;

    @Value("${agent.python.path:../agent}")
    private String agentPath;

    @Value("${agent.timeout:30}")
    private int timeout;

    private final SessionService sessionService;

    public AgentService(SessionService sessionService) {
        this.sessionService = sessionService;
    }

    /**
     * 执行 Agent 任务
     */
    public AgentResponse execute(AgentRequest request) {
        // 获取或创建会话
        Session session = sessionService.getOrCreateSession(
                request.getSessionId(),
                request.getUserId()
        );

        // 记录用户消息
        sessionService.addMessage(session.getSessionId(), "user", request.getUserInput());

        try {
            // 调用 Python Agent
            JSONObject result = callPythonAgent(request.getUserInput());

            // 构建响应
            AgentResponse response = buildResponse(result, session.getSessionId());

            // 记录助手响应
            sessionService.addMessage(session.getSessionId(), "assistant",
                    response.getNotification() != null ? response.getNotification() : "任务执行完成");

            return response;

        } catch (Exception e) {
            log.error("Agent 执行失败", e);

            // 返回错误响应
            return AgentResponse.builder()
                    .status("error")
                    .sessionId(session.getSessionId())
                    .errorMessage("服务暂时不可用，请稍后重试")
                    .build();
        }
    }

    /**
     * 调用 Python Agent
     */
    private JSONObject callPythonAgent(String userInput) throws IOException, InterruptedException {
        // 构建命令
        String[] command = {
                pythonScript,
                "-c",
                String.format(
                        "import asyncio, json, sys; sys.path.insert(0, '%s'); " +
                                "from agent.main import create_agent; " +
                                "agent = create_agent(llm_provider='mock'); " +
                                "result = asyncio.run(agent.run('%s')); " +
                                "print(json.dumps(result, ensure_ascii=False))",
                        agentPath,
                        userInput.replace("'", "\\'")
                )
        };

        // 执行命令
        ProcessBuilder processBuilder = new ProcessBuilder(command);
        processBuilder.redirectErrorStream(true);
        Process process = processBuilder.start();

        // 读取输出
        StringBuilder output = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
            String line;
            while ((line = reader.readLine()) != null) {
                output.append(line);
            }
        }

        // 等待完成
        boolean completed = process.waitFor(timeout, TimeUnit.SECONDS);
        if (!completed) {
            process.destroyForcibly();
            throw new RuntimeException("Agent 执行超时");
        }

        // 解析结果
        String outputStr = output.toString().trim();
        log.info("Python Agent 输出: {}", outputStr);

        return JSON.parseObject(outputStr);
    }

    /**
     * 构建响应
     */
    private AgentResponse buildResponse(JSONObject result, String sessionId) {
        String status = result.getString("status");

        // 解析任务摘要
        ArrayList<AgentResponse.TaskSummary> tasks = new ArrayList<>();
        JSONObject summary = result.getJSONObject("summary");
        if (summary != null) {
            var taskList = summary.getJSONArray("tasks");
            if (taskList != null) {
                for (int i = 0; i < taskList.size(); i++) {
                    JSONObject task = taskList.getJSONObject(i);
                    tasks.add(AgentResponse.TaskSummary.builder()
                            .taskId(task.getString("task_id"))
                            .name(task.getString("name"))
                            .status(task.getString("status"))
                            .build());
                }
            }
        }

        // 构建通知消息
        String notification = buildNotification(status, result);

        return AgentResponse.builder()
                .status(status)
                .sessionId(sessionId)
                .tasks(tasks)
                .results(result.getJSONObject("results"))
                .notification(notification)
                .build();
    }

    /**
     * 构建通知消息
     */
    private String buildNotification(String status, JSONObject result) {
        if ("success".equals(status)) {
            return "任务执行成功！";
        } else if ("partial".equals(status)) {
            return "部分任务执行成功，请查看详情。";
        } else if ("replan_needed".equals(status)) {
            String reason = result.getString("reason");
            return "检测到环境变化（" + reason + "），正在为您重新规划行程...";
        } else {
            return "任务执行完成，请查看详情。";
        }
    }
}
