import os
from dotenv import load_dotenv

load_dotenv()

# Discord Bot Token
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# 数据库文件路径
DATABASE_FILE = 'featured_messages.db'

# 机器人配置
BOT_PREFIX = '!'
BOT_NAME = '留言精選'

# 积分系统配置
POINTS_PER_FEATURE = 1  # 每次精選获得的积分 