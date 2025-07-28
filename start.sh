#!/bin/bash

# Discord Bot 启动脚本
# 支持自动重启和错误处理

set -e

echo "🤖 启动 Discord Bot..."

# 检查环境变量
if [ -z "$DISCORD_TOKEN" ]; then
    echo "❌ 错误: DISCORD_TOKEN 环境变量未设置"
    exit 1
fi

# 创建必要的目录
mkdir -p /app/data/logs

# 设置日志文件
LOG_FILE="/app/data/logs/bot.log"
ERROR_LOG="/app/data/logs/error.log"

# 函数：启动Bot
start_bot() {
    echo "🚀 正在启动 Discord Bot..."
    echo "📅 启动时间: $(date)"
    echo "🔧 Python 版本: $(python --version)"
    echo "📁 工作目录: $(pwd)"
    echo "💾 数据目录: /app/data"
    echo "📝 日志文件: $LOG_FILE"
    echo "=================================="
    
    # 启动Bot并记录日志
    exec python bot.py 2>&1 | tee -a "$LOG_FILE"
}

# 函数：处理信号
cleanup() {
    echo "🛑 收到停止信号，正在关闭Bot..."
    exit 0
}

# 设置信号处理
trap cleanup SIGTERM SIGINT

# 主循环
while true; do
    echo "🔄 启动Bot进程..."
    
    # 启动Bot
    if start_bot; then
        echo "✅ Bot正常退出"
        break
    else
        echo "❌ Bot异常退出，退出码: $?"
        echo "🔄 5秒后重新启动..."
        sleep 5
    fi
done

echo "👋 Bot已完全停止" 