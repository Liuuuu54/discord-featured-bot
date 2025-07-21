#!/bin/bash

# 數據庫備份腳本
# 使用方法: ./backup.sh

set -e

# 設置備份目錄
BACKUP_DIR="./backups"
DATE=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="bot_database_${DATE}.db"

echo "💾 開始備份數據庫..."

# 創建備份目錄
mkdir -p "$BACKUP_DIR"

# 檢查數據庫文件是否存在
if [ ! -f "./data/bot_database.db" ]; then
    echo "❌ 錯誤: 數據庫文件不存在"
    exit 1
fi

# 停止 Bot 容器（確保數據一致性）
echo "🛑 停止 Bot 容器..."
docker-compose stop dc-bot

# 等待一下確保文件寫入完成
sleep 2

# 複製數據庫文件
echo "📋 複製數據庫文件..."
cp "./data/bot_database.db" "$BACKUP_DIR/$BACKUP_FILE"

# 重新啟動 Bot 容器
echo "🚀 重新啟動 Bot 容器..."
docker-compose start dc-bot

# 檢查備份文件
if [ -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
    echo "✅ 備份成功: $BACKUP_DIR/$BACKUP_FILE"
    
    # 顯示文件大小
    FILE_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
    echo "📊 備份文件大小: $FILE_SIZE"
    
    # 列出最近的備份
    echo "📋 最近的備份文件:"
    ls -la "$BACKUP_DIR"/*.db | tail -5
else
    echo "❌ 備份失敗"
    exit 1
fi

echo "🎉 備份完成！" 