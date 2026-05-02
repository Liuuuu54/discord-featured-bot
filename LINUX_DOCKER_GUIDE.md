# Docker 部署指南

## 🚀 快速开始

### 1. 环境准备

确保你的 VPS 已安装：
- Docker
- Docker Compose

```bash
# 检查 Docker 版本
docker --version
docker-compose --version
```

### 2. 部署步骤

```bash
# 1. 克隆项目
git clone <your-repo-url>
cd dc_bot

# 2. 配置环境变量
cp env_example.txt .env
nano .env  # 设置你的 DISCORD_TOKEN

# 3. 给脚本执行权限
chmod +x deploy.sh backup.sh start.sh

# 4. 一键部署
./deploy.sh deploy
```

### 3. 验证部署

```bash
# 查看容器状态
./deploy.sh status

# 查看日志
./deploy.sh logs
```

## 📋 管理命令

### 基本操作

```bash
# 启动 Bot
./deploy.sh start

# 停止 Bot
./deploy.sh stop

# 重启 Bot
./deploy.sh restart

# 查看状态
./deploy.sh status

# 查看日志
./deploy.sh logs
```

### 数据管理

```bash
# 备份数据
./backup.sh backup

# 查看备份列表
./backup.sh list

# 恢复备份
./backup.sh restore backups/dc_bot_backup_20231201_120000.tar.gz

# 清理旧备份
./backup.sh cleanup
```

### 维护操作

```bash
# 重新构建镜像
./deploy.sh build

# 清理 Docker 资源
./deploy.sh cleanup

# 更新 Bot（拉取最新代码后）
./deploy.sh deploy
```

## 🔧 配置说明

### 环境变量

在 `.env` 文件中配置：

```bash
# 必需：Discord Bot Token
DISCORD_TOKEN=your_bot_token_here

# 可选：管理组角色名称（如果不设置，将使用 config.py 中的默认值）
# ADMIN_ROLE_NAMES=管理组,秘书组,BOT维护员,版主,Admin,Moderator
```

### VPS 终端乱码

v2.1.0 起，`deploy.sh`、`backup.sh`、`start.sh` 的终端输出改为 ASCII/English，避免 VPS 或 SSH 客户端未配置 UTF-8 时出现中文乱码。

容器内已设置：

```bash
LANG=C.UTF-8
LC_ALL=C.UTF-8
PYTHONIOENCODING=utf-8
```

如果你希望 VPS shell 本身也正常显示中文，可在服务器上额外设置 UTF-8 locale：

```bash
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
```

若系统支持 `locale-gen`，也可以安装完整 UTF-8 locale：

```bash
sudo apt-get update
sudo apt-get install -y locales
sudo locale-gen en_US.UTF-8
sudo update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
```

### 数据持久化

- **数据目录**: `./data/` (挂载到容器内 `/app/data/`)
- **数据库**: `./data/featured_messages.db`
- **日志**: `./data/logs/bot.log`
- **备份**: `./backups/`

### 资源限制

Docker Compose 配置了资源限制：
- **内存**: 最大 512MB，预留 256MB
- **CPU**: 最大 0.5 核，预留 0.25 核

## 📊 监控和日志

### 查看实时日志

```bash
# 查看所有日志
./deploy.sh logs

# 查看最近100行日志
docker-compose logs --tail=100

# 查看错误日志
docker-compose logs | grep ERROR
```

### 日志轮转

Docker 日志配置：
- 最大文件大小：10MB
- 保留文件数：3个

## 🔄 更新流程

### 自动更新

```bash
# 1. 拉取最新代码
git pull

# 2. 重新部署
./deploy.sh deploy
```

> v2.1.0 起项目代码拆分到 `app/`、`app/booklist/`、`app/features/` 等目录，但 Docker 启动入口仍是 `start.sh -> python bot.py`。`bot.py` 和 `booklist_system.py` 都保留兼容入口，因此 VPS 更新和重启流程不变。
>
> 如果是从 v2.0.x 升级到 v2.1.0，建议在 `git pull` 前先执行一次 `./backup.sh backup`，再按上面的自动更新流程部署。

### 手动更新

```bash
# 1. 停止服务
./deploy.sh stop

# 2. 备份数据
./backup.sh backup

# 3. 拉取代码
git pull

# 4. 重新构建
./deploy.sh build

# 5. 启动服务
./deploy.sh start
```

## 🛠️ 故障排除

### 常见问题

1. **容器无法启动**
   ```bash
   # 查看详细错误
   docker-compose logs
   
   # 检查环境变量
   cat .env
   ```

2. **Bot 无法连接 Discord**
   ```bash
   # 检查 Token 是否正确
   # 查看连接日志
   ./deploy.sh logs
   ```

3. **数据丢失**
   ```bash
   # 查看备份
   ./backup.sh list
   
   # 恢复备份
   ./backup.sh restore <backup_file>
   ```

4. **权限问题**
   ```bash
   # 检查文件权限
   ls -la
   
   # 修复权限
   chmod +x deploy.sh backup.sh start.sh
   ```

### 调试模式

```bash
# 进入容器调试
docker-compose exec discord-bot bash

# 查看容器内文件
docker-compose exec discord-bot ls -la /app/data

# 查看容器内日志
docker-compose exec discord-bot tail -f /app/data/logs/bot.log
```

## 📈 性能优化

### 资源监控

```bash
# 查看容器资源使用
docker stats dc-bot

# 查看系统资源
htop
```

### 数据库优化

- 定期备份数据库
- 监控数据库大小
- 清理旧日志文件

### 日志管理

```bash
# 清理旧日志
find ./data/logs -name "*.log" -mtime +7 -delete

# 压缩日志
gzip ./data/logs/bot.log
```

## 🔒 安全建议

1. **环境变量安全**
   - 不要在代码中硬编码 Token
   - 定期更换 Bot Token
   - 限制 `.env` 文件权限

2. **网络安全**
   - 使用防火墙限制端口访问
   - 定期更新系统和 Docker
   - 监控异常连接

3. **数据安全**
   - 定期备份数据
   - 加密敏感数据
   - 限制数据目录权限

## 📞 支持

如果遇到问题：

1. 查看日志文件
2. 检查配置文件
3. 参考故障排除部分
4. 提交 Issue 并附上错误信息 
