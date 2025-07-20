import os
from dotenv import load_dotenv

# 只在本地環境中載入 .env 文件
if os.path.exists('.env'):
    load_dotenv()

# Discord Bot Token
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# 檢查 Token 是否存在
if not DISCORD_TOKEN:
    raise ValueError("❌ DISCORD_TOKEN 環境變量未設置！請在 Railway 項目設置中添加 DISCORD_TOKEN 環境變量。")

# 数据库文件路径
DATABASE_FILE = 'featured_messages.db'

# 机器人配置
BOT_PREFIX = '!'
BOT_NAME = '留言精選'

# 积分系统配置
POINTS_PER_FEATURE = 1  # 每次精選获得的积分 