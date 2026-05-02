# 留言精选 Discord Bot

> 版本：2.1.0

一个专为Discord论坛设计的留言精选机器人，允许楼主将优质留言设为精选。支持精选记录、引荐统计与书单功能。

## 功能特点

- 🌟 **留言精选**: 楼主可以将优质留言设为精选（支持斜杠命令和右键菜单）
- ❌ **精选取消**: 楼主可以取消错误精选（支持斜杠命令和右键菜单）
- 🏆 **总排行榜**: 管理组可查看所有用户引荐人数排名，支持时间范围筛选
- 🌌 **全服精选列表**: 管理组可查看全服所有精选留言列表，支持时间/赞数排序和时间范围筛选
- 📜 **鉴赏申请窗口**: 管理组可创建申请窗口，用户满足条件可获得鉴赏家身份
- 📚 **书单**: 每个用户 10 张书单、每张最多 20 帖，支持跨服收藏
- 🔗 **书单帖连结**: 可在 `/书单 管理书单` 绑定书单帖 URL，并展示在 `/留言 精选记录` 页面
- 📖 **公开书单分页**: 公开书单支持分页浏览（每页 5 帖），并支持重启后继续翻页
- 📈 **统计功能**: 查看用户精选次数和引荐统计 (引荐统计基于精选记录)
- 🛡️ **权限控制**: 只有楼主可以精选留言
- 🔄 **跨帖重复**: 不同帖子中可以重复精选同一用户
- 🌐 **多群组支持**: 支持在多个 Discord 群组中独立运行

## 使用规则

1. **权限限制**: 只有楼主可以精选留言
2. **自我限制**: 不能精选自己的留言
3. **单帖限制**: 每个帖子中每位用户只能被精选一次
4. **跨帖允许**: 跨帖子可以重复精选同一用户
5. **内容要求**: 留言至少10个字符，不能只含表情符号或贴纸，支持附件+长文组合

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

### 3. 配置機器人

#### 3.1 設置敏感信息
複製 `env_example.txt` 為 `.env` 並設置您的 Discord Bot Token:

```env
DISCORD_TOKEN=your_actual_bot_token_here
```

#### 3.2 自定義功能配置（可選）
編輯 `config.py` 文件，根據需要調整各種配置項：

- **界面设置**: 调整 `VIEW_TIMEOUT`、`USER_RECORDS_PER_PAGE` 等界面参数
- **管理组角色**: 修改 `ADMIN_ROLE_NAMES` 添加管理组角色
- **鉴赏家要求**: 调整 `APPRECIATOR_MIN_FEATURED`、`APPRECIATOR_MIN_REFERRALS`
- **鉴赏家统计范围**: 调整 `APPRECIATOR_CROSS_GUILD_STATS`（`True` 为跨服累计，`False` 为本服累计）

詳細配置說明請參考 [CONFIG_GUIDE.md](CONFIG_GUIDE.md)

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

完整 slash command、右键菜单、书单与书单帖守门说明请见 [command.md](command.md)。

## 项目结构
<details>
<summary>展开 / 收起 项目结构</summary>

第六阶段解耦后，根目录 `bot.py` 与 `booklist_system.py` 保留为兼容入口，启动流程、Bot client、留言精选系统与书单系统分离；数据库结构与数据文件不迁移，并补上資料層單元測試作为重构回归保护。

```
app/
├── main.py                  # 启动流程
├── logging_config.py        # 日志初始化
├── bot/
│   └── client.py            # FeaturedMessageBot 与 Bot lifecycle
├── booklist/
│   ├── commands.py          # 书单 Cog 与 slash 指令
│   ├── modals.py            # 书单输入表单
│   ├── views.py             # 书单管理、公开分页与管理组面板
│   ├── formatting.py        # 书单显示格式 helper
│   └── constants.py         # 书单分页与数量限制
├── features/
│   ├── featured_system.py   # 留言精选 Cog 与 slash/context 指令
│   ├── featured_views.py    # 精选互动界面的聚合导出入口
│   ├── feature_actions.py   # 精选/取消精选的 Modal 与确认 View
│   ├── record_views.py      # 用户精选记录与引荐排行榜 View
│   ├── stats_views.py       # 帖子统计与全服精选列表 View
│   └── appreciator_views.py # 鉴赏家申请 View
└── utils/
    ├── discord_channels.py  # Discord 频道类型判断
    ├── discord_links.py     # Discord URL 解析
    ├── permissions.py       # 权限判断 helper
    └── text.py              # 文本截断、数字解析、字段切分

bot.py                       # 兼容入口：调用 app.main.start_bot()
booklist_system.py           # 兼容入口：导出 app.booklist.BooklistCommands
database.py                  # SQLite 数据访问层（本阶段不迁移）
command.md                   # 指令与交互说明
history.md                   # 版本更新历史
tests/
└── test_database_manager.py # SQLite 数据层回归测试
```

