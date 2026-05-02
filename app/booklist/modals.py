import discord

from app.booklist.constants import PUBLIC_BOOKLIST_PAGE_SIZE
from app.booklist.formatting import _build_book_entry_block
from app.utils.discord_links import (
    is_valid_discord_url as _is_valid_discord_url,
    parse_discord_url as _parse_discord_url,
)
from app.utils.text import safe_int as _safe_int

class AddToBooklistModal(discord.ui.Modal, title="添加至书单"):
    def __init__(self, cog, thread: discord.Thread):
        super().__init__()
        self.cog = cog
        self.thread = thread

        self.list_id_input = discord.ui.TextInput(
            label="书单 ID (0~9)",
            placeholder="输入 0 到 9",
            required=True,
            max_length=1,
        )
        self.review_input = discord.ui.TextInput(
            label="帖子评价（可选）",
            placeholder="可以留空",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph,
        )

        self.add_item(self.list_id_input)
        self.add_item(self.review_input)

    async def on_submit(self, interaction: discord.Interaction):
        list_id = _safe_int(self.list_id_input.value)
        if list_id is None or not (0 <= list_id <= 9):
            await interaction.response.send_message("❌ 书单 ID 必须是 0~9。", ephemeral=True)
            return

        review = (self.review_input.value or "").strip()
        thread_url = f"https://discord.com/channels/{interaction.guild_id}/{self.thread.id}"

        success, message = self.cog.db.add_post_to_booklist(
            user_id=interaction.user.id,
            list_id=list_id,
            thread_guild_id=interaction.guild_id,
            thread_id=self.thread.id,
            thread_title=self.thread.name or f"帖子 {self.thread.id}",
            thread_url=thread_url,
            review=review,
        )

        if not success:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)
            return

        await interaction.response.send_message(
            f"✅ 已添加到书单 {list_id}。\n🧾 标题：{self.thread.name}\n📝 评价：{review or '（无）'}",
            ephemeral=True,
        )


