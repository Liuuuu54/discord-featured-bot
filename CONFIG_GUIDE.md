# Discord Bot 配置指南

## 概述

本机器人的配置分为两个部分：
- **敏感信息**：存储在 `.env` 文件中（如 Discord Token）
- **功能配置**：存储在 `config.py` 文件中（如积分、界面设置等）

## 快速开始

### 1. 设置敏感信息

复制 `env_example.txt` 为 `.env` 文件：

```bash
cp env_example.txt .env
```

编辑 `.env` 文件，填入您的 Discord Bot Token：

```env
DISCORD_TOKEN=your_discord_bot_token_here
```

### 2. 自定义功能配置

编辑 `config.py` 文件，根据需要调整各种配置项。

## 配置项详解

### 敏感信息配置 (.env)

| 配置项 | 说明 | 必需 | 默认值 |
|--------|------|------|--------|
| `DISCORD_TOKEN` | Discord Bot Token | ✅ | 无 |

**注意**：只有 `DISCORD_TOKEN` 是必需的，所有其他配置项都在 `config.py` 中直接设置。

### 功能配置 (config.py)

#### 机器人基础配置

```python
# 注意：机器人名称在 Discord Developer Portal 的 Bot 页面设置
# 本机器人使用斜杠命令，不需要命令前缀
```

#### 积分系统配置

```python
POINTS_PER_FEATURE = 1              # 每次精选获得的积分
```

#### 界面配置

```python
VIEW_TIMEOUT = 300                  # 视图超时时间（秒）
USER_RECORDS_PER_PAGE = 5          # 用户记录每页显示数
RANKING_PER_PAGE = 20              # 排行榜每页显示数
THREAD_STATS_PER_PAGE = 5          # 帖子统计每页显示数
RECORDS_PER_PAGE = 10              # 全服精选列表每页显示数
REACTION_CACHE_DURATION = 5        # 表情符号缓存时间（秒）
```

#### 日志配置

```python
LOG_LEVEL = 'INFO'                  # 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_TO_CONSOLE = True              # 是否输出到控制台
```

#### 功能开关

```python
ENABLE_REACTION_STATS = True       # 是否启用表情符号统计
ENABLE_CACHE = True                # 是否启用缓存
ENABLE_VERBOSE_LOGGING = False     # 是否启用详细日志
```

#### 消息配置

```python
MIN_MESSAGE_LENGTH = 10            # 精选留言最小字符数
MAX_MESSAGE_LENGTH = 0             # 精选留言最大字符数（0表示无限制）
ALLOW_ATTACHMENTS = True           # 是否允许精选包含附件的消息
ALLOW_LINKS = True                 # 是否允许精选包含链接的消息
```

#### 时间范围配置

```python
DEFAULT_TIME_RANGE_DAYS = 30       # 默认时间范围（天）
MAX_TIME_RANGE_DAYS = 365          # 最大时间范围（天）
```

#### 管理组配置

```python
ADMIN_ROLE_NAMES = [               # 管理组角色名称列表
    "管理组", 
    "秘书组",
    "BOT维护员", 
    "版主",
    "Admin", 
    "Moderator", 
]
```

**注意**：这些配置项直接在 `config.py` 中设置，不支持环境变量覆盖。

#### 鉴赏申请窗口配置

```python
APPRECIATOR_ROLE_NAME = '鉴赏家'    # 鉴赏家角色名称
APPRECIATOR_MIN_POINTS = 1         # 最低积分要求
APPRECIATOR_MIN_REFERRALS = 3      # 最低引荐人数要求
```

**注意**：这些配置项直接在 `config.py` 中设置，不支持环境变量覆盖。

## 部署说明

### 本地开发

1. 创建 `.env` 文件并填入 Discord Token
2. 根据需要修改 `config.py` 中的配置项
3. 运行机器人

### VPS 部署

1. 设置环境变量 `DISCORD_TOKEN`
2. 根据需要设置其他可选环境变量
3. 修改 `config.py` 中的配置项
4. 运行机器人

## 配置建议

### 性能优化

- 增加 `REACTION_CACHE_DURATION` 可以减少 API 调用
- 调整 `VIEW_TIMEOUT` 可以控制界面响应时间
- 设置合适的 `LOG_LEVEL` 可以减少日志输出

### 用户体验

- 调整每页显示记录数可以优化界面显示
- 设置合理的积分和引荐人数要求
- 配置合适的管理组角色名称

### 安全性

- 确保 `.env` 文件不被提交到版本控制
- 定期更换 Discord Token
- 限制管理组角色权限

## 常见问题

### Q: 如何修改积分系统？
A: 编辑 `config.py` 中的 `POINTS_PER_FEATURE` 配置项。

### Q: 如何添加新的管理组角色？
A: 直接编辑 `config.py` 文件中的 `ADMIN_ROLE_NAMES` 列表。

### Q: 如何修改鉴赏家申请条件？
A: 直接编辑 `config.py` 文件中的 `APPRECIATOR_MIN_POINTS` 和 `APPRECIATOR_MIN_REFERRALS` 配置项。

### Q: 如何调整界面显示？
A: 修改 `config.py` 中的界面配置项，如 `USER_RECORDS_PER_PAGE`、`VIEW_TIMEOUT` 等。

### Q: 如何启用调试模式？
A: 将 `LOG_LEVEL` 设置为 `'DEBUG'`，并启用 `ENABLE_VERBOSE_LOGGING`。
