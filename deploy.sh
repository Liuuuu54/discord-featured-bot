#!/bin/bash

# Discord Bot Docker deployment script.
# ASCII-only output keeps VPS consoles readable even when UTF-8 is not configured.

set -e

export LANG="${LANG:-C.UTF-8}"
export LC_ALL="${LC_ALL:-C.UTF-8}"
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_NAME="dc-bot"
CONTAINER_NAME="dc-bot"

print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

check_docker() {
    print_message "$BLUE" "[INFO] Checking Docker environment..."

    if ! command -v docker &> /dev/null; then
        print_message "$RED" "[ERROR] Docker is not installed"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        print_message "$RED" "[ERROR] Docker Compose is not installed"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        print_message "$RED" "[ERROR] Docker service is not running"
        print_message "$YELLOW" "Run:"
        echo "sudo systemctl start docker"
        echo "sudo systemctl enable docker"
        exit 1
    fi

    print_message "$BLUE" "[INFO] Docker versions:"
    docker --version
    docker-compose --version
    print_message "$GREEN" "[OK] Docker environment ready"
}

check_env() {
    print_message "$BLUE" "[INFO] Checking environment..."

    if [ ! -f ".env" ]; then
        print_message "$YELLOW" "[WARN] .env file not found"
        if [ -f "env_example.txt" ]; then
            print_message "$BLUE" "[INFO] Copying env_example.txt to .env"
            cp env_example.txt .env
            print_message "$YELLOW" "Edit .env and set DISCORD_TOKEN, then rerun this script"
            exit 1
        fi
        print_message "$RED" "[ERROR] Environment template not found"
        exit 1
    fi

    if ! grep -q "DISCORD_TOKEN=" .env || grep -q "DISCORD_TOKEN=$" .env; then
        print_message "$RED" "[ERROR] DISCORD_TOKEN is missing in .env"
        print_message "$YELLOW" "Current .env:"
        cat .env
        exit 1
    fi

    print_message "$BLUE" "[INFO] Environment summary:"
    echo "DISCORD_TOKEN: $(grep DISCORD_TOKEN .env | cut -d'=' -f2 | head -c 10)..."
    echo "Admin roles: configured in config.py"
    echo "Appreciator settings: configured in config.py"
    print_message "$GREEN" "[OK] Environment ready"
}

build_image() {
    print_message "$BLUE" "[INFO] Building Docker image..."

    for required_file in Dockerfile docker-compose.yml requirements.txt; do
        if [ ! -f "$required_file" ]; then
            print_message "$RED" "[ERROR] Missing $required_file"
            exit 1
        fi
    done

    print_message "$BLUE" "[INFO] Build inputs:"
    echo "Dockerfile: $(ls -la Dockerfile)"
    echo "docker-compose.yml: $(ls -la docker-compose.yml)"
    echo "requirements.txt: $(ls -la requirements.txt)"

    docker-compose build --no-cache
    if [ $? -ne 0 ]; then
        print_message "$RED" "[ERROR] Docker image build failed"
        print_message "$YELLOW" "[INFO] Re-running build with plain progress:"
        docker-compose build --no-cache --progress=plain
        exit 1
    fi

    print_message "$GREEN" "[OK] Docker image built"
}

start_service() {
    print_message "$BLUE" "[INFO] Starting Discord Bot..."

    if ! docker images | grep -q "discord-featured-bot"; then
        print_message "$YELLOW" "[WARN] Image not found, building first..."
        build_image
    fi

    mkdir -p data/logs

    docker-compose up -d
    if [ $? -ne 0 ]; then
        print_message "$RED" "[ERROR] Startup failed"
        docker-compose logs
        exit 1
    fi

    sleep 3

    if docker-compose ps | grep -q "Up"; then
        print_message "$GREEN" "[OK] Discord Bot started"
        docker-compose ps
    else
        print_message "$RED" "[ERROR] Container failed to start"
        docker-compose logs
        exit 1
    fi
}

stop_service() {
    print_message "$YELLOW" "[INFO] Stopping Discord Bot..."
    docker-compose down
    print_message "$GREEN" "[OK] Discord Bot stopped"
}

restart_service() {
    print_message "$BLUE" "[INFO] Restarting Discord Bot..."
    docker-compose restart
    print_message "$GREEN" "[OK] Discord Bot restarted"
}

view_logs() {
    print_message "$BLUE" "[INFO] Showing Discord Bot logs..."

    if ! docker-compose ps | grep -q "Up"; then
        print_message "$YELLOW" "[WARN] Container is not running; showing recent logs"
        docker-compose logs --tail=50
    else
        print_message "$BLUE" "[INFO] Following logs. Press Ctrl+C to exit."
        docker-compose logs -f
    fi
}

show_status() {
    print_message "$BLUE" "[INFO] Discord Bot status:"
    docker-compose ps
    echo
    print_message "$BLUE" "[INFO] Container status:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo
    print_message "$BLUE" "[INFO] Container resource usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" 2>/dev/null || echo "Cannot read resource usage"
    echo
    print_message "$BLUE" "[INFO] Recent logs:"
    docker-compose logs --tail=10
}

cleanup() {
    print_message "$YELLOW" "[INFO] Cleaning Docker resources..."
    docker-compose down --volumes --remove-orphans
    docker system prune -f
    print_message "$GREEN" "[OK] Cleanup complete"
}

backup_data() {
    local backup_dir="backup_$(date +%Y%m%d_%H%M%S)"
    print_message "$BLUE" "[INFO] Backing up data to $backup_dir..."

    mkdir -p "$backup_dir"
    if [ -d "data" ]; then
        cp -r data "$backup_dir/"
        print_message "$GREEN" "[OK] Data backup complete: $backup_dir"
    else
        print_message "$YELLOW" "[WARN] Data directory not found"
    fi
}

debug_info() {
    print_message "$BLUE" "[INFO] System debug info:"
    echo "OS: $(uname -a)"
    echo "Docker: $(docker --version)"
    echo "Docker Compose: $(docker-compose --version)"
    echo "Current directory: $(pwd)"
    echo "Locale: LANG=${LANG:-unset}, LC_ALL=${LC_ALL:-unset}"
    echo "Files:"
    ls -la
    echo
    print_message "$BLUE" "[INFO] Docker images:"
    docker images
    echo
    print_message "$BLUE" "[INFO] Docker containers:"
    docker ps -a
    echo
    print_message "$BLUE" "[INFO] Docker networks:"
    docker network ls
    echo
    if [ -f ".env" ]; then
        print_message "$BLUE" "[INFO] .env contents:"
        cat .env
    fi
    echo
    print_message "$BLUE" "[INFO] System resources:"
    echo "Disk: $(df -h .)"
    echo "Memory: $(free -h)"
    echo "Ports: Discord Bot does not listen on local ports"
}

show_help() {
    echo "Discord Bot Docker deployment script"
    echo
    echo "Usage: $0 [command]"
    echo
    echo "Commands:"
    echo "  start     Start Discord Bot"
    echo "  stop      Stop Discord Bot"
    echo "  restart   Restart Discord Bot"
    echo "  build     Build Docker image"
    echo "  deploy    Deploy (build + start)"
    echo "  logs      Show logs"
    echo "  status    Show status"
    echo "  backup    Back up data"
    echo "  cleanup   Clean Docker resources"
    echo "  debug     Show debug info"
    echo "  help      Show this help"
    echo
}

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
            print_message "$GREEN" "[OK] Discord Bot deployment complete"
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

main "$@"
