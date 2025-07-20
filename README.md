# 留言精選 Discord Bot

一个专为Discord论坛设计的留言精選机器人，允许楼主将优质留言设为精選，并为被精選用户提供积分奖励。支持月度积分系统和排行榜功能。

## 功能特点

- 🌟 **留言精選**: 楼主可以将优质留言设为精選
- 🏆 **积分系统**: 被精選用户自动获得积分奖励
- 📊 **月度积分**: 每月积分独立计算，自动重置
- 🏅 **排行榜**: 显示月度积分排行榜
- 📈 **统计功能**: 查看用户积分和精選统计
- 🛡️ **权限控制**: 只有楼主可以精選留言
- 🔄 **跨帖重复**: 不同帖子中可以重复精選同一用户
- 🔒 **隐私保护**: 积分查询仅对用户本人可见
- 🌐 **多群组支持**: 支持在多个 Discord 群组中独立运行

## 使用规则

1. **权限限制**: 只有楼主可以精選留言
2. **自我限制**: 不能精選自己的留言
3. **单帖限制**: 每个帖子中每位用户只能被精選一次
4. **跨帖允许**: 跨帖子可以重复精選同一用户
5. **积分奖励**: 每次精選获得1积分
6. **月度重置**: 每月1日积分自动重置
7. **隐私保护**: `/积分` 命令仅对用户本人可见

## 安装步骤

### 1. 克隆项目
```bash
git clone <repository-url>
cd dc_bot
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

#### 本地开发环境
1. 复制 `env_example.txt` 为 `.env`
2. 在 `.env` 文件中设置您的 Discord Bot Token:
```
DISCORD_TOKEN=your_actual_bot_token_here
```
#### Railway 部署环境
在 Railway 项目设置中添加环境变量：
1. 变量名: `DISCORD_TOKEN`
2. 变量值: 您的 Discord Bot Token

### 4. 创建 Discord 机器人
1. 访问 [Discord Developer Portal](https://discord.com/developers/applications)
2. 创建新应用
3. 在 "Bot" 部分创建机器人
4. 复制 Token 并粘贴到 `.env` 文件中
5. 启用以下权限:
   - Send Messages
   - Use Slash Commands
   - Read Message History
   - Embed Links
   - Mention Everyone

### 5. 邀请机器人到服务器
使用以下链接邀请机器人（替换 YOUR_BOT_CLIENT_ID）:
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_CLIENT_ID&permissions=2048&scope=bot%20applications.commands
```

### 6. 运行机器人

#### 本地运行
```bash
python bot.py
```

#### Railway 部署

1. **连接 GitHub 仓库**
   - 在 Railway 中创建新项目
   - 选择 "Deploy from GitHub repo"
   - 连接您的 GitHub 仓库

2. **配置环境变量**
   - 在项目设置中添加环境变量
   - 变量名: `DISCORD_TOKEN`
   - 变量值: 您的 Discord Bot Token

3. **设置启动命令**
   - 在 Railway 项目设置中设置启动命令:
   ```bash
   python bot.py
   ```

4. **自动部署**
   - Railway 会自动检测代码变更并重新部署
   - 每次推送到 GitHub 主分支都会触发自动部署

> **Railway 优势**: 免费额度、自动部署、HTTPS 支持、无需服务器管理

## 命令说明

### 🌟 /精選
将指定用户的留言设为精選
- **参数**: 
  - `message_id`: 要精選的留言ID
  - `reason`: 精選原因（可选）
- **权限**: 仅楼主可用
- **效果**: 
  - 被精選用户获得1积分
  - 自动@提及被精選用户
  - 显示精選原因

### 📊 /积分
查看用户积分和精選统计（仅对用户本人可见）
- **参数**: 
  - `user`: 要查看的用户（留空查看自己）
- **显示**: 
  - 当前总积分
  - 被精選次数
  - 精選他人次数
  - 分页显示精選记录（每页5条）
  - 包含原帖链接、精選者、时间等信息

### 🏅 /排行榜
显示月度积分排行榜
- **显示**: 
  - 前10名用户
  - 月度积分排名
  - 积分数量