class RenameBooklistModal(discord.ui.Modal, title="重命名书单"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.title_input = discord.ui.TextInput(
            label="新标题",
            placeholder="例如：推理神作收藏",
            required=True,
            max_length=60,
        )
        self.add_item(self.title_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_title = self.title_input.value.strip()
        if not new_title:
            await interaction.response.send_message("❌ 标题不能为空。", ephemeral=True)
            return

        self.view.cog.db.rename_user_booklist(self.view.user_id, self.view.current_list_id, new_title)
        embed = self.view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.view)


class DeleteEntryModal(discord.ui.Modal, title="删除书单帖子"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.index_input = discord.ui.TextInput(
            label="帖子序号 (1~20)",
            placeholder="输入当前页面显示的序号",
            required=True,
            max_length=2,
        )
        self.add_item(self.index_input)

    async def on_submit(self, interaction: discord.Interaction):
        index = _safe_int(self.index_input.value)
        if index is None or not (1 <= index <= 20):
            await interaction.response.send_message("❌ 序号必须在 1~20。", ephemeral=True)
            return

        success, msg = self.view.cog.db.remove_booklist_entry_by_index(
            self.view.user_id, self.view.current_list_id, index
        )
        if not success:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        embed = self.view.build_embed(extra_notice=f"✅ {msg}")
        await interaction.response.edit_message(embed=embed, view=self.view)


class MoveEntryModal(discord.ui.Modal, title="搬移书单帖子"):
    def __init__(self, view):
        super().__init__()
        self.view = view

        self.index_input = discord.ui.TextInput(
            label="帖子序号 (1~20)",
            placeholder="输入当前页面显示的序号",
            required=True,
            max_length=2,
        )
        self.target_list_input = discord.ui.TextInput(
            label="目标书单 ID (0~9)",
            placeholder="输入 0 到 9",
            required=True,
            max_length=1,
        )
        self.add_item(self.index_input)
        self.add_item(self.target_list_input)

    async def on_submit(self, interaction: discord.Interaction):
        index = _safe_int(self.index_input.value)
        target_list = _safe_int(self.target_list_input.value)

        if index is None or not (1 <= index <= 20):
            await interaction.response.send_message("❌ 序号必须在 1~20。", ephemeral=True)
            return
        if target_list is None or not (0 <= target_list <= 9):
            await interaction.response.send_message("❌ 目标书单 ID 必须是 0~9。", ephemeral=True)
            return

        success, msg = self.view.cog.db.move_booklist_entry_by_index(
            self.view.user_id,
            self.view.current_list_id,
            index,
            target_list,
        )
        if not success:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        embed = self.view.build_embed(extra_notice=f"✅ {msg}")
        await interaction.response.edit_message(embed=embed, view=self.view)


class EditReviewModal(discord.ui.Modal, title="修改帖子评价"):
    def __init__(self, view):
        super().__init__()
        self.view = view

        self.index_input = discord.ui.TextInput(
            label="帖子序号 (1~20)",
            placeholder="输入当前页面显示的序号",
            required=True,
            max_length=2,
        )
        self.review_input = discord.ui.TextInput(
            label="新评价（可留空）",
            placeholder="留空会清空原评价",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.index_input)
        self.add_item(self.review_input)

    async def on_submit(self, interaction: discord.Interaction):
        index = _safe_int(self.index_input.value)
        if index is None or not (1 <= index <= 20):
            await interaction.response.send_message("❌ 序号必须在 1~20。", ephemeral=True)
            return

        new_review = (self.review_input.value or "").strip()
        success, msg = self.view.cog.db.update_booklist_entry_review_by_index(
            self.view.user_id,
            self.view.current_list_id,
            index,
            new_review,
        )
        if not success:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        embed = self.view.build_embed(extra_notice=f"✅ {msg}")
        await interaction.response.edit_message(embed=embed, view=self.view)


class LinkBooklistThreadModal(discord.ui.Modal, title="连结书单帖"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.url_input = discord.ui.TextInput(
            label="书单帖 URL（留空可清除）",
            placeholder="https://discord.com/channels/服务器ID/频道或帖子ID",
            required=False,
            max_length=300,
            style=discord.TextStyle.short,
        )
        self.add_item(self.url_input)

    async def on_submit(self, interaction: discord.Interaction):
        url = (self.url_input.value or "").strip()
        if url and not _is_valid_discord_url(url):
            await interaction.response.send_message("❌ URL 格式错误，请填写 Discord 链接。", ephemeral=True)
            return

        if url:
            parsed = _parse_discord_url(url)
            if not parsed:
                await interaction.response.send_message("❌ URL 解析失败，请检查链接。", ephemeral=True)
                return

            guild_id, thread_id = parsed
            if self.view.cog.bot.get_guild(guild_id) is None:
                await interaction.response.send_message("❌ 该服务器未接入本 Bot，无法绑定。", ephemeral=True)
                return

            channel = self.view.cog.bot.get_channel(thread_id)
            if channel is None:
                try:
                    channel = await self.view.cog.bot.fetch_channel(thread_id)
                except Exception:
                    await interaction.response.send_message("❌ 无法读取该帖子，请检查 URL 是否正确。", ephemeral=True)
                    return

            if not isinstance(channel, discord.Thread):
                await interaction.response.send_message("❌ 该链接不是帖子链接，请绑定论坛帖 URL。", ephemeral=True)
                return

            if channel.owner_id != interaction.user.id:
                await interaction.response.send_message("❌ 只能绑定你自己作为楼主的帖子。", ephemeral=True)
                return

            whitelist_forum_id = self.view.cog.db.get_booklist_thread_whitelist(interaction.guild_id)
            if whitelist_forum_id and channel.parent_id != whitelist_forum_id:
                await interaction.response.send_message("❌ 该帖子不在白名单论坛内，无法绑定。", ephemeral=True)
                return

            # 统一归一化为帖子层级链接，避免消息链接带来的歧义
            url = f"https://discord.com/channels/{guild_id}/{thread_id}"

        self.view.cog.db.set_user_booklist_thread_url(self.view.user_id, self.view.guild_id, url)
        notice = "✅ 已更新书单帖连结。" if url else "✅ 已清除书单帖连结。"
        embed = self.view.build_embed(extra_notice=notice)
        await interaction.response.edit_message(embed=embed, view=self.view)


class AddPostByUrlModal(discord.ui.Modal, title="添加至书单（URL）"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.list_id_input = discord.ui.TextInput(
            label="书单 ID (0~9)",
            placeholder="输入 0 到 9",
            required=True,
            max_length=1,
        )
        self.url_input = discord.ui.TextInput(
            label="帖子 URL",
            placeholder="https://discord.com/channels/<guild_id>/<thread_id>",
            required=True,
            max_length=300,
        )
        self.review_input = discord.ui.TextInput(
            label="帖子评价（可选）",
            placeholder="可以留空",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.list_id_input)
        self.add_item(self.url_input)
        self.add_item(self.review_input)

    async def on_submit(self, interaction: discord.Interaction):
        list_id = _safe_int(self.list_id_input.value)
        if list_id is None or not (0 <= list_id <= 9):
            await interaction.response.send_message("❌ 书单 ID 必须是 0~9。", ephemeral=True)
            return

        raw_url = (self.url_input.value or "").strip()
        parsed = _parse_discord_url(raw_url)
        if not parsed:
            await interaction.response.send_message("❌ 帖子 URL 格式错误。", ephemeral=True)
            return

        guild_id, thread_id = parsed
        if self.view.cog.bot.get_guild(guild_id) is None:
            await interaction.response.send_message("❌ 该服务器未接入本 Bot，无法添加。", ephemeral=True)
            return

        channel = self.view.cog.bot.get_channel(thread_id)
        if channel is None:
            try:
                channel = await self.view.cog.bot.fetch_channel(thread_id)
            except Exception:
                await interaction.response.send_message("❌ 无法读取该帖子，请检查 URL 是否正确。", ephemeral=True)
                return

        if not isinstance(channel, discord.Thread):
            await interaction.response.send_message("❌ 该 URL 不是帖子链接，请提供论坛帖 URL。", ephemeral=True)
            return

        review = (self.review_input.value or "").strip()
        success, msg = self.view.cog.db.add_post_to_booklist(
            user_id=self.view.user_id,
            list_id=list_id,
            thread_guild_id=guild_id,
            thread_id=thread_id,
            thread_title=channel.name or f"帖子 {thread_id}",
            thread_url=f"https://discord.com/channels/{guild_id}/{thread_id}",
            review=review,
        )
        if not success:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        self.view.current_list_id = list_id
        embed = self.view.build_embed(extra_notice=f"✅ 已添加帖子：{channel.name}")
        await interaction.response.edit_message(embed=embed, view=self.view)


class PublicBooklistModal(discord.ui.Modal, title="公开书单"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

        self.list_id_input = discord.ui.TextInput(
            label="书单 ID (0~9)",
            placeholder="输入 0 到 9",
            required=True,
            max_length=1,
        )
        self.intro_input = discord.ui.TextInput(
            label="书单介绍（至少 50 字）",
            placeholder="写下这张书单的定位、风格、推荐理由",
            required=True,
            max_length=1200,
            style=discord.TextStyle.paragraph,
        )

        self.add_item(self.list_id_input)
        self.add_item(self.intro_input)

    async def on_submit(self, interaction: discord.Interaction):
        list_id = _safe_int(self.list_id_input.value)
        intro = (self.intro_input.value or "").strip()

        if list_id is None or not (0 <= list_id <= 9):
            await interaction.response.send_message("❌ 书单 ID 必须是 0~9。", ephemeral=True)
            return

        if len(intro) < 50:
            await interaction.response.send_message("❌ 书单介绍至少 50 字。", ephemeral=True)
            return

        data = self.cog.db.get_user_booklist(interaction.user.id, list_id)
        if data['post_count'] < 5:
            await interaction.response.send_message("❌ 该书单至少要有 5 帖才能公开。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        entries = data['entries']
        total_entries = len(entries)
        total_chunks = max(1, (total_entries + PUBLIC_BOOKLIST_PAGE_SIZE - 1) // PUBLIC_BOOKLIST_PAGE_SIZE)

        published_messages: list[discord.Message] = []
        for chunk_idx in range(total_chunks):
            start = chunk_idx * PUBLIC_BOOKLIST_PAGE_SIZE
            end = start + PUBLIC_BOOKLIST_PAGE_SIZE
            chunk_entries = entries[start:end]

            embed = discord.Embed(
                title=f"📖 公开书单：{data['title']}（ID {list_id}）",
                description=(
                    f"发布者：<@{interaction.user.id}>\n\n{intro}"
                    if chunk_idx == 0
                    else f"发布者：<@{interaction.user.id}>"
                ),
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow(),
            )

            if chunk_entries:
                embed.add_field(
                    name=f"帖子列表（第 {chunk_idx + 1}/{total_chunks} 组，共 {total_entries} 帖）",
                    value="以下为本组书目：",
                    inline=False,
                )
                for row_idx, entry in enumerate(chunk_entries, start + 1):
                    embed.add_field(
                        name=f"ID {row_idx:02}",
                        value=_build_book_entry_block(entry, row_idx),
                        inline=False,
                    )
            else:
                embed.add_field(
                    name="帖子列表",
                    value="该书单当前没有帖子（可能已被清空）。",
                    inline=False,
                )

            message = await interaction.channel.send(embed=embed)
            published_messages.append(message)
            self.cog.db.add_public_booklist_index(
                message_id=message.id,
                publisher_user_id=interaction.user.id,
                list_id=list_id,
                guild_id=interaction.guild_id,
                channel_id=interaction.channel_id
            )

        await interaction.followup.send(
            f"✅ 书单已公开，共发送 {len(published_messages)} 则。\n首则连结：{published_messages[0].jump_url}",
            ephemeral=True,
        )


