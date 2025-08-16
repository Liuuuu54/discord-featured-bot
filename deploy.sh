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
    print_message $BLUE "🔍 检查 Docker 环境..."
    
    if ! command -v docker &> /dev/null; then
        print_message $RED "❌ Docker 未安装！请先安装 Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_message $RED "❌ Docker Compose 未安装！请先安装 Docker Compose"
        exit 1
    fi
    
    # 检查 Docker 服务是否运行
    if ! docker info &> /dev/null; then
        print_message $RED "❌ Docker 服务未运行！"
        print_message $YELLOW "请运行以下命令启动 Docker:"
        echo "sudo systemctl start docker"
        echo "sudo systemctl enable docker"
        exit 1
    fi
    
    # 检查 Docker 版本
    print_message $BLUE "📋 Docker 版本信息:"
    docker --version
    docker-compose --version
    
    print_message $GREEN "✅ Docker 环境检查通过"
}

# 函数：检查环境变量
check_env() {
    print_message $BLUE "🔍 检查环境变量..."
    
    if [ ! -f ".env" ]; then
        print_message $YELLOW "⚠️  未找到 .env 文件"
        if [ -f "env_example.txt" ]; then
            print_message $BLUE "📝 正在复制 env_example.txt 为 .env"
            cp env_example.txt .env
            print_message $YELLOW "请编辑 .env 文件并设置您的 DISCORD_TOKEN"
            print_message $BLUE "然后重新运行此脚本"
            exit 1
        else
            print_message $RED "❌ 未找到环境变量配置文件"
            exit 1
        fi
    fi
    
    # 检查DISCORD_TOKEN是否设置
    if ! grep -q "DISCORD_TOKEN=" .env || grep -q "DISCORD_TOKEN=$" .env; then
        print_message $RED "❌ 请在 .env 文件中设置 DISCORD_TOKEN"
        print_message $YELLOW "当前 .env 文件内容:"
        cat .env
        exit 1
    fi
    
    # 检查必要的环境变量
    print_message $BLUE "📋 环境变量检查:"
    echo "DISCORD_TOKEN: $(grep DISCORD_TOKEN .env | cut -d'=' -f2 | head -c 10)..."
    
    print_message $GREEN "✅ 环境变量检查通过"
    print_message $BLUE "📋 配置检查:"
    echo "管理组角色: 在 config.py 中设置"
    echo "鉴赏家配置: 在 config.py 中设置"
}

# 函数：构建镜像
build_image() {
    print_message $BLUE "🔨 正在构建 Docker 镜像..."
    
    # 检查是否有 Dockerfile
    if [ ! -f "Dockerfile" ]; then
        print_message $RED "❌ 未找到 Dockerfile"
        exit 1
    fi
    
    # 检查是否有 docker-compose.yml
    if [ ! -f "docker-compose.yml" ]; then
        print_message $RED "❌ 未找到 docker-compose.yml"
        exit 1
    fi
    
    # 检查是否有 requirements.txt
    if [ ! -f "requirements.txt" ]; then
        print_message $RED "❌ 未找到 requirements.txt"
        exit 1
    fi
    
    print_message $BLUE "📋 构建配置检查:"
    echo "Dockerfile: $(ls -la Dockerfile)"
    echo "docker-compose.yml: $(ls -la docker-compose.yml)"
    echo "requirements.txt: $(ls -la requirements.txt)"
    
    docker-compose build --no-cache
    if [ $? -ne 0 ]; then
        print_message $RED "❌ 镜像构建失败"
        print_message $YELLOW "查看构建日志:"
        docker-compose build --no-cache --progress=plain
        exit 1
    fi
    
    print_message $GREEN "✅ 镜像构建完成"
}

# 函数：启动服务
start_service() {
    print_message $BLUE "🚀 正在启动 Discord Bot..."
    
    # 检查镜像是否存在
    if ! docker images | grep -q "discord-featured-bot"; then
        print_message $YELLOW "⚠️  镜像不存在，正在构建..."
        build_image
    fi
    
    # 检查端口是否被占用
    if netstat -tuln | grep -q ":80 "; then
        print_message $YELLOW "⚠️  端口 80 可能被占用"
    fi
    
    # 创建数据目录
    mkdir -p data/logs
    
    docker-compose up -d
    if [ $? -ne 0 ]; then
        print_message $RED "❌ 启动失败"
        print_message $YELLOW "查看详细错误信息:"
        docker-compose logs
        exit 1
    fi
    
    # 等待几秒让容器完全启动
    sleep 3
    
    # 检查容器状态
    if docker-compose ps | grep -q "Up"; then
        print_message $GREEN "✅ Discord Bot 已启动"
        print_message $BLUE "📊 容器状态:"
        docker-compose ps
    else
        print_message $RED "❌ 容器启动失败"
        print_message $YELLOW "查看容器日志:"
        docker-compose logs
        exit 1
    fi
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
    
    # 检查容器是否运行
    if ! docker-compose ps | grep -q "Up"; then
        print_message $YELLOW "⚠️  容器未运行，显示历史日志:"
        docker-compose logs --tail=50
    else
        print_message $BLUE "🔄 实时日志 (按 Ctrl+C 退出):"
        docker-compose logs -f
    fi
}

# 函数：查看状态
show_status() {
    print_message $BLUE "📊 Discord Bot 状态:"
    docker-compose ps
    echo
    print_message $BLUE "🔍 容器健康状态:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo
    print_message $BLUE "📈 容器资源使用:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" 2>/dev/null || echo "无法获取资源使用信息"
    echo
    print_message $BLUE "📝 最近日志 (最后10行):"
    docker-compose logs --tail=10
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

# 函数：调试信息
debug_info() {
    print_message $BLUE "🔍 系统调试信息:"
    echo "操作系统: $(uname -a)"
    echo "Docker 版本: $(docker --version)"
    echo "Docker Compose 版本: $(docker-compose --version)"
    echo "当前目录: $(pwd)"
    echo "文件列表:"
    ls -la
    echo
    print_message $BLUE "Docker 镜像列表:"
    docker images
    echo
    print_message $BLUE "Docker 容器列表:"
    docker ps -a
    echo
    print_message $BLUE "Docker 网络列表:"
    docker network ls
    echo
    if [ -f ".env" ]; then
        print_message $BLUE ".env 文件内容:"
        cat .env
    fi
    echo
    print_message $BLUE "系统资源信息:"
    echo "磁盘使用: $(df -h .)"
    echo "内存使用: $(free -h)"
    echo "端口占用:"
    netstat -tuln | grep -E ":(80|443|3000|8080)" || echo "未发现相关端口占用"
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
    echo "  debug     显示调试信息"
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
        "debug")
            debug_info
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# 执行主函数
main "$@" 