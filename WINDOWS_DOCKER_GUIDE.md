# Windows Docker 部署指南

## 📋 前置要求

### 1. 安装 Docker Desktop
1. 访问 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
2. 下载并安装 Docker Desktop
3. 启动 Docker Desktop
4. 确保 Docker 服务正在运行

### 2. 系统要求
- Windows 10 64位 (版本 1903 或更高)
- 启用 Hyper-V 和容器功能
- 至少 4GB RAM

## 🚀 快速部署

### 步骤 1: 准备环境
```cmd
# 克隆或下载项目到本地
cd /d D:\dc_bot

# 复制环境变量模板
copy env_example.txt .env
```

### 步骤 2: 配置环境变量
编辑 `.env` 文件，设置您的 Discord Bot Token：
```env
DISCORD_TOKEN=your_actual_discord_bot_token_here
```

### 步骤 3: 一键部署
```cmd
# 使用 Windows 部署脚本
deploy.bat deploy
```

## 📖 使用说明

### 基本命令
```cmd
# 查看帮助
deploy.bat help

# 构建镜像
deploy.bat build

# 启动服务
deploy.bat start

# 停止服务
deploy.bat stop

# 重启服务
deploy.bat restart

# 查看状态
deploy.bat status

# 查看日志
deploy.bat logs

# 备份数据
deploy.bat backup

# 清理资源
deploy.bat cleanup
```

### 完整部署流程
```cmd
# 1. 检查 Docker 是否安装
docker --version

# 2. 复制环境变量
copy env_example.txt .env

# 3. 编辑 .env 文件（用记事本或其他编辑器）
notepad .env

# 4. 一键部署
deploy.bat deploy

# 5. 检查状态
deploy.bat status

# 6. 查看日志
deploy.bat logs
```

## 🔧 故障排除

### 常见问题

#### 1. Docker 未安装
```
❌ Docker 未安装！请先安装 Docker Desktop
```
**解决方案：**
- 下载并安装 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
- 重启计算机
- 启动 Docker Desktop

#### 2. 环境变量未设置
```
❌ 请在 .env 文件中设置 DISCORD_TOKEN
```
**解决方案：**
```cmd
# 复制环境变量模板
copy env_example.txt .env

# 编辑文件
notepad .env
```

#### 3. 端口冲突
```
❌ 启动失败
```
**解决方案：**
```cmd
# 检查端口占用
netstat -ano | findstr :80

# 停止冲突的服务或修改端口
```

#### 4. 权限问题
```
❌ 权限被拒绝
```
**解决方案：**
- 以管理员身份运行命令提示符
- 确保 Docker Desktop 正在运行
- 检查 Windows Defender 防火墙设置

### 手动操作

#### 直接使用 Docker Compose
```cmd
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

#### 查看容器状态
```cmd
# 查看运行中的容器
docker ps

# 查看所有容器
docker ps -a

# 查看镜像
docker images
```

## 📁 文件结构

```
dc_bot/
├── deploy.bat          # Windows 部署脚本
├── docker-compose.yml  # Docker Compose 配置
├── Dockerfile         # Docker 镜像配置
├── .env               # 环境变量（需要创建）
├── env_example.txt    # 环境变量模板
├── bot.py             # 主程序
├── requirements.txt   # Python 依赖
└── data/              # 数据目录
    └── logs/          # 日志目录
```

## 🔄 更新部署

### 更新代码后重新部署
```cmd
# 停止当前服务
deploy.bat stop

# 重新构建并启动
deploy.bat deploy
```

### 仅更新镜像
```cmd
# 重新构建镜像
deploy.bat build

# 重启服务
deploy.bat restart
```

## 💾 数据管理

### 备份数据
```cmd
# 自动备份
deploy.bat backup

# 手动备份
xcopy /E /I data backup_%date:~0,4%%date:~5,2%%date:~8,2%
```

### 恢复数据
```cmd
# 停止服务
deploy.bat stop

# 复制备份数据
xcopy /E /I backup_20241201\data data

# 重新启动
deploy.bat start
```

## 🛠️ 开发模式

### 本地开发（不使用 Docker）
```cmd
# 安装 Python 依赖
pip install -r requirements.txt

# 直接运行
start.bat
```

### 调试模式
```cmd
# 查看详细日志
docker-compose logs -f --tail=100

# 进入容器
docker exec -it dc-bot bash

# 查看容器内文件
docker exec -it dc-bot ls -la
```

## 📊 监控和维护

### 查看资源使用
```cmd
# 查看容器资源使用
docker stats

# 查看磁盘使用
docker system df
```

### 清理资源
```cmd
# 清理未使用的镜像和容器
deploy.bat cleanup

# 手动清理
docker system prune -a
```

## 🔐 安全建议

1. **保护 .env 文件**
   - 不要将 .env 文件提交到版本控制
   - 定期更换 Discord Bot Token

2. **网络安全**
   - 使用防火墙限制访问
   - 定期更新 Docker 和系统

3. **数据备份**
   - 定期备份 data 目录
   - 测试备份恢复流程

## 📞 技术支持

如果遇到问题：

1. 检查 Docker Desktop 是否正常运行
2. 查看 `deploy.bat logs` 输出的错误信息
3. 确认 .env 文件配置正确
4. 检查网络连接和防火墙设置

## 🎯 快速命令参考

| 功能 | 命令 |
|------|------|
| 一键部署 | `deploy.bat deploy` |
| 启动服务 | `deploy.bat start` |
| 停止服务 | `deploy.bat stop` |
| 重启服务 | `deploy.bat restart` |
| 查看状态 | `deploy.bat status` |
| 查看日志 | `deploy.bat logs` |
| 备份数据 | `deploy.bat backup` |
| 清理资源 | `deploy.bat cleanup` |
| 查看帮助 | `deploy.bat help` | 