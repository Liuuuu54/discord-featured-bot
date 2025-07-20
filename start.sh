#!/bin/bash

echo "正在启动留言精選机器人..."
echo

# 检查是否存在.env文件
if [ ! -f ".env" ]; then
    echo "错误: 找不到 .env 文件！"
    echo "请复制 env_example.txt 为 .env 并设置您的 Discord Bot Token"
    exit 1
fi

# 检查是否安装了依赖
if ! python3 -c "import discord" 2>/dev/null; then
    echo "正在安装依赖包..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "安装依赖失败！"
        exit 1
    fi
fi

echo "启动机器人..."
python3 bot.py 