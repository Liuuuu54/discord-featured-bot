@echo off
chcp 65001 >nul
echo 🤖 Discord Bot 启动脚本 (Windows)
echo.

REM 检查是否存在 .env 文件
if not exist ".env" (
    echo ❌ 错误: 找不到 .env 文件
    echo 📝 请复制 env_example.txt 为 .env 并设置您的 Discord Bot Token
    pause
    exit /b 1
)

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: Python 未安装或不在 PATH 中
    echo 📥 请先安装 Python 3.8+
    pause
    exit /b 1
)

REM 检查依赖是否安装
echo 🔍 检查依赖包...
python -c "import discord" >nul 2>&1
if errorlevel 1 (
    echo 📦 正在安装依赖包...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ 依赖安装失败
        pause
        exit /b 1
    )
)

REM 创建数据目录
if not exist "data" mkdir data
if not exist "data\logs" mkdir data\logs

echo 🚀 启动 Discord Bot...
echo 📅 启动时间: %date% %time%
echo 📁 工作目录: %cd%
echo 💾 数据目录: %cd%\data
echo 📝 日志文件: %cd%\data\logs\bot.log
echo ==================================

REM 启动 Bot
python bot.py

echo.
echo 👋 Bot 已停止
pause 