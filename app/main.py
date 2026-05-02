import asyncio
import logging

import config
from app.bot.client import FeaturedMessageBot
from app.logging_config import setup_logging

logger = logging.getLogger(__name__)


async def main():
    """主函数"""
    setup_logging()
    bot = FeaturedMessageBot()

    try:
        await bot.start(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("🛑 收到停止信号，正在关闭机器人...")
    except Exception as e:
        logger.error(f"❌ 机器人运行时发生错误: {e}")
    finally:
        await bot.close()


def start_bot():
    """启动 Discord Bot"""
    asyncio.run(main())
