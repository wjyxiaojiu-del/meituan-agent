@echo off
chcp 65001 >nul
echo.
echo ============================================================
echo   美团 AI Agent 后端服务启动脚本
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/2] 检查 Python 环境...
python --version
if errorlevel 1 (
    echo 错误: 未找到 Python
    pause
    exit /b 1
)

echo.
echo [2/2] 启动后端服务...
echo.
echo 服务地址: http://localhost:8080
echo 健康检查: http://localhost:8080/api/agent/health
echo.
echo 按 Ctrl+C 停止服务
echo ============================================================
echo.

python backend_simple.py

pause
