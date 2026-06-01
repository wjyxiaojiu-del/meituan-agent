"""
FastAPI 后端服务
统一后端：静态文件服务 + Agent API
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from typing import Optional, Dict, Any
import os
import logging
import json
import uuid
import asyncio

from .main import create_agent
from .core.session import SessionManager, SQLiteSessionManager
from .core.context import set_trace_id, set_session_id, reset_context

logger = logging.getLogger(__name__)

app = FastAPI(title="美团 AI Agent", version="2.2")

from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    msg = "参数错误"
    if errors:
        loc = errors[0].get("loc", [])
        raw = errors[0].get("msg", "")
        if "userInput" in loc:
            msg = raw
        elif "sessionId" in loc:
            msg = raw
    return JSONResponse(status_code=400, content={"status": "error", "message": msg})

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    """为每个请求生成 trace ID，并设置到上下文"""
    trace_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
    request.state.trace_id = trace_id
    reset_context()
    set_trace_id(trace_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = trace_id
    return response

# Simple rate limiter: 100 req/min per IP on API endpoints
_rate_store: Dict[str, list] = {}
_RATE_WINDOW = 60  # seconds
_RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "100"))  # configurable


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        ip = request.client.host if request.client else "unknown"
        if ip in ("127.0.0.1", "::1"):
            return await call_next(request)
        import time
        now = time.time()
        bucket = _rate_store.setdefault(ip, [])
        bucket[:] = [t for t in bucket if now - t < _RATE_WINDOW]
        if len(bucket) >= _RATE_LIMIT:
            return JSONResponse(
                status_code=429,
                content={"status": "error", "message": "请求过于频繁，请稍后重试"},
            )
        bucket.append(now)
    return await call_next(request)


# 会话管理器：优先使用 SQLite 持久化，回退内存存储
_session_db = os.environ.get("SESSION_DB_PATH", "data/sessions.db")
try:
    shared_session_manager = SQLiteSessionManager(db_path=_session_db)
    logger.info(f"SQLite 会话持久化已启用: {_session_db}")
except Exception as e:
    logger.warning(f"SQLite 初始化失败，使用内存存储: {e}")
    shared_session_manager = SessionManager()

# 静态文件目录
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")


def _sanitize(obj: Any) -> Any:
    """递归清理字符串中的无效 Unicode 代理字符"""
    if isinstance(obj, str):
        return obj.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


class ExecuteRequest(BaseModel):
    userInput: str
    sessionId: Optional[str] = None
    enableStory: Optional[bool] = None

    @field_validator("userInput")
    @classmethod
    def validate_user_input(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("请输入您的需求")
        if len(v) > 500:
            raise ValueError("输入内容过长，请控制在 500 字以内")
        return v


class ConfirmRequest(BaseModel):
    sessionId: str
    confirmed: bool = True

    @field_validator("sessionId")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("sessionId 不能为空")
        return v.strip()


class ContinueRequest(BaseModel):
    userInput: str
    sessionId: str

    @field_validator("userInput")
    @classmethod
    def validate_user_input(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("请输入您的需求")
        if len(v) > 500:
            raise ValueError("输入内容过长，请控制在 500 字以内")
        return v

    @field_validator("sessionId")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("sessionId 不能为空")
        return v.strip()


@app.get("/api/agent/health")
async def health():
    # 检测 LLM 模式
    llm_mode = os.environ.get("LLM_MODE", "auto")
    api_key = os.environ.get("LLM_API_KEY", "")
    if llm_mode == "mock" or (llm_mode == "auto" and not api_key):
        effective_mode = "mock"
    else:
        effective_mode = "live"

    # 会话统计
    session_count = 0
    db_status = "ok"
    try:
        if isinstance(shared_session_manager, SQLiteSessionManager):
            session_count = len(shared_session_manager.sessions)
        else:
            session_count = len(shared_session_manager.sessions)
    except Exception:
        db_status = "error"

    # 工具统计
    from .main import create_agent
    tools_count = 6  # 默认 6 个工具

    return {
        "status": "ok",
        "service": "meituan-agent-backend",
        "version": "2.2.0",
        "llm_mode": effective_mode,
        "llm_provider": os.environ.get("LLM_PROVIDER", "mock"),
        "session_count": session_count,
        "db_status": db_status,
        "tools_registered": tools_count,
    }


@app.get("/api/agent/sessions")
async def list_sessions(limit: int = 20):
    """列出最近的会话"""
    try:
        sessions = shared_session_manager.list_sessions(limit=limit)
        return _sanitize(sessions)
    except Exception as e:
        logger.error(f"[会话列表错误] {e}")
        return []


@app.get("/api/pois")
async def get_pois():
    """返回所有 POI 数据，供前端地图使用"""
    from .core.poi_data import load_all_pois
    pois = load_all_pois()
    return _sanitize([
        {
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "rating": p.rating,
            "review_count": p.review_count,
            "location": p.location,
            "address": p.address,
            "price_per_person": p.price_per_person,
            "coupon_price": p.coupon_price,
            "original_price": p.original_price,
            "tags": p.tags,
        }
        for p in pois
    ])


class OptimizeRouteRequest(BaseModel):
    poiIds: list


@app.post("/api/optimize-route")
async def optimize_route(req: OptimizeRouteRequest):
    """接收 POI ID 列表，返回最优排序 + 真实路线数据"""
    from .core.poi_data import load_all_pois
    from .core.route_planner import RoutePlanner, RouteConstraints
    from datetime import datetime

    all_pois = load_all_pois()
    poi_map = {p.id: p for p in all_pois}

    # 过滤出有效的 POI
    selected = [poi_map[pid] for pid in req.poiIds if pid in poi_map]
    if len(selected) < 2:
        return JSONResponse(
            status_code=400,
            content=_sanitize({"error": "至少需要 2 个站点", "route": []}),
        )

    # 用路线规划器做 TSP 优化
    rp = RoutePlanner()
    rp.load_mock_data(all_pois)

    constraints = RouteConstraints(
        start_time=datetime.now().replace(hour=14, minute=0, second=0, microsecond=0),
        max_duration=600,
        max_budget=99999,
        group_size=2,
        pace="normal",
    )

    # 对选中的 POI 做贪心+2-opt 优化
    candidate_ids = [p.id for p in selected]
    route, stats = rp.plan_route(candidate_ids, constraints)

    if not route:
        # 降级：按原始顺序
        route_data = [
            {
                "poi_id": p.id, "poi_name": p.name, "category": p.category,
                "location": p.location, "price_per_person": p.price_per_person,
                "coupon_price": p.coupon_price, "original_price": p.original_price,
                "rating": p.rating, "address": p.address,
            }
            for p in selected
        ]
        return _sanitize({"route": route_data, "stats": {}})

    route_data = rp.get_route_for_planner(route)
    return _sanitize({"route": route_data, "stats": stats})


@app.post("/api/agent/execute")
async def execute(req: ExecuteRequest):
    """规划请求：生成方案（等待确认）"""
    if not req.userInput or not req.userInput.strip():
        return JSONResponse(
            status_code=400,
            content=_sanitize({"status": "error", "message": "请输入您的需求"}),
        )

    try:
        logger.info(f"[规划请求] {req.userInput}")
        agent = create_agent(session_manager=shared_session_manager, live=os.environ.get("LLM_MODE") == "live")
        result = await asyncio.wait_for(agent.run(req.userInput, req.sessionId, enable_story=req.enableStory), timeout=60)

        response = {
            "status": result.get("status"),
            "sessionId": result.get("session_id"),
            "planSummary": result.get("plan_summary"),
            "route": result.get("route"),
            "routeStats": result.get("route_stats"),
            "story": result.get("story"),
            "tasks": result.get("tasks_preview", []),
            "llmStatus": getattr(agent.llm_client, '_last_status', 'unknown'),
            "llmError": getattr(agent.llm_client, '_last_error', ''),
        }

        logger.info(f"[规划完成] 状态={response['status']}, 任务数={len(response['tasks'])}")
        return _sanitize(response)

    except asyncio.TimeoutError:
        logger.error(f"[规划超时] {req.userInput}")
        return JSONResponse(
            status_code=504,
            content=_sanitize({"status": "timeout", "message": "请求超时，请重试"}),
        )
    except Exception as e:
        logger.error(f"[规划错误] {e}")
        return JSONResponse(
            status_code=500,
            content=_sanitize({"status": "error", "message": str(e)}),
        )


@app.post("/api/agent/execute/stream")
async def execute_stream(req: ExecuteRequest):
    """流式规划请求：SSE 逐步返回思考过程和结果"""
    if not req.userInput or not req.userInput.strip():
        return JSONResponse(
            status_code=400,
            content=_sanitize({"status": "error", "message": "请输入您的需求"}),
        )

    agent = create_agent(session_manager=shared_session_manager, live=os.environ.get("LLM_MODE") == "live")

    async def event_generator():
        try:
            # 心跳任务：每 15 秒发送一次心跳，避免代理超时
            heartbeat_task = asyncio.create_task(_heartbeat_loop())
            try:
                async for event in agent.run_stream(req.userInput, req.sessionId, enable_story=req.enableStory):
                    yield f"data: {json.dumps(_sanitize(event), ensure_ascii=False)}\n\n"
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
        except Exception as e:
            logger.error(f"[流式错误] {e}")
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)}, ensure_ascii=False)}\n\n"

    async def _heartbeat_loop():
        """心跳循环：每 15 秒发送 SSE 注释保持连接"""
        while True:
            await asyncio.sleep(15)
            # 心跳通过 yield 无法从外部注入，这里仅用于防止生成器被 GC
            # 实际心跳通过 nginx 等反向代理配置实现
            logger.debug("[heartbeat] keeping connection alive")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/agent/continue")
async def continue_conversation_endpoint(req: ContinueRequest):
    """多轮对话端点：识别修改请求 → 局部 patch；否则普通对话回复"""
    if not req.userInput or not req.userInput.strip():
        return JSONResponse(
            status_code=400,
            content=_sanitize({"status": "error", "message": "请输入您的需求"}),
        )
    try:
        logger.info(f"[继续对话] session={req.sessionId} input={req.userInput}")
        agent = create_agent(
            session_manager=shared_session_manager,
            live=os.environ.get("LLM_MODE") == "live",
        )
        result = await asyncio.wait_for(
            agent.continue_conversation(req.userInput, req.sessionId),
            timeout=60,
        )
        response = {
            "status": result.get("status"),
            "sessionId": result.get("session_id"),
            "actionType": result.get("action_type"),
            "changeLog": result.get("change_log"),
            "planSummary": result.get("plan_summary"),
            "reply": result.get("reply"),
            "route": result.get("route"),
            "routeStats": result.get("route_stats"),
            "story": result.get("story"),
            "tasks": result.get("tasks_preview", []),
        }
        logger.info(f"[继续对话完成] status={response['status']} action={response.get('actionType')}")
        return _sanitize(response)
    except asyncio.TimeoutError:
        logger.error(f"[继续对话超时] session={req.sessionId}")
        return JSONResponse(
            status_code=504,
            content=_sanitize({"status": "timeout", "message": "请求超时，请重试"}),
        )
    except Exception as e:
        logger.error(f"[继续对话错误] {e}")
        return JSONResponse(
            status_code=500,
            content=_sanitize({"status": "error", "message": str(e)}),
        )


@app.post("/api/agent/confirm")
async def confirm(req: ConfirmRequest):
    """确认请求：确认后执行 / 取消"""
    try:
        logger.info(f"[确认请求] session={req.sessionId}, confirmed={req.confirmed}")
        agent = create_agent(session_manager=shared_session_manager, live=os.environ.get("LLM_MODE") == "live")

        # 从 session 获取待执行任务（execute_plan 会清理 pending_tasks）
        session = shared_session_manager.get_session(req.sessionId)
        pending_tasks = session.context.get("pending_tasks", []) if session else []

        result = await asyncio.wait_for(agent.confirm_and_execute(req.sessionId, confirmed=req.confirmed), timeout=60)

        # 构建任务列表：合并原始任务信息和执行结果
        results_map = result.get("results", {})
        tasks_list = []
        for t in pending_tasks:
            task_id = t.task_id
            task_result = results_map.get(task_id, {})
            tasks_list.append({
                "task_id": task_id,
                "name": task_result.get("task_name") or t.name,
                "tool_name": t.tool_name,
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
        return _sanitize(response)

    except asyncio.TimeoutError:
        logger.error(f"[确认超时] session={req.sessionId}")
        return JSONResponse(
            status_code=504,
            content=_sanitize({"status": "timeout", "message": "执行超时，请重试"}),
        )
    except Exception as e:
        logger.error(f"[确认错误] {e}")
        return JSONResponse(
            status_code=500,
            content=_sanitize({"status": "error", "message": str(e)}),
        )


@app.get("/")
async def root():
    """提供前端页面"""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.isfile(index_path):
        raise HTTPException(status_code=404, detail="前端文件未找到")
    return FileResponse(index_path, media_type="text/html")


# 静态文件挂载（放在路由之后，避免覆盖 API）
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
