"""
简化版 Python 后端
支持计划确认流程：规划 → 确认 → 执行
"""

import asyncio
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, ".")

from agent.main import create_agent

# 创建 Agent 实例（默认使用 config.json 中的 LLM 配置）
agent = create_agent()


class AgentHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/agent/health":
            self.send_json_response({
                "status": "ok",
                "service": "meituan-agent-backend",
                "version": "2.0.0",
            })
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path == "/api/agent/execute":
            self._handle_execute()
        elif self.path == "/api/agent/confirm":
            self._handle_confirm()
        else:
            self.send_error(404, "Not Found")

    def _handle_execute(self):
        """处理规划请求（第一步：生成方案）"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)

            user_input = data.get("userInput", "")
            session_id = data.get("sessionId")

            if not user_input:
                self.send_json_response({
                    "status": "error",
                    "message": "请输入您的需求",
                }, 400)
                return

            print(f"\n[规划请求] {user_input}")
            result = asyncio.run(agent.run(user_input, session_id))

            response = {
                "status": result.get("status"),
                "sessionId": result.get("session_id"),
                "planSummary": result.get("plan_summary"),
                "route": result.get("route"),
                "story": result.get("story"),
                "tasks": result.get("tasks_preview", []),
            }

            print(f"[规划完成] 状态={response['status']}, 任务数={len(response['tasks'])}")
            self.send_json_response(response)

        except Exception as e:
            print(f"[错误] {e}")
            self.send_json_response({
                "status": "error",
                "message": str(e),
            }, 500)

    def _handle_confirm(self):
        """处理确认请求（第二步：确认后执行）"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)

            session_id = data.get("sessionId")
            confirmed = data.get("confirmed", True)

            if not session_id:
                self.send_json_response({
                    "status": "error",
                    "message": "缺少 sessionId",
                }, 400)
                return

            print(f"\n[确认请求] session={session_id}, confirmed={confirmed}")

            # 从 session 获取待执行任务（execute_plan 会清理 pending_tasks）
            session = agent.session_manager.get_session(session_id)
            pending_tasks = session.context.get("pending_tasks", []) if session else []

            result = asyncio.run(agent.confirm_and_execute(session_id, confirmed))

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

            print(f"[执行完成] 状态={response['status']}")
            self.send_json_response(response)

        except Exception as e:
            print(f"[错误] {e}")
            self.send_json_response({
                "status": "error",
                "message": str(e),
            }, 500)

    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    port = 8080
    server = HTTPServer(("0.0.0.0", port), AgentHandler)
    print(f"\n{'='*60}")
    print(f"  美团 AI Agent 后端服务 v2.0")
    print(f"  地址: http://localhost:{port}")
    print(f"  健康检查: GET  /api/agent/health")
    print(f"  规划请求: POST /api/agent/execute")
    print(f"  确认执行: POST /api/agent/confirm")
    print(f"{'='*60}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.shutdown()


if __name__ == "__main__":
    main()
