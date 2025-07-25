# 留言精選 Discord Bot

一个专为Discord论坛设计的留言精選机器人，允许楼主将优质留言设为精選，并为被精選用户提供积分奖励。支持月度积分系统和排行榜功能。

## 功能特点

- 🌟 **留言精選**: 楼主可以将优质留言设为精選
- ❌ **精選取消**: 楼主可以取消错误精選并修正积分
- 🏆 **积分系统**: 被精選用户自动获得积分奖励
- 📊 **月度积分**: 每月积分独立计算，自动重置
- 🏅 **排行榜**: 显示月度积分排行榜
- 🏆 **总排行榜**: 管理组可查看所有用户总积分排名
- 📈 **统计功能**: 查看用户积分和精選统计
- 🛡️ **权限控制**: 只有楼主可以精選留言
- 🔄 **跨帖重复**: 不同帖子中可以重复精選同一用户
- 🌐 **多群组支持**: 支持在多个 Discord 群组中独立运行

## 使用规则

1. **权限限制**: 只有楼主可以精選留言
2. **自我限制**: 不能精選自己的留言
3. **单帖限制**: 每个帖子中每位用户只能被精選一次
4. **跨帖允许**: 跨帖子可以重复精選同一用户
5. **积分奖励**: 每次精選获得1积分
6. **月度重置**: 每月1日积分自动重置

## 🚀 快速開始

### 1. 克隆項目
```bash
git clone <repository-url>
cd dc_bot
```

### 2. 安裝依賴
```bash
pip install -r requirements.txt
```

### 3. 配置環境變量
複製 `env_example.txt` 為 `.env` 並設置您的 Discord Bot Token:
```
DISCORD_TOKEN=your_actual_bot_token_here
```

### 4. 創建 Discord 機器人
1. 訪問 [Discord Developer Portal](https://discord.com/developers/applications)
2. 創建新應用並在 "Bot" 部分創建機器人
3. 複製 Token 並設置到環境變量中
4. 啟用以下權限:
   - Send Messages
   - Use Slash Commands
   - Read Message History
   - Embed Links
   - Mention Everyone

### 5. 邀請機器人到服務器
使用以下鏈接邀請機器人（替換 YOUR_BOT_CLIENT_ID）:
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_CLIENT_ID&permissions=2048&scope=bot%20applications.commands
```

### 6. 運行機器人
```bash
python bot.py
```

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

### ❌ /精選取消
取消指定留言的精選狀態
- **参数**: 
  - `message_id`: 要取消精選的留言ID
- **权限**: 仅楼主可用
- **效果**: 
  - 移除精選记录
  - 被精選用户积分减少1分
  - 同时减少总积分和月度积分
  - 支持错误精選的修正

### 📊 /积分
查看用户积分和精選统计（支持查看其他用户）
- **参数**: 
  - `user` (可选): 要查看的用户，不填则查看自己
- **显示**: 
  - 当前总积分
  - 被精選次数
  - 精選他人次数
  - 分页显示精選记录（每页5条）
  - 包含原帖链接、精選者、时间等信息
- **权限**: 
  - 所有积分查看都仅自己可见

### 🏅 /排行榜
显示月度积分排行榜（仅对用户本人可见）
- **显示**: 
  - 前10名用户
  - 月度积分排名
  - 积分数量
- **更新**: 实时更新

### 🏆 /總排行
显示总积分排行榜（仅管理组可用）
- **权限**: 需要管理员权限
- **显示**: 
  - 所有用户的积分排名（不会重置）
  - 每页显示20个用户
  - 支持分页浏览
  - 积分数量
- **特点**: 仅管理组可见，用于管理监控

### 📈 /帖子统计
查看当前帖子的精選统计（仅对用户本人可见）
- **权限**: 仅在帖子中可用
- **显示**: 分页显示精選记录（每页5条）

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
├── bot.py                    # 主机器人文件
├── config.py                 # 配置文件
├── database.py               # 数据库管理
├── db_checker.py             # 数据库检查工具
├── requirements.txt          # 依赖包
├── env_example.txt           # 环境变量示例
├── README.md                 # 说明文档
├── Dockerfile                # Docker 配置
├── docker-compose.yml        # Docker Compose 配置
├── deploy.sh                 # Docker 部署脚本
├── backup.sh                 # Docker 备份脚本
└── featured_messages.db      # 数据库文件（自动生成）
```

## 工具说明

### 数据库检查工具
```bash
# 详细检查（默认）
python db_checker.py

# 简单检查
python db_checker.py --simple

# 交互式查询
python db_checker.py --interactive

# 检查特定群组
python db_checker.py --guild 123456789

# 查看帮助
python db_checker.py --help
```

## 故障排除

### 常见问题

1. **机器人无法启动**
   - 检查环境变量中的 Token 是否正确
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



### 日志查看
机器人运行时会输出详细日志，包括:
- 启动信息
- 命令执行记录
- 错误信息
- 数据库操作记录

## 更新日志

### v1.0.1
- ✨ 新增 `/精選取消` 命令：楼主可取消错误精選并修正积分
- ✨ 新增 `/總排行` 命令：管理组可查看所有用户总积分排行榜
- 🔧 优化 `/积分` 命令：支持查看其他用户积分

### v1.0.0
- 🌟 基础精選功能
- 📊 积分统计系统
- 🛡️ 权限控制
- ✨ 月度积分系统
- 🏅 排行榜功能
- 📄 分页显示功能
- 🔧 数据库检查工具
- 🐛 交互响应错误修复

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目！

## 许可证

MIT License 