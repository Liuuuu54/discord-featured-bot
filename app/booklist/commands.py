import discord
from discord import app_commands
from discord.ext import commands

import config
from app.booklist.modals import AddToBooklistModal, PublicBooklistModal
from app.booklist.views import GuildBooklistAdminView, ManageBooklistView, PublicBooklistPagerView
from app.utils.discord_channels import is_thread_channel as _is_thread_channel
from app.utils.permissions import has_admin_permission

class BooklistCommands(commands.Cog):
    """书单独立模块"""

    booklist_group = app_commands.Group(name="书单", description="书单相关指令")

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    async def _yielded_to_webpage(self, interaction: discord.Interaction) -> bool:
        """本服已开启网页接管时，bot 书单指令让位并引导用户前往网页版。

        返回 True 表示已拦截（调用方应直接 return）。
        """
        guild_id = interaction.guild_id
        if not guild_id or not self.db.is_booklist_webpage_takeover(guild_id):
            return False

        await interaction.response.send_message(
            f"📖 本服书单已迁移至网页版，bot 端书单功能已让位。\n"
            f"请前往 👉 {config.BOOKLIST_WEBPAGE_URL}",
            ephemeral=True,
        )
        return True

    async def cog_load(self):
        """重启后校验公开书单索引；旧版带翻页按钮的消息继续恢复交互。"""
        indexes = self.db.get_active_public_booklist_indexes()
        for item in indexes:
            message_id = item['message_id']
            channel_id = item['channel_id']
            publisher_user_id = item['publisher_user_id']
            list_id = item['list_id']

            channel = self.bot.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception:
                    self.db.deactivate_public_booklist_index(message_id)
                    continue

            try:
                message = await channel.fetch_message(message_id)
            except Exception:
                self.db.deactivate_public_booklist_index(message_id)
                continue

            # 仅为旧版翻页消息恢复按钮；新版为静态多消息，不需要 View
            if message.components:
                view = PublicBooklistPagerView(
                    self,
                    publisher_user_id=publisher_user_id,
                    list_id=list_id,
                    intro="（书单介绍未保存快照，内容以当前书单为准）",
                    current_page=1
                )
                self.bot.add_view(view, message_id=message_id)

    @booklist_group.command(name="添加至书单", description="将当前帖子添加到你的书单（仅自己可见）")
    async def add_to_booklist(self, interaction: discord.Interaction):
        if await self._yielded_to_webpage(interaction):
            return
        if not _is_thread_channel(interaction.channel):
            await interaction.response.send_message("❌ 此命令只能在帖子中使用。", ephemeral=True)
            return

        await interaction.response.send_modal(AddToBooklistModal(self, interaction.channel))

    @booklist_group.command(name="管理书单", description="管理你的 10 张书单（仅自己可见）")
    async def manage_booklist(self, interaction: discord.Interaction):
        if await self._yielded_to_webpage(interaction):
            return
        self.db.ensure_user_booklists(interaction.user.id)
        view = ManageBooklistView(self, interaction.user.id, interaction.guild_id, current_list_id=0)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @booklist_group.command(name="公开书单", description="公开你的书单到当前频道")
    async def publish_booklist(self, interaction: discord.Interaction):
        if await self._yielded_to_webpage(interaction):
            return
        if not _is_thread_channel(interaction.channel):
            await interaction.response.send_message("❌ /书单 公开书单 只能在论坛帖中使用。", ephemeral=True)
            return

        parent = interaction.channel.parent
        if not parent or parent.type != discord.ChannelType.forum:
            await interaction.response.send_message("❌ /书单 公开书单 只能在论坛帖中使用。", ephemeral=True)
            return

        if interaction.channel.owner_id != interaction.user.id:
            await interaction.response.send_message("❌ 只有帖主（楼主）可以在本帖公开书单。", ephemeral=True)
            return

        self.db.ensure_user_booklists(interaction.user.id)
        await interaction.response.send_modal(PublicBooklistModal(self))

    @booklist_group.command(name="守门帖", description="将当前帖设为发言守门（仅楼主可发言，其他人只能加反应）")
    @app_commands.describe(unbind="解除当前帖的守门绑定")
    async def guard_booklist_thread(self, interaction: discord.Interaction, unbind: bool = False):
        # 守门是版务功能，独立于网页接管，不走让位 guard。
        if unbind:
            self.db.set_user_booklist_thread_url(interaction.user.id, interaction.guild_id, "")
            await interaction.response.send_message("✅ 已解除你的书单帖守门绑定。", ephemeral=True)
            return

        channel = interaction.channel
        if not _is_thread_channel(channel):
            await interaction.response.send_message("❌ 此命令只能在帖子/子区中使用。", ephemeral=True)
            return

        if channel.owner_id != interaction.user.id:
            await interaction.response.send_message("❌ 只有帖主（楼主）可以为本帖设置守门。", ephemeral=True)
            return

        whitelist_forum_id = self.db.get_booklist_thread_whitelist(interaction.guild_id)
        if whitelist_forum_id and channel.parent_id != whitelist_forum_id:
            await interaction.response.send_message("❌ 本帖不在书单帖白名单论坛内，无法设置守门。", ephemeral=True)
            return

        url = f"https://discord.com/channels/{interaction.guild_id}/{channel.id}"
        self.db.set_user_booklist_thread_url(interaction.user.id, interaction.guild_id, url)
        await interaction.response.send_message(
            "✅ 已为本帖开启书单帖守门：仅你（楼主）可发言，其他人只能添加反应。\n"
            "如需关闭，使用 `/书单 守门帖 unbind:True`。",
            ephemeral=True,
        )

    @booklist_group.command(name="全服书单列表", description="查看全服书单概览并设置书单帖白名单（管理组）")
    async def guild_booklist_overview(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ 该命令只能在服务器内使用。", ephemeral=True)
            return

        if not has_admin_permission(interaction.user, config.ADMIN_ROLE_NAMES):
            await interaction.response.send_message("❌ 仅管理组可使用该命令。", ephemeral=True)
            return

        view = GuildBooklistAdminView(self, interaction.guild_id, interaction.user.id, page=1)
        embed, _ = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