- **更新**: 实时更新

### 📈 /帖子统计
查看当前帖子的精選统计（仅对用户本人可见）
- **权限**: 仅在帖子中可用
- **显示**: 所有精選记录

### ❓ /帮助
查看机器人使用说明

## 数据库结构

机器人使用 SQLite 数据库存储数据，包含以下表:

### user_points (总积分表)
- `user_id`: 用户ID
- `username`: 用户名
- `points`: 总积分
- `created_at`: 创建时间
- `updated_at`: 更新时间

### monthly_points (月度积分表)
- `id`: 记录ID
- `user_id`: 用户ID
- `username`: 用户名
- `points`: 月度积分
- `year_month`: 年月 (格式: YYYY-MM)
- `created_at`: 创建时间
- `updated_at`: 更新时间

### featured_messages (精選记录表)
- `id`: 记录ID
- `thread_id`: 帖子ID
- `message_id`: 留言ID
- `author_id`: 留言作者ID
- `author_name`: 留言作者名
- `featured_by_id`: 精選者ID
- `featured_by_name`: 精選者名
- `featured_at`: 精選时间
- `reason`: 精選原因

## 文件结构

```
dc_bot/
├── bot.py              # 主机器人文件
├── config.py           # 配置文件
├── database.py         # 数据库管理
├── db_checker.py       # 数据库检查工具（支持简单/详细模式）
├── health_check.py     # 健康检查服务器（Railway 部署用）
├── requirements.txt    # 依赖包
├── env_example.txt     # 环境变量示例
├── railway.json        # Railway 部署配置
├── README.md          # 说明文档
└── featured_messages.db # 数据库文件（自动生成）
```

## 工具说明

### 数据库检查工具

#### 本地使用
```bash
# 详细检查（默认）
python db_checker.py

# 简单检查（适合 Railway 环境）
python db_checker.py --simple

# 交互式查询
python db_checker.py --interactive

# 检查特定群组
python db_checker.py --guild 123456789

# 查看帮助
python db_checker.py --help
```

#### Railway 环境使用

**方法 1: Railway CLI（推荐）**
```bash
# 安装 Railway CLI
npm install -g @railway/cli

# 登录并连接项目
railway login
railway link

# 运行检查工具
railway run python db_checker.py --simple
railway run python db_checker.py --interactive
railway run python db_checker.py --guild 123456789
```

**方法 2: Railway Web 界面**
1. 在 Railway 项目页面点击 "Deployments"
2. 选择最新部署，点击 "Logs"
3. 在 "Settings" 中临时修改启动命令为 `python db_checker.py --simple`
4. 查看日志输出

## 故障排除

### 常见问题

1. **机器人无法启动**
   - 检查 `.env` 文件中的 Token 是否正确
   - 确认机器人已正确邀请到服务器
   - 检查数据库文件权限

2. **命令无法使用**
   - 确认机器人有正确的权限
   - 等待几分钟让命令同步完成
   - 检查机器人是否在线

3. **数据库错误**
   - 删除 `featured_messages.db` 文件重新启动
   - 使用 `db_checker.py` 检查数据库状态
   - 检查文件权限

4. **月度积分显示异常**
   - 使用 `db_checker.py` 检查月度积分表
   - 确认数据库结构完整

5. **Railway 健康检查失败**
   - 机器人已内置健康检查服务器
   - 在 Railway 环境中会自动启动
   - 健康检查路径: `/`
   - 超时时间: 30秒

### 日志查看
机器人运行时会输出详细日志，包括:
- 启动信息
- 命令执行记录
- 错误信息
- 数据库操作记录

## 更新日志

### v1.0.0
- 🌟 基础精選功能
- 📊 积分统计系统
- 🛡️ 权限控制
- ✨ 月度积分系统
- 🏅 排行榜功能
- 🔒 隐私保护（积分查询仅对本人可见）
- 📄 分页显示功能
- 🔧 数据库检查工具
- 🐛 交互响应错误修复
- 📱 用户界面和体验优化

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目！

## 许可证

MIT License 