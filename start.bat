@echo off
echo 正在启动留言精選机器人...
echo.

REM 检查是否存在.env文件
if not exist ".env" (
    echo 错误: 找不到 .env 文件！
    echo 请复制 env_example.txt 为 .env 并设置您的 Discord Bot Token
    pause
    exit /b 1
)

REM 检查是否安装了依赖
python -c "import discord" 2>nul
if errorlevel 1 (
    echo 正在安装依赖包...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo 安装依赖失败！
        pause
        exit /b 1
    )
)

echo 启动机器人...
python bot.py

pause 