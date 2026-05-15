@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   美团 AI Agent — 启动脚本
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: 安装依赖
echo [1/3] 检查依赖...
pip install -r requirements.txt -q

:: 检查配置文件
if not exist config.json (
    if exist config.example.json (
        echo [提示] 未检测到 config.json，已复制模板
        copy config.example.json config.json >nul
        echo        请编辑 config.json 填入 DeepSeek API Key
        echo        或不配置，将以 Mock 模式运行（离线演示）
    )
)

:: 启动后端
echo [2/3] 启动后端服务...
echo [3/3] 后端地址: http://localhost:8080
echo.
echo 按 Ctrl+C 停止服务
echo.
python -m agent.api
