import os
from dotenv import load_dotenv

# 只在本地環境中載入 .env 文件
if os.path.exists('.env'):
    load_dotenv()

# Discord Bot Token
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# 檢查 Token 是否存在
if not DISCORD_TOKEN:
    raise ValueError("❌ DISCORD_TOKEN 環境變量未設置！請設置 DISCORD_TOKEN 環境變量。")

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

# 机器人配置
BOT_PREFIX = '!'
BOT_NAME = '留言精選'

# 积分系统配置
POINTS_PER_FEATURE = 1  # 每次精選获得的积分

# 管理组配置
ADMIN_ROLE_NAMES = [
    "管理组", 
    "管理员", 
    "Admin", 
    "Moderator", 
    "管理",
    "版主",
]  # 管理组角色名称列表，可以从环境变量读取

# 从环境变量读取管理组角色名称（可选）
ADMIN_ROLES_ENV = os.getenv('ADMIN_ROLE_NAMES')
if ADMIN_ROLES_ENV:
    try:
        # 支持逗号分隔的角色名称
        custom_admin_roles = [role.strip() for role in ADMIN_ROLES_ENV.split(',')]
        ADMIN_ROLE_NAMES = custom_admin_roles
    except Exception as e:
        print(f"⚠️ 解析环境变量 ADMIN_ROLE_NAMES 失败: {e}，使用默认配置") 