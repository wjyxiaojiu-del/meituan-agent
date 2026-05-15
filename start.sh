#!/bin/bash
echo ""
echo "========================================"
echo "  美团 AI Agent — 启动脚本"
echo "========================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到 Python3，请先安装 Python 3.10+"
    exit 1
fi

# 安装依赖
echo "[1/3] 检查依赖..."
pip3 install -r requirements.txt -q

# 检查配置文件
if [ ! -f config.json ] && [ -f config.example.json ]; then
    echo "[提示] 未检测到 config.json，已复制模板"
    cp config.example.json config.json
    echo "       请编辑 config.json 填入 DeepSeek API Key"
    echo "       或不配置，将以 Mock 模式运行（离线演示）"
fi

# 启动后端
echo "[2/3] 启动后端服务..."
echo "[3/3] 后端地址: http://localhost:8080"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""
python3 -m agent.api
