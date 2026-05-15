"""
FastAPI 后端服务
替代 backend_simple.py，支持异步处理
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import os
import logging

from .main import create_agent
from .core.session import SessionManager

logger = logging.getLogger(__name__)

app = FastAPI(title="美团 AI Agent", version="2.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 共享 SessionManager（跨请求保持 session 状态）
shared_session_manager = SessionManager()


class ExecuteRequest(BaseModel):
    userInput: str
    sessionId: Optional[str] = None


class ConfirmRequest(BaseModel):
    sessionId: str
    confirmed: bool = True


@app.get("/api/agent/health")
async def health():
    return {
        "status": "ok",
        "service": "meituan-agent-backend",
        "version": "2.0.0",
        "llm_provider": os.environ.get("LLM_PROVIDER", "mock"),
    }


@app.post("/api/agent/execute")
async def execute(req: ExecuteRequest):
    """规划请求：生成方案（等待确认）"""
    if not req.userInput or not req.userInput.strip():
        raise HTTPException(status_code=400, detail="请输入您的需求")

    try:
        logger.info(f"[规划请求] {req.userInput}")
        agent = create_agent(session_manager=shared_session_manager)
        result = await agent.run(req.userInput, req.sessionId)

        response = {
            "status": result.get("status"),
            "sessionId": result.get("session_id"),
            "planSummary": result.get("plan_summary"),
            "route": result.get("route"),
            "story": result.get("story"),
            "tasks": result.get("tasks_preview", []),
        }

        logger.info(f"[规划完成] 状态={response['status']}, 任务数={len(response['tasks'])}")
        return response

    except Exception as e:
        logger.error(f"[规划错误] {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/confirm")
async def confirm(req: ConfirmRequest):
    """确认请求：确认后执行 / 取消"""
    try:
        logger.info(f"[确认请求] session={req.sessionId}, confirmed={req.confirmed}")
        agent = create_agent(session_manager=shared_session_manager)

        # 从 session 获取待执行任务（execute_plan 会清理 pending_tasks）
        session = shared_session_manager.get_session(req.sessionId)
        pending_tasks = session.context.get("pending_tasks", []) if session else []

        result = await agent.confirm_and_execute(req.sessionId, confirmed=req.confirmed)

        # 构建任务列表：合并原始任务信息和执行结果
        results_map = result.get("results", {})
        tasks_list = []
        for t in pending_tasks:
            task_id = t.task_id
            task_result = results_map.get(task_id, {})
            tasks_list.append({
                "task_id": task_id,
                "name": task_result.get("task_name") or t.name,
                "status": "SUCCESS" if task_id in results_map else "PENDING",
            })

        response = {
            "status": result.get("status"),
            "sessionId": result.get("session_id"),
            "results": results_map,
            "shareText": result.get("share_text"),
            "route": result.get("route"),
            "tasks": tasks_list,
        }

        logger.info(f"[执行完成] 状态={response['status']}")
        return response

    except Exception as e:
        logger.error(f"[确认错误] {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
