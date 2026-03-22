import logging
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

MAX_BOOKLISTS = 10
MAX_POSTS_PER_LIST = 20
PUBLIC_BOOKLIST_PAGE_SIZE = 5


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


def _is_valid_discord_url(url: str) -> bool:
    pattern = r"^https://discord\.com/channels/\d+/\d+(?:/\d+)?$"
    return re.match(pattern, url.strip()) is not None


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

        self.view.cog.db.set_user_booklist_thread_url(self.view.user_id, self.view.guild_id, url)
        notice = "✅ 已更新书单帖连结。" if url else "✅ 已清除书单帖连结。"
        embed = self.view.build_embed(extra_notice=notice)
        await interaction.response.edit_message(embed=embed, view=self.view)


class ManageBooklistView(discord.ui.View):
    def __init__(self, cog, user_id: int, guild_id: int, current_list_id: int = 0):
        super().__init__(timeout=600)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
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
                lines.append(
                    f"🆔 ID：`{idx:02}`\n"
                    f"📌 标题：{title}\n"
                    f"🔗 连结：{entry['thread_url']}\n"
                    f"📝 评价：{review}"
                )
            embed.add_field(name="帖子列表", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="帖子列表", value="暂无帖子。", inline=False)

        profile_url = self.cog.db.get_user_booklist_thread_url(self.user_id, self.guild_id)
        profile_text = f"[点击跳转]({profile_url})" if profile_url else "该用户暂无书单帖"
        embed.add_field(name="书单帖连结", value=profile_text, inline=False)

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

    @discord.ui.button(label="连结书单帖", style=discord.ButtonStyle.primary, emoji="🔗", row=1)
    async def link_booklist_thread(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LinkBooklistThreadModal(self))


class PublicBooklistPagerView(discord.ui.View):
    def __init__(self, cog, publisher_user_id: int, list_id: int, intro: str, current_page: int = 1):
        super().__init__(timeout=None)
        self.cog = cog
        self.publisher_user_id = publisher_user_id
        self.list_id = list_id
        self.intro = intro
        self.current_page = current_page

    def _build_embed_and_pages(self) -> tuple[discord.Embed, int]:
        data = self.cog.db.get_user_booklist(self.publisher_user_id, self.list_id)
        entries = data['entries']
        total_entries = len(entries)
        total_pages = max(1, (total_entries + PUBLIC_BOOKLIST_PAGE_SIZE - 1) // PUBLIC_BOOKLIST_PAGE_SIZE)
        self.current_page = max(1, min(self.current_page, total_pages))

        start = (self.current_page - 1) * PUBLIC_BOOKLIST_PAGE_SIZE
        end = start + PUBLIC_BOOKLIST_PAGE_SIZE
        page_entries = entries[start:end]

        embed = discord.Embed(
            title=f"📖 公开书单：{data['title']}（ID {self.list_id}）",
            description=f"发布者：<@{self.publisher_user_id}>\n\n{self.intro}",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow(),
        )

        if page_entries:
            lines = []
            for idx, entry in enumerate(page_entries, start + 1):
                title = _truncate(entry['thread_title'], 60)
                review = entry['review'].strip() if entry['review'] else ""
                review_text = _truncate(review, 50) if review else "（无评价）"
                lines.append(
                    f"🆔 ID：`{idx:02}`\n"
                    f"📌 标题：{title}\n"
                    f"🔗 连结：{entry['thread_url']}\n"
                    f"📝 评价：{review_text}"
                )
            embed.add_field(
                name=f"帖子列表（第 {self.current_page}/{total_pages} 页，共 {total_entries} 帖）",
                value="\n".join(lines),
                inline=False,
            )
        else:
            embed.add_field(
                name="帖子列表",
                value="该书单当前没有帖子（可能已被清空）。",
                inline=False,
            )

        return embed, total_pages

    def _update_buttons(self, total_pages: int):
        self.prev_page.disabled = self.current_page <= 1
        self.next_page.disabled = self.current_page >= total_pages

    @discord.ui.button(label="上一页", style=discord.ButtonStyle.secondary, emoji="◀️", custom_id="booklist_public:prev:v1")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        embed, total_pages = self._build_embed_and_pages()
        self._update_buttons(total_pages)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="下一页", style=discord.ButtonStyle.secondary, emoji="▶️", custom_id="booklist_public:next:v1")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        embed, total_pages = self._build_embed_and_pages()
        self._update_buttons(total_pages)
        await interaction.response.edit_message(embed=embed, view=self)

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

        view = PublicBooklistPagerView(
            self.cog,
            publisher_user_id=interaction.user.id,
            list_id=list_id,
            intro=intro,
            current_page=1
        )
        embed, total_pages = view._build_embed_and_pages()
        view._update_buttons(total_pages)

        await interaction.response.defer(ephemeral=True, thinking=True)
        message = await interaction.channel.send(embed=embed, view=view)
        self.cog.db.add_public_booklist_index(
            message_id=message.id,
            publisher_user_id=interaction.user.id,
            list_id=list_id,
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id
        )

        await interaction.followup.send(
            f"✅ 书单已公开：{message.jump_url}\n支持全员翻页；重启后仍可继续翻页。",
            ephemeral=True,
        )


class BooklistCommands(commands.Cog):
    """书单独立模块"""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    async def cog_load(self):
        """重启后恢复公开书单分页按钮；不存在的消息自动失效。"""
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
                await channel.fetch_message(message_id)
            except Exception:
                self.db.deactivate_public_booklist_index(message_id)
                continue

            # intro 不存快照，重启恢复时用简短占位文本
            view = PublicBooklistPagerView(
                self,
                publisher_user_id=publisher_user_id,
                list_id=list_id,
                intro="（书单介绍未保存快照，内容以当前书单为准）",
                current_page=1
            )
            self.bot.add_view(view, message_id=message_id)

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
        view = ManageBooklistView(self, interaction.user.id, interaction.guild_id, current_list_id=0)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="公开书单", description="公开你的书单到当前频道")
    async def publish_booklist(self, interaction: discord.Interaction):
        if not _is_thread_channel(interaction.channel):
            await interaction.response.send_message("❌ /公开书单 只能在论坛帖中使用。", ephemeral=True)
            return

        parent = interaction.channel.parent
        if not parent or parent.type != discord.ChannelType.forum:
            await interaction.response.send_message("❌ /公开书单 只能在论坛帖中使用。", ephemeral=True)
            return

        if interaction.channel.owner_id != interaction.user.id:
            await interaction.response.send_message("❌ 只有帖主（楼主）可以在本帖公开书单。", ephemeral=True)
            return

        self.db.ensure_user_booklists(interaction.user.id)
        await interaction.response.send_modal(PublicBooklistModal(self))
