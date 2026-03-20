import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

MAX_BOOKLISTS = 10
MAX_POSTS_PER_LIST = 20


def _is_thread_channel(channel: discord.abc.GuildChannel) -> bool:
    return isinstance(channel, discord.Thread)


def _safe_int(value: str) -> Optional[int]:
    try:
        return int(value.strip())
    except Exception:
        return None


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


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


class ManageBooklistView(discord.ui.View):
    def __init__(self, cog, user_id: int, current_list_id: int = 0):
        super().__init__(timeout=600)
        self.cog = cog
        self.user_id = user_id
        self.current_list_id = current_list_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 这是别人的书单管理页。", ephemeral=True)
            return False
        return True

    def build_embed(self, extra_notice: str = "") -> discord.Embed:
        data = self.cog.db.get_user_booklist(self.user_id, self.current_list_id)
        overview = self.cog.db.get_user_booklists_overview(self.user_id)

        embed = discord.Embed(
            title=f"📚 书单管理 | ID {self.current_list_id}",
            description=f"**标题**：{data['title']}\n**数量**：{data['post_count']}/{MAX_POSTS_PER_LIST}",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )

        if extra_notice:
            embed.add_field(name="操作结果", value=extra_notice, inline=False)

        if data['entries']:
            lines = []
            for idx, entry in enumerate(data['entries'], 1):
                title = _truncate(entry['thread_title'], 40)
                review = entry['review'].strip() if entry['review'] else "（无评价）"
                review = _truncate(review, 50)
                lines.append(f"`{idx:02}` [{title}]({entry['thread_url']})\n评价：{review}")
            embed.add_field(name="帖子列表", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="帖子列表", value="暂无帖子。", inline=False)

        overview_text = " | ".join([f"{x['list_id']}:{x['post_count']}" for x in overview])
        embed.set_footer(text=f"10 张书单概览（ID:数量） {overview_text}")
        return embed

    @discord.ui.button(label="上一张", style=discord.ButtonStyle.secondary, emoji="◀️")
    async def prev_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_list_id = (self.current_list_id - 1) % MAX_BOOKLISTS
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="下一张", style=discord.ButtonStyle.secondary, emoji="▶️")
    async def next_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_list_id = (self.current_list_id + 1) % MAX_BOOKLISTS
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="改标题", style=discord.ButtonStyle.primary, emoji="✏️")
    async def rename_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RenameBooklistModal(self))

    @discord.ui.button(label="删帖子", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_entry(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DeleteEntryModal(self))

    @discord.ui.button(label="搬移", style=discord.ButtonStyle.success, emoji="📦")
    async def move_entry(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MoveEntryModal(self))

    @discord.ui.button(label="改评价", style=discord.ButtonStyle.success, emoji="📝")
    async def edit_review(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditReviewModal(self))

    @discord.ui.button(label="刷新", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


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

        lines = []
        for idx, entry in enumerate(data['entries'], 1):
            title = _truncate(entry['thread_title'], 60)
            review = entry['review'].strip() if entry['review'] else ""
            review_text = f" | 评价：{_truncate(review, 50)}" if review else ""
            lines.append(f"`{idx:02}` [{title}]({entry['thread_url']}){review_text}")

        embed = discord.Embed(
            title=f"📖 公开书单：{data['title']}（ID {list_id}）",
            description=f"发布者：{interaction.user.mention}\n\n{intro}",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name=f"帖子列表（{data['post_count']} / {MAX_POSTS_PER_LIST}）",
            value="\n".join(lines),
            inline=False,
        )
        embed.set_footer(text="可使用下方按钮移除公开书单")

        view = PublicBooklistMessageView(self.cog, owner_id=interaction.user.id)

        await interaction.response.defer(ephemeral=True, thinking=True)
        message = await interaction.channel.send(embed=embed, view=view)
        self.cog.db.create_public_booklist_record(
            user_id=interaction.user.id,
            list_id=list_id,
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id,
            message_id=message.id,
            intro=intro,
        )

        await interaction.followup.send(
            f"✅ 书单已公开：{message.jump_url}\n你可以用公开消息下方按钮自行移除。",
            ephemeral=True,
        )


class PublicBooklistMessageView(discord.ui.View):
    def __init__(self, cog, owner_id: int):
        super().__init__(timeout=604800)
        self.cog = cog
        self.owner_id = owner_id

    @discord.ui.button(label="移除公开书单", style=discord.ButtonStyle.danger, emoji="🧹")
    async def remove_public_post(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ 只有发布者可以移除这条公开书单。", ephemeral=True)
            return

        self.cog.db.deactivate_public_booklist(interaction.user.id, interaction.message.id)
        try:
            await interaction.message.delete()
        except discord.Forbidden:
            await interaction.response.send_message("❌ 我没有删除该消息的权限，请联系管理员。", ephemeral=True)
            return


class BooklistCommands(commands.Cog):
    """书单 2.0 独立模块"""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @app_commands.command(name="添加至书单", description="将当前帖子添加到你的书单（仅自己可见）")
    async def add_to_booklist(self, interaction: discord.Interaction):
        if not _is_thread_channel(interaction.channel):
            await interaction.response.send_message("❌ 此命令只能在帖子中使用。", ephemeral=True)
            return

        self.db.ensure_user_booklists(interaction.user.id)
        await interaction.response.send_modal(AddToBooklistModal(self, interaction.channel))

    @app_commands.command(name="管理书单", description="管理你的 10 张书单（仅自己可见）")
    async def manage_booklist(self, interaction: discord.Interaction):
        self.db.ensure_user_booklists(interaction.user.id)
        view = ManageBooklistView(self, interaction.user.id, current_list_id=0)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="公开书单", description="公开你的书单到当前频道")
    async def publish_booklist(self, interaction: discord.Interaction):
        self.db.ensure_user_booklists(interaction.user.id)
        await interaction.response.send_modal(PublicBooklistModal(self))