</details>

## 测试
<details>
<summary>展开 / 收起 测试说明</summary>

项目使用 Python 标准库 `unittest`，不需要额外测试依赖。

```bash
python -m unittest discover -s tests
```

重构后可用以下命令做快速语法检查：

```bash
python -m py_compile bot.py booklist_system.py database.py config.py config_check.py db_checker.py guild_data_extractor.py app/main.py app/logging_config.py app/bot/client.py app/features/featured_system.py app/features/featured_views.py app/features/feature_actions.py app/features/record_views.py app/features/stats_views.py app/features/appreciator_views.py app/utils/discord_channels.py app/utils/discord_links.py app/utils/permissions.py app/utils/text.py tests/test_database_manager.py
```

</details>

## 数据管理
<details>
<summary>展开 / 收起 数据管理</summary>

### 数据目录结构
机器人会自动创建以下目录结构：
```
data/
├── featured_messages.db  # SQLite 数据库文件
└── logs/
    └── bot.log          # 机器人运行日志
```

### 数据库结构

机器人使用 SQLite 数据库存储数据，包含以下表:

### featured_messages (精选记录表)
- `id`: 记录ID
- `guild_id`: 群组ID
- `thread_id`: 帖子ID
- `message_id`: 留言ID
- `author_id`: 留言作者ID
- `author_name`: 留言作者名
- `featured_by_id`: 精选者ID
- `featured_by_name`: 精选者名
- `featured_at`: 精选时间
- `reason`: 精选原因
- `bot_message_id`: 机器人精选通知消息ID

### user_booklists (用户书单主表)
- `user_id`: 用户ID
- `list_id`: 书单ID（0~9）
- `title`: 书单标题
- `created_at`: 创建时间
- `updated_at`: 更新时间

### user_booklist_entries (书单帖子明细)
- `id`: 明细ID
- `user_id`: 用户ID
- `list_id`: 书单ID
- `thread_guild_id`: 帖子所属群组ID
- `thread_id`: 帖子ID
- `thread_title`: 帖子标题
- `thread_url`: 帖子链接
- `review`: 帖子评价
- `added_at`: 添加时间

### user_booklist_thread_links (书单帖连结绑定)
- `user_id`: 用户ID
- `guild_id`: 群组ID
- `thread_url`: 绑定的书单帖链接
- `updated_at`: 更新时间

### public_booklist_indexes (公开书单最小索引)
- `message_id`: 公开消息ID
- `publisher_user_id`: 发布者用户ID
- `list_id`: 书单ID
- `guild_id`: 群组ID
- `channel_id`: 频道ID
- `published_at`: 发布时间

### booklist_thread_whitelist (书单帖白名单)
- `guild_id`: 群组ID
- `forum_channel_id`: 白名单论坛频道ID
- `updated_at`: 更新时间

</details>

## 工具说明
<details>
<summary>展开 / 收起 工具说明</summary>

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

### 群组数据提取工具
```bash
# 列出所有群组
python guild_data_extractor.py list

# 提取指定群组数据（JSON + CSV）
python guild_data_extractor.py 123456789

# 只导出JSON格式
python guild_data_extractor.py 123456789 json

# 只导出CSV格式
python guild_data_extractor.py 123456789 csv

# 只创建独立数据库
python guild_data_extractor.py 123456789 db

# 提取所有群组数据
python guild_data_extractor.py all
```

**注意**: v1.4.1版本已移除月度积分功能，提取工具不再包含月度积分数据。

</details>

## 故障排除
<details>
<summary>展开 / 收起 故障排除</summary>

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
   - 删除 `data/featured_messages.db` 文件重新启动
   - 使用 `db_checker.py` 检查数据库状态
   - 检查 `data/` 目录权限

4. **统计显示异常**
   - 使用 `db_checker.py` 检查记录表
   - 确认数据库结构完整

### 日志查看
机器人运行时会输出详细日志，包括:
- 启动信息
- 命令执行记录
- 错误信息
- 数据库操作记录
- 性能监控信息
- 表情符号统计处理时间

**日志文件位置**: `data/logs/bot.log`

</details>

## 更新日志

完整版本历史请见 [history.md](history.md)。

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目！

## 许可证

MIT License 
