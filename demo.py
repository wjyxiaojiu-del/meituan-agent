"""
美团 AI Agent — 一键验收启动脚本
用法：python demo.py
"""

import os
import sys
import time
import json
import socket
import subprocess
import webbrowser
from pathlib import Path

PORT = 8080
URL = f"http://localhost:{PORT}"


def check_port(port: int) -> bool:
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for_server(url: str, timeout: int = 15) -> bool:
    """等待服务启动"""
    import urllib.request
    import urllib.error

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{url}/api/agent/health", timeout=2)
            return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.5)
    return False


def main():
    print()
    print("=" * 50)
    print("  美团 AI Agent — 自用验收模式")
    print("=" * 50)
    print()

    root = Path(__file__).parent
    os.chdir(root)

    # 1. 检查 Python 版本
    if sys.version_info < (3, 10):
        print("[错误] 需要 Python 3.10+，当前:", sys.version)
        sys.exit(1)

    # 2. 检查 .env 文件
    env_file = root / ".env"
    env_example = root / ".env.example"
    if not env_file.exists() and env_example.exists():
        print("[提示] 未找到 .env，已从 .env.example 复制模板")
        print("       如需使用真实 LLM，请编辑 .env 填入 API Key")
        import shutil
        shutil.copy(env_example, env_file)

    # 3. 检查 config.json
    config_file = root / "config.json"
    config_example = root / "config.example.json"
    if not config_file.exists() and config_example.exists():
        print("[提示] 未找到 config.json，已从模板复制")
        import shutil
        shutil.copy(config_example, config_file)

    # 4. 检测 LLM 模式
    llm_mode = os.environ.get("LLM_MODE", "auto")
    api_key = os.environ.get("LLM_API_KEY", "")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("LLM_MODE="):
                llm_mode = line.split("=", 1)[1].strip().strip('"').strip("'")
            if line.startswith("LLM_API_KEY="):
                api_key = line.split("=", 1)[1].strip().strip('"').strip("'")

    if llm_mode == "mock" or (llm_mode == "auto" and not api_key):
        mode_label = "Mock 离线演示"
        mode_desc = "无需 API Key，结果为模拟数据"
    else:
        mode_label = "Live 真实 LLM"
        mode_desc = "使用 MiMo-v2.5-pro 推理模型"

    print(f"[模式] {mode_label} — {mode_desc}")

    # 5. 检查端口
    if check_port(PORT):
        print(f"[提示] 端口 {PORT} 已被占用，可能服务已在运行")
        print(f"[提示] 直接打开浏览器: {URL}")
        webbrowser.open(URL)
        return

    # 6. 安装依赖（静默）
    print("[准备] 检查依赖...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
        capture_output=True, timeout=60
    )

    # 7. 启动服务
    print(f"[启动] 正在启动服务 (端口 {PORT})...")
    server = subprocess.Popen(
        [sys.executable, "-m", "agent.api"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # 8. 等待服务就绪
    if wait_for_server(URL):
        print(f"[就绪] 服务已启动: {URL}")
        print()

        # 自动打开浏览器
        time.sleep(0.5)
        webbrowser.open(URL)

        # 打印验收提示
        print("=" * 50)
        print("  验收场景（可直接在页面上操作）")
        print("=" * 50)
        print()
        print("  1. 普通吃饭  — 输入「两个人下午想吃个火锅」")
        print("  2. 情侣约会  — 点击「情侣约会」场景卡片")
        print("  3. 朋友聚会  — 输入「6个朋友晚上聚会」")
        print("  4. 预算很紧  — 输入「50块以内带孩子玩」")
        print("  5. 关闭剧情  — 关闭剧情开关 +「下午出去玩」")
        print("  6. 手机模式  — F12 切手机视口，测试重排路线")
        print()
        print(f"  浏览器已打开: {URL}")
        print(f"  按 Ctrl+C 停止服务")
        print()

        try:
            server.wait()
        except KeyboardInterrupt:
            print("\n[停止] 正在关闭服务...")
            server.terminate()
            server.wait(timeout=5)
            print("[完成] 服务已停止")
    else:
        print("[错误] 服务启动超时，请检查日志")
        server.terminate()
        sys.exit(1)


if __name__ == "__main__":
    main()
