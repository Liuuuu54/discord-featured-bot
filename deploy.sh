#!/bin/bash

# Discord Bot Docker 部署腳本
# 使用方法: ./deploy.sh

set -e

echo "🚀 開始部署 Discord Bot..."

# 檢查環境變量
if [ -z "$DISCORD_TOKEN" ]; then
    echo "❌ 錯誤: DISCORD_TOKEN 環境變量未設置"
    echo "請設置 DISCORD_TOKEN 環境變量:"
    echo "export DISCORD_TOKEN='your_discord_token_here'"
    exit 1
fi

# 創建必要的目錄
echo "📁 創建目錄..."
mkdir -p data logs

# 設置目錄權限
chmod 755 data logs

# 停止現有容器（如果存在）
echo "🛑 停止現有容器..."
docker-compose down || true

# 構建新鏡像
echo "🔨 構建 Docker 鏡像..."
docker-compose build --no-cache

# 啟動服務
echo "🚀 啟動服務..."
docker-compose up -d

# 檢查容器狀態
echo "📊 檢查容器狀態..."
docker-compose ps

# 查看日誌
echo "📋 查看啟動日誌..."
docker-compose logs -f --tail=20

echo "✅ 部署完成！"
echo "📝 查看日誌: docker-compose logs -f"
echo "🛑 停止服務: docker-compose down"
echo "🔄 重啟服務: docker-compose restart" 