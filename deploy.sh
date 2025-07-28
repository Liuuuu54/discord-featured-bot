#!/bin/bash

# Discord Bot Docker 部署脚本
# 支持一键部署、更新和重启

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目信息
PROJECT_NAME="dc-bot"
CONTAINER_NAME="dc-bot"

# 函数：打印带颜色的消息
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# 函数：检查Docker是否安装
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_message $RED "❌ Docker 未安装！请先安装 Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_message $RED "❌ Docker Compose 未安装！请先安装 Docker Compose"
        exit 1
    fi
}

# 函数：检查环境变量
check_env() {
    if [ ! -f ".env" ]; then
        print_message $YELLOW "⚠️  未找到 .env 文件"
        if [ -f "env_example.txt" ]; then
            print_message $BLUE "📝 正在复制 env_example.txt 为 .env"
            cp env_example.txt .env
            print_message $YELLOW "请编辑 .env 文件并设置您的 DISCORD_TOKEN"
            exit 1
        else
            print_message $RED "❌ 未找到环境变量配置文件"
            exit 1
        fi
    fi
    
    # 检查DISCORD_TOKEN是否设置
    if ! grep -q "DISCORD_TOKEN=" .env || grep -q "DISCORD_TOKEN=$" .env; then
        print_message $RED "❌ 请在 .env 文件中设置 DISCORD_TOKEN"
        exit 1
    fi
}

# 函数：构建镜像
build_image() {
    print_message $BLUE "🔨 正在构建 Docker 镜像..."
    docker-compose build --no-cache
    print_message $GREEN "✅ 镜像构建完成"
}

# 函数：启动服务
start_service() {
    print_message $BLUE "🚀 正在启动 Discord Bot..."
    docker-compose up -d
    print_message $GREEN "✅ Discord Bot 已启动"
}

# 函数：停止服务
stop_service() {
    print_message $YELLOW "🛑 正在停止 Discord Bot..."
    docker-compose down
    print_message $GREEN "✅ Discord Bot 已停止"
}

# 函数：重启服务
restart_service() {
    print_message $BLUE "🔄 正在重启 Discord Bot..."
    docker-compose restart
    print_message $GREEN "✅ Discord Bot 已重启"
}

# 函数：查看日志
view_logs() {
    print_message $BLUE "📝 显示 Discord Bot 日志..."
    docker-compose logs -f
}

# 函数：查看状态
show_status() {
    print_message $BLUE "📊 Discord Bot 状态:"
    docker-compose ps
    echo
    print_message $BLUE "🔍 容器健康状态:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

# 函数：清理
cleanup() {
    print_message $YELLOW "🧹 正在清理..."
    docker-compose down --volumes --remove-orphans
    docker system prune -f
    print_message $GREEN "✅ 清理完成"
}

# 函数：备份数据
backup_data() {
    local backup_dir="backup_$(date +%Y%m%d_%H%M%S)"
    print_message $BLUE "💾 正在备份数据到 $backup_dir..."
    
    mkdir -p "$backup_dir"
    if [ -d "data" ]; then
        cp -r data "$backup_dir/"
        print_message $GREEN "✅ 数据备份完成: $backup_dir"
    else
        print_message $YELLOW "⚠️  没有找到数据目录"
    fi
}

# 函数：显示帮助
show_help() {
    echo "Discord Bot Docker 部署脚本"
    echo
    echo "用法: $0 [命令]"
    echo
    echo "命令:"
    echo "  start     启动 Discord Bot"
    echo "  stop      停止 Discord Bot"
    echo "  restart   重启 Discord Bot"
    echo "  build     构建 Docker 镜像"
    echo "  deploy    部署（构建 + 启动）"
    echo "  logs      查看日志"
    echo "  status    查看状态"
    echo "  backup    备份数据"
    echo "  cleanup   清理 Docker 资源"
    echo "  help      显示此帮助信息"
    echo
}

# 主函数
main() {
    case "${1:-help}" in
        "start")
            check_docker
            check_env
            start_service
            ;;
        "stop")
            check_docker
            stop_service
            ;;
        "restart")
            check_docker
            restart_service
            ;;
        "build")
            check_docker
            check_env
            build_image
            ;;
        "deploy")
            check_docker
            check_env
            build_image
            start_service
            print_message $GREEN "🎉 Discord Bot 部署完成！"
            ;;
        "logs")
            check_docker
            view_logs
            ;;
        "status")
            check_docker
            show_status
            ;;
        "backup")
            backup_data
            ;;
        "cleanup")
            check_docker
            cleanup
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# 执行主函数
main "$@" 