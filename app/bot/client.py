import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

import config
from database import DatabaseManager

logger = logging.getLogger(__name__)


class FeaturedMessageBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True

        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None,
        )

        self.db = DatabaseManager(config.DATABASE_FILE)

    async def setup_hook(self):
        """机器人启动时的设置"""
        from app.booklist import BooklistCommands
        from app.features.featured_system import AppreciatorApplicationView, FeaturedCommands

        self.add_view(AppreciatorApplicationView(self))
        await self.add_cog(FeaturedCommands(self))
        await self.add_cog(BooklistCommands(self))
        await self.tree.sync()
        logger.info('🤖 机器人设置完成，正在连接...')

    async def on_ready(self):
        """机器人准备就绪时的回调"""
        logger.info('=' * 50)
        logger.info('🤖 机器人已成功启动！')
        logger.info(f'📝 机器人名称: {self.user.name}')
        logger.info(f'🆔 机器人ID: {self.user.id}')
        logger.info(f'📅 启动时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        logger.info(f'🌐 连接状态: 已连接到 {len(self.guilds)} 个服务器')
        logger.info('=' * 50)
        logger.info('✅ 机器人已准备就绪，可以开始使用！')
        logger.info('📋 可用命令: /留言 精选, /留言 精选记录, /留言 帖子统计, /留言 总排行, /留言 鉴赏申请窗口, /留言 全服精选列表, /书单 添加至书单, /书单 管理书单, /书单 公开书单, /书单 全服书单列表')
        logger.info('=' * 50)

    async def on_interaction(self, interaction: discord.Interaction):
        """统一记录交互日志，覆盖斜杠命令/右键菜单/按钮/表单。"""
        try:
            guild_name = interaction.guild.name if interaction.guild else "DM"
            guild_id = interaction.guild.id if interaction.guild else 0
            channel_id = interaction.channel.id if interaction.channel else 0
            user_name = interaction.user.name if interaction.user else "Unknown"
            user_id = interaction.user.id if interaction.user else 0

            if interaction.type == discord.InteractionType.application_command:
                command_name = interaction.command.qualified_name if interaction.command else "unknown"
                logger.info(
                    f"🧭 交互: application_command | 命令: {command_name} | 用户: {user_name}({user_id}) | "
                    f"群组: {guild_name}({guild_id}) | 频道: {channel_id}"
                )
            elif interaction.type == discord.InteractionType.component:
                custom_id = interaction.data.get("custom_id") if interaction.data else "unknown"
                logger.info(
                    f"🧭 交互: component | custom_id: {custom_id} | 用户: {user_name}({user_id}) | "
                    f"群组: {guild_name}({guild_id}) | 频道: {channel_id}"
                )
            elif interaction.type == discord.InteractionType.modal_submit:
                custom_id = interaction.data.get("custom_id") if interaction.data else "unknown"
                logger.info(
                    f"🧭 交互: modal_submit | custom_id: {custom_id} | 用户: {user_name}({user_id}) | "
                    f"群组: {guild_name}({guild_id}) | 频道: {channel_id}"
                )
        except Exception as e:
            logger.debug(f"记录交互日志失败: {e}")

    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        """当消息被删除时，清理公开书单最小索引，避免数据膨胀。"""
        try:
            self.db.deactivate_public_booklist_index(payload.message_id)
        except Exception as e:
            logger.debug(f"清理公开书单索引失败(单条): {e}")

    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent):
        """当批量删消息时，清理公开书单最小索引。"""
        for message_id in payload.message_ids:
            try:
                self.db.deactivate_public_booklist_index(message_id)
            except Exception as e:
                logger.debug(f"清理公开书单索引失败(批量): {e}")

    async def on_message(self, message: discord.Message):
        """书单帖发言限制：仅绑定者本人可发言，其他人只能反应。"""
        if message.author.bot:
            return

        if message.guild and isinstance(message.channel, discord.Thread):
            bound_owner_id = self.db.get_booklist_thread_owner(message.guild.id, message.channel.id)
            if bound_owner_id and message.author.id != bound_owner_id:
                try:
                    await message.delete()
                    logger.info(
                        f"🧹 已删除书单帖非楼主留言 | 用户: {message.author.name}({message.author.id}) | "
                        f"帖子: {message.channel.id} | 群组: {message.guild.id}"
                    )
                except discord.Forbidden:
                    logger.warning(
                        f"⚠️ 无权限删除书单帖留言 | 用户: {message.author.id} | 帖子: {message.channel.id} | 群组: {message.guild.id}"
                    )
                except Exception as e:
                    logger.warning(f"删除书单帖留言失败: {e}")
                return

        await self.process_commands(message)

    async def on_command_error(self, ctx, error):
        """处理命令错误"""
        if isinstance(error, commands.CommandNotFound):
            return

        logger.error(f"命令执行错误: {error}")

        try:
            if isinstance(error, commands.MissingPermissions):
                await ctx.send("❌ 您没有权限执行此命令！", delete_after=5)
            elif isinstance(error, commands.BotMissingPermissions):
                await ctx.send("❌ 机器人缺少必要的权限！", delete_after=5)
            elif isinstance(error, commands.CommandOnCooldown):
                await ctx.send(f"⏰ 命令冷却中，请等待 {error.retry_after:.1f} 秒后重试", delete_after=5)
            else:
                await ctx.send("❌ 命令执行时发生错误，请稍后重试", delete_after=5)
        except Exception as e:
            logger.error(f"发送错误消息失败: {e}")

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """处理斜杠命令错误"""
        if isinstance(error, app_commands.CommandNotFound):
            return

        logger.error(f"斜杠命令执行错误: {error}")

        try:
            if isinstance(error, app_commands.MissingPermissions):
                await interaction.response.send_message("❌ 您没有权限执行此命令！", ephemeral=True)
            elif isinstance(error, app_commands.BotMissingPermissions):
                await interaction.response.send_message("❌ 机器人缺少必要的权限！", ephemeral=True)
            elif isinstance(error, app_commands.CommandOnCooldown):
                await interaction.response.send_message(f"⏰ 命令冷却中，请等待 {error.retry_after:.1f} 秒后重试", ephemeral=True)
            else:
                await interaction.response.send_message("❌ 命令执行时发生错误，请稍后重试", ephemeral=True)
        except Exception as e:
            logger.error(f"发送斜杠命令错误消息失败: {e}")
