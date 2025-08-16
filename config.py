import os
from dotenv import load_dotenv

# 只在本地環境中載入 .env 文件
if os.path.exists('.env'):
    load_dotenv()

# ==================== 敏感信息（从 .env 读取）====================
# Discord Bot Token
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# 檢查 Token 是否存在
if not DISCORD_TOKEN:
    raise ValueError("❌ DISCORD_TOKEN 環境變量未設置！請設置 DISCORD_TOKEN 環境變量。")

# ==================== 文件路径配置 ====================
# 创建数据目录
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# 创建日志目录
LOGS_DIR = os.path.join(DATA_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# 数据库文件路径
DATABASE_FILE = os.path.join(DATA_DIR, 'featured_messages.db')

# 日志文件路径
LOG_FILE = os.path.join(LOGS_DIR, 'bot.log')

# ==================== 积分系统配置 ====================
POINTS_PER_FEATURE = 1  # 每次精選获得的积分

# ==================== 管理组配置 ====================
# 管理组角色名称列表
ADMIN_ROLE_NAMES = [
    "管理组", 
    "秘书组",
    "BOT维护员", 
    "版主",
    "Admin", 
    "Moderator", 
]

# ==================== 鉴赏申请窗口配置 ====================
APPRECIATOR_ROLE_NAME = '鉴赏家'  # 鉴赏家角色名称
APPRECIATOR_MIN_POINTS = 1  # 最低积分要求
APPRECIATOR_MIN_REFERRALS = 3  # 最低引荐人数要求

# ==================== 界面配置 ====================
# 视图超时时间（秒）
VIEW_TIMEOUT = 300  # 5分钟

# 每页显示记录数
USER_RECORDS_PER_PAGE = 5      # 用户记录每页显示数
RANKING_PER_PAGE = 20          # 排行榜每页显示数
THREAD_STATS_PER_PAGE = 5      # 帖子统计每页显示数
RECORDS_PER_PAGE = 10          # 全服精选列表每页显示数

# 表情符号缓存时间（秒）
REACTION_CACHE_DURATION = 5

# ==================== 日志配置 ====================
# 日志级别
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# 是否输出到控制台
LOG_TO_CONSOLE = True

# ==================== 功能开关 ====================
# 是否启用表情符号统计
ENABLE_REACTION_STATS = True

# 是否启用缓存
ENABLE_CACHE = True

# 是否启用详细日志
ENABLE_VERBOSE_LOGGING = False

# ==================== 消息配置 ====================
# 精选留言最小字符数
MIN_MESSAGE_LENGTH = 10

# 精选留言最大字符数（0表示无限制）
MAX_MESSAGE_LENGTH = 0

# 是否允许精选包含附件的消息
ALLOW_ATTACHMENTS = True

# 是否允许精选包含链接的消息
ALLOW_LINKS = True

# ==================== 时间范围配置 ====================
# 默认时间范围（天）
DEFAULT_TIME_RANGE_DAYS = 30

# 最大时间范围（天）
MAX_TIME_RANGE_DAYS = 365 