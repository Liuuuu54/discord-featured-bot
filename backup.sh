#!/bin/bash

# Discord Bot 数据备份脚本
# 自动备份数据库和日志文件

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
BACKUP_DIR="backups"
DATA_DIR="data"
MAX_BACKUPS=10  # 保留最近10个备份

# 函数：打印带颜色的消息
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# 函数：创建备份目录
create_backup_dir() {
    if [ ! -d "$BACKUP_DIR" ]; then
        mkdir -p "$BACKUP_DIR"
        print_message $BLUE "📁 创建备份目录: $BACKUP_DIR"
    fi
}

# 函数：生成备份文件名
generate_backup_name() {
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    echo "dc_bot_backup_${timestamp}.tar.gz"
}

# 函数：执行备份
perform_backup() {
    local backup_file="$BACKUP_DIR/$(generate_backup_name)"
    
    print_message $BLUE "💾 开始备份数据..."
    print_message $BLUE "📁 备份目录: $DATA_DIR"
    print_message $BLUE "📄 备份文件: $backup_file"
    
    # 检查数据目录是否存在
    if [ ! -d "$DATA_DIR" ]; then
        print_message $YELLOW "⚠️  数据目录不存在: $DATA_DIR"
        return 1
    fi
    
    # 创建备份
    tar -czf "$backup_file" -C . "$DATA_DIR" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        print_message $GREEN "✅ 备份完成: $backup_file"
        
        # 显示备份文件大小
        local size=$(du -h "$backup_file" | cut -f1)
        print_message $BLUE "📊 备份文件大小: $size"
        
        return 0
    else
        print_message $RED "❌ 备份失败"
        return 1
    fi
}

# 函数：清理旧备份
cleanup_old_backups() {
    print_message $BLUE "🧹 清理旧备份文件..."
    
    # 获取备份文件列表并按时间排序
    local backup_files=($(ls -t "$BACKUP_DIR"/dc_bot_backup_*.tar.gz 2>/dev/null || true))
    
    if [ ${#backup_files[@]} -gt $MAX_BACKUPS ]; then
        local files_to_delete=${backup_files[@]:$MAX_BACKUPS}
        
        for file in $files_to_delete; do
            print_message $YELLOW "🗑️  删除旧备份: $(basename "$file")"
            rm -f "$file"
        done
        
        print_message $GREEN "✅ 清理完成，保留最近 $MAX_BACKUPS 个备份"
    else
        print_message $BLUE "📊 当前备份数量: ${#backup_files[@]} (未超过限制: $MAX_BACKUPS)"
    fi
}

# 函数：显示备份列表
list_backups() {
    print_message $BLUE "📋 备份文件列表:"
    echo
    
    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A "$BACKUP_DIR" 2>/dev/null)" ]; then
        print_message $YELLOW "📭 没有找到备份文件"
        return
    fi
    
    local backup_files=($(ls -t "$BACKUP_DIR"/dc_bot_backup_*.tar.gz 2>/dev/null || true))
    
    if [ ${#backup_files[@]} -eq 0 ]; then
        print_message $YELLOW "📭 没有找到备份文件"
        return
    fi
    
    printf "%-30s %-15s %-10s\n" "文件名" "大小" "创建时间"
    echo "------------------------------------------------------------"
    
    for file in "${backup_files[@]}"; do
        local filename=$(basename "$file")
        local size=$(du -h "$file" | cut -f1)
        local date=$(stat -c %y "$file" | cut -d' ' -f1,2 | cut -d'.' -f1)
        printf "%-30s %-15s %-10s\n" "$filename" "$size" "$date"
    done
}

# 函数：恢复备份
restore_backup() {
    local backup_file="$1"
    
    if [ -z "$backup_file" ]; then
        print_message $RED "❌ 请指定要恢复的备份文件"
        echo "用法: $0 restore <backup_file>"
        return 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        print_message $RED "❌ 备份文件不存在: $backup_file"
        return 1
    fi
    
    print_message $YELLOW "⚠️  即将恢复备份: $backup_file"
    print_message $YELLOW "⚠️  这将覆盖当前的数据目录"
    read -p "确认继续? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_message $BLUE "🔄 正在恢复备份..."
        
        # 停止Bot（如果正在运行）
        if command -v docker-compose &> /dev/null; then
            print_message $BLUE "🛑 停止Discord Bot..."
            docker-compose down 2>/dev/null || true
        fi
        
        # 备份当前数据（如果存在）
        if [ -d "$DATA_DIR" ]; then
            local current_backup="backup_before_restore_$(date +%Y%m%d_%H%M%S).tar.gz"
            print_message $BLUE "💾 备份当前数据: $current_backup"
            tar -czf "$current_backup" -C . "$DATA_DIR" 2>/dev/null || true
        fi
        
        # 删除当前数据目录
        rm -rf "$DATA_DIR"
        
        # 恢复备份
        tar -xzf "$backup_file" -C .
        
        if [ $? -eq 0 ]; then
            print_message $GREEN "✅ 备份恢复完成"
            print_message $BLUE "🚀 可以重新启动Discord Bot"
        else
            print_message $RED "❌ 备份恢复失败"
            return 1
        fi
    else
        print_message $BLUE "❌ 恢复操作已取消"
    fi
}

# 函数：显示帮助
show_help() {
    echo "Discord Bot 数据备份脚本"
    echo
    echo "用法: $0 [命令]"
    echo
    echo "命令:"
    echo "  backup    执行数据备份"
    echo "  list      显示备份列表"
    echo "  restore   恢复指定备份"
    echo "  cleanup   清理旧备份"
    echo "  help      显示此帮助信息"
    echo
    echo "示例:"
    echo "  $0 backup                    # 执行备份"
    echo "  $0 list                      # 显示备份列表"
    echo "  $0 restore backup_file.tar.gz # 恢复指定备份"
    echo "  $0 cleanup                   # 清理旧备份"
    echo
}

# 主函数
main() {
    case "${1:-help}" in
        "backup")
            create_backup_dir
            perform_backup
            cleanup_old_backups
            ;;
        "list")
            list_backups
            ;;
        "restore")
            restore_backup "$2"
            ;;
        "cleanup")
            create_backup_dir
            cleanup_old_backups
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# 执行主函数
main "$@" 