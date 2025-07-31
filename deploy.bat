@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo 🚀 Discord Bot Docker 部署脚本 (Windows)
echo.

REM 检查参数
if "%1"=="" (
    echo 用法: %0 [命令]
    echo.
    echo 命令:
    echo   start     启动 Discord Bot
    echo   stop      停止 Discord Bot
    echo   restart   重启 Discord Bot
    echo   build     构建 Docker 镜像
    echo   deploy    部署（构建 + 启动）
    echo   logs      查看日志
    echo   status    查看状态
    echo   backup    备份数据
    echo   cleanup   清理 Docker 资源
    echo   debug     显示调试信息
    echo   help      显示此帮助信息
    echo.
    pause
    exit /b 0
)

REM 函数：打印带颜色的消息
:print_message
set "color=%1"
set "message=%2"
if "%color%"=="RED" (
    echo ❌ %message%
) else if "%color%"=="GREEN" (
    echo ✅ %message%
) else if "%color%"=="YELLOW" (
    echo ⚠️  %message%
) else if "%color%"=="BLUE" (
    echo 🔍 %message%
) else (
    echo %message%
)
goto :eof

REM 函数：检查Docker环境
:check_docker
call :print_message BLUE "检查 Docker 环境..."

docker --version >nul 2>&1
if errorlevel 1 (
    call :print_message RED "Docker 未安装！请先安装 Docker Desktop"
    echo 📥 下载地址: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

docker-compose --version >nul 2>&1
if errorlevel 1 (
    call :print_message RED "Docker Compose 未安装！"
    pause
    exit /b 1
)

REM 检查 Docker 服务是否运行
docker info >nul 2>&1
if errorlevel 1 (
    call :print_message RED "Docker 服务未运行！"
    call :print_message YELLOW "请启动 Docker Desktop"
    pause
    exit /b 1
)

call :print_message BLUE "Docker 版本信息:"
docker --version
docker-compose --version

call :print_message GREEN "Docker 环境检查通过"
goto :eof

REM 函数：检查环境变量
:check_env
call :print_message BLUE "检查环境变量..."

if not exist ".env" (
    call :print_message YELLOW "未找到 .env 文件"
    if exist "env_example.txt" (
        call :print_message BLUE "正在复制 env_example.txt 为 .env"
        copy env_example.txt .env >nul
        call :print_message YELLOW "请编辑 .env 文件并设置您的 DISCORD_TOKEN"
        call :print_message BLUE "然后重新运行此脚本"
        notepad .env
        pause
        exit /b 1
    ) else (
        call :print_message RED "未找到环境变量配置文件"
        pause
        exit /b 1
    )
)

REM 检查DISCORD_TOKEN是否设置
findstr /C:"DISCORD_TOKEN=" .env | findstr /V /C:"DISCORD_TOKEN=$" >nul
if errorlevel 1 (
    call :print_message RED "请在 .env 文件中设置 DISCORD_TOKEN"
    call :print_message YELLOW "当前 .env 文件内容:"
    type .env
    pause
    exit /b 1
)

call :print_message BLUE "环境变量检查:"
for /f "tokens=1,2 delims==" %%a in ('findstr "DISCORD_TOKEN=" .env') do (
    set "token=%%b"
    set "token=!token:~0,10!..."
    echo DISCORD_TOKEN: !token!
)
for /f "tokens=1,2 delims==" %%a in ('findstr "ADMIN_ROLE_NAMES=" .env') do echo ADMIN_ROLE_NAMES: %%b
for /f "tokens=1,2 delims==" %%a in ('findstr "APPRECIATOR_ROLE_NAME=" .env') do echo APPRECIATOR_ROLE_NAME: %%b

call :print_message GREEN "环境变量检查通过"
goto :eof

REM 函数：构建镜像
:build_image
call :print_message BLUE "正在构建 Docker 镜像..."

if not exist "Dockerfile" (
    call :print_message RED "未找到 Dockerfile"
    pause
    exit /b 1
)

if not exist "docker-compose.yml" (
    call :print_message RED "未找到 docker-compose.yml"
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    call :print_message RED "未找到 requirements.txt"
    pause
    exit /b 1
)

call :print_message BLUE "构建配置检查:"
dir Dockerfile
dir docker-compose.yml
dir requirements.txt

docker-compose build --no-cache
if errorlevel 1 (
    call :print_message RED "镜像构建失败"
    call :print_message YELLOW "查看构建日志:"
    docker-compose build --no-cache --progress=plain
    pause
    exit /b 1
)

call :print_message GREEN "镜像构建完成"
goto :eof

REM 函数：启动服务
:start_service
call :print_message BLUE "正在启动 Discord Bot..."

REM 检查镜像是否存在
docker images | findstr "discord-featured-bot" >nul
if errorlevel 1 (
    call :print_message YELLOW "镜像不存在，正在构建..."
    call :build_image
)

REM 创建数据目录
if not exist "data" mkdir data
if not exist "data\logs" mkdir data\logs

docker-compose up -d
if errorlevel 1 (
    call :print_message RED "启动失败"
    call :print_message YELLOW "查看详细错误信息:"
    docker-compose logs
    pause
    exit /b 1
)

REM 等待几秒让容器完全启动
timeout /t 3 /nobreak >nul

REM 检查容器状态
docker-compose ps | findstr "Up" >nul
if errorlevel 1 (
    call :print_message RED "容器启动失败"
    call :print_message YELLOW "查看容器日志:"
    docker-compose logs
    pause
    exit /b 1
) else (
    call :print_message GREEN "Discord Bot 已启动"
    call :print_message BLUE "容器状态:"
    docker-compose ps
)
goto :eof

REM 函数：停止服务
:stop_service
call :print_message YELLOW "正在停止 Discord Bot..."
docker-compose down
call :print_message GREEN "Discord Bot 已停止"
goto :eof

REM 函数：重启服务
:restart_service
call :print_message BLUE "正在重启 Discord Bot..."
docker-compose restart
call :print_message GREEN "Discord Bot 已重启"
goto :eof

REM 函数：查看日志
:view_logs
call :print_message BLUE "显示 Discord Bot 日志..."

REM 检查容器是否运行
docker-compose ps | findstr "Up" >nul
if errorlevel 1 (
    call :print_message YELLOW "容器未运行，显示历史日志:"
    docker-compose logs --tail=50
) else (
    call :print_message BLUE "实时日志 (按 Ctrl+C 退出):"
    docker-compose logs -f
)
goto :eof

REM 函数：查看状态
:show_status
call :print_message BLUE "Discord Bot 状态:"
docker-compose ps
echo.
call :print_message BLUE "容器健康状态:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.
call :print_message BLUE "容器资源使用:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" 2>nul || echo 无法获取资源使用信息
echo.
call :print_message BLUE "最近日志 (最后10行):"
docker-compose logs --tail=10
goto :eof

REM 函数：清理
:cleanup
call :print_message YELLOW "正在清理..."
docker-compose down --volumes --remove-orphans
docker system prune -f
call :print_message GREEN "清理完成"
goto :eof

REM 函数：备份数据
:backup_data
set "backup_dir=backup_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "backup_dir=%backup_dir: =0%"
call :print_message BLUE "正在备份数据到 %backup_dir%..."

if exist "data" (
    xcopy /E /I data "%backup_dir%\data" >nul
    call :print_message GREEN "数据备份完成: %backup_dir%"
) else (
    call :print_message YELLOW "没有找到数据目录"
)
goto :eof

REM 函数：调试信息
:debug_info
call :print_message BLUE "系统调试信息:"
echo 操作系统: %OS%
echo Docker 版本: 
docker --version
echo Docker Compose 版本:
docker-compose --version
echo 当前目录: %CD%
echo 文件列表:
dir
echo.
call :print_message BLUE "Docker 镜像列表:"
docker images
echo.
call :print_message BLUE "Docker 容器列表:"
docker ps -a
echo.
call :print_message BLUE "Docker 网络列表:"
docker network ls
echo.
if exist ".env" (
    call :print_message BLUE ".env 文件内容:"
    type .env
)
echo.
call :print_message BLUE "系统资源信息:"
echo 磁盘使用:
dir
echo 端口占用:
netstat -an | findstr ":80\|:443\|:3000\|:8080" || echo 未发现相关端口占用
goto :eof

REM 函数：显示帮助
:show_help
echo Discord Bot Docker 部署脚本 (Windows)
echo.
echo 用法: %0 [命令]
echo.
echo 命令:
echo   start     启动 Discord Bot
echo   stop      停止 Discord Bot
echo   restart   重启 Discord Bot
echo   build     构建 Docker 镜像
echo   deploy    部署（构建 + 启动）
echo   logs      查看日志
echo   status    查看状态
echo   backup    备份数据
echo   cleanup   清理 Docker 资源
echo   debug     显示调试信息
echo   help      显示此帮助信息
echo.
goto :eof

REM 根据命令执行相应操作
if "%1"=="start" (
    call :check_docker
    call :check_env
    call :start_service
    goto :end
)

if "%1"=="stop" (
    call :check_docker
    call :stop_service
    goto :end
)

if "%1"=="restart" (
    call :check_docker
    call :restart_service
    goto :end
)

if "%1"=="build" (
    call :check_docker
    call :check_env
    call :build_image
    goto :end
)

if "%1"=="deploy" (
    call :check_docker
    call :check_env
    call :build_image
    call :start_service
    call :print_message GREEN "🎉 Discord Bot 部署完成！"
    goto :end
)

if "%1"=="logs" (
    call :check_docker
    call :view_logs
    goto :end
)

if "%1"=="status" (
    call :check_docker
    call :show_status
    goto :end
)

if "%1"=="backup" (
    call :backup_data
    goto :end
)

if "%1"=="cleanup" (
    call :check_docker
    call :cleanup
    goto :end
)

if "%1"=="debug" (
    call :debug_info
    goto :end
)

if "%1"=="help" (
    call :show_help
    goto :end
)

echo 未知命令: %1
echo 使用 %0 help 查看可用命令
goto :end

:end
echo.
pause 