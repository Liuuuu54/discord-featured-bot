import logging

import discord
from discord import app_commands
from discord.ext import commands

import config
from app.utils.permissions import has_admin_permission

logger = logging.getLogger(__name__)


class WelcomeCommands(commands.Cog):
    """新成员欢迎消息模块"""

    welcome_group = app_commands.Group(name="欢迎", description="新成员欢迎消息设置（管理组）")

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """新成员加入时，若本服已设置欢迎频道则发送欢迎消息。"""
        channel_id = self.db.get_welcome_channel(member.guild.id)
        if not channel_id:
            return

        channel = member.guild.get_channel(channel_id) or self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception as e:
                logger.warning(f"欢迎频道获取失败（guild={member.guild.id}, channel={channel_id}）: {e}")
                return

        embed = discord.Embed(
            title="👋 欢迎加入！",
            description=f"欢迎 {member.mention} 加入 **{member.guild.name}**！",
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.warning(f"欢迎消息发送失败，无频道权限（guild={member.guild.id}, channel={channel_id}）")
        except Exception as e:
            logger.error(f"欢迎消息发送失败: {e}")

    @welcome_group.command(name="设置频道", description="设置新成员加入时发送欢迎消息的频道（管理组）")
    async def set_welcome_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ 该命令只能在服务器内使用。", ephemeral=True)
            return

        if not has_admin_permission(interaction.user, config.ADMIN_ROLE_NAMES):
            await interaction.response.send_message("❌ 仅管理组可使用该命令。", ephemeral=True)
            return

        self.db.set_welcome_channel(interaction.guild_id, channel.id)
        await interaction.response.send_message(f"✅ 已设置新成员欢迎频道为 {channel.mention}。", ephemeral=True)

    @welcome_group.command(name="关闭", description="关闭本服新成员欢迎消息（管理组）")
    async def disable_welcome(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ 该命令只能在服务器内使用。", ephemeral=True)
            return

        if not has_admin_permission(interaction.user, config.ADMIN_ROLE_NAMES):
            await interaction.response.send_message("❌ 仅管理组可使用该命令。", ephemeral=True)
            return

        self.db.disable_welcome(interaction.guild_id)
        await interaction.response.send_message("✅ 已关闭本服新成员欢迎消息。", ephemeral=True)
