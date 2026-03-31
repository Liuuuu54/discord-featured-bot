import logging
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
import config

logger = logging.getLogger(__name__)

MAX_BOOKLISTS = 10
MAX_POSTS_PER_LIST = 20
PUBLIC_BOOKLIST_PAGE_SIZE = 5
MANAGE_BOOKLIST_PAGE_SIZE = 5


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


def _split_blocks_into_fields(blocks: list[str], max_field_len: int = 1000) -> list[str]:
    if not blocks:
        return []

    fields: list[str] = []
    current = ""
    separator = "\n\n"

    for block in blocks:
        if len(block) > max_field_len:
            block = _truncate(block, max_field_len)

        candidate = f"{current}{separator}{block}" if current else block
        if len(candidate) <= max_field_len:
            current = candidate
            continue

        if current:
            fields.append(current)
        current = block

    if current:
        fields.append(current)
    return fields


def _build_book_entry_block(entry: dict, index: int, *, title_max_len: int = 60, review_max_len: Optional[int] = None) -> str:
    title = _truncate(entry['thread_title'], title_max_len)
    review = entry['review'].strip() if entry['review'] else ""
    if review and review_max_len is not None:
        review = _truncate(review, review_max_len)
    review_text = review if review else "（无评价）"
    return (
        f"🆔 ID：`{index:02}`\n"
        f"📌 标题：{title}\n"
        f"🔗 连结：{entry['thread_url']}\n"
        f"📝 评价：{review_text}"
    )


def _is_valid_discord_url(url: str) -> bool:
    pattern = r"^https://discord\.com/channels/\d+/\d+(?:/\d+)?$"
    return re.match(pattern, url.strip()) is not None


def _parse_discord_url(url: str) -> Optional[tuple[int, int]]:
    match = re.match(r"^https://discord\.com/channels/(\d+)/(\d+)(?:/\d+)?$", url.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _has_booklist_admin_permission(member: discord.Member) -> bool:
    has_role = any(role.name in config.ADMIN_ROLE_NAMES for role in member.roles)
    has_perm = member.guild_permissions.manage_messages or member.guild_permissions.administrator
    return has_role or has_perm


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


class ManageBooklistView(discord.ui.View):
    def __init__(self, cog, user_id: int, guild_id: int, current_list_id: int = 0):
        super().__init__(timeout=600)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.current_list_id = current_list_id
        self.current_entry_page = 1

        # 功能性重排：书单切换、帖子分页、管理动作
        self.clear_items()
        self.add_item(self.prev_list)
        self.add_item(self.next_list)
        self.add_item(self.prev_entries_page)
        self.add_item(self.next_entries_page)
        self.add_item(self.add_post_by_url)
        self.add_item(self.delete_entry)
        self.add_item(self.move_entry)
        self.add_item(self.rename_list)
        self.add_item(self.edit_review)
        self.add_item(self.link_booklist_thread)
        self.add_item(self.refresh)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 这是别人的书单管理页。", ephemeral=True)
            return False
        return True

    def build_embed(self, extra_notice: str = "") -> discord.Embed:
        data = self.cog.db.get_user_booklist(self.user_id, self.current_list_id)
        overview = self.cog.db.get_user_booklists_overview(self.user_id)
        total_entries = len(data['entries'])
        total_pages = max(1, (total_entries + MANAGE_BOOKLIST_PAGE_SIZE - 1) // MANAGE_BOOKLIST_PAGE_SIZE)
        self.current_entry_page = max(1, min(self.current_entry_page, total_pages))
        start_idx = (self.current_entry_page - 1) * MANAGE_BOOKLIST_PAGE_SIZE
        end_idx = start_idx + MANAGE_BOOKLIST_PAGE_SIZE
        page_entries = data['entries'][start_idx:end_idx]
        self.prev_entries_page.disabled = self.current_entry_page <= 1
        self.next_entries_page.disabled = self.current_entry_page >= total_pages

        embed = discord.Embed(
            title=f"📚 书单管理 | ID {self.current_list_id}",
            description=f"**标题**：{data['title']}\n**数量**：{data['post_count']}/{MAX_POSTS_PER_LIST}",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )

        if extra_notice:
            embed.add_field(name="操作结果", value=extra_notice, inline=False)

        if page_entries:
            lines = []
            for offset, entry in enumerate(page_entries, 1):
                idx = start_idx + offset
                lines.append(_build_book_entry_block(entry, idx, title_max_len=40, review_max_len=50))
            field_values = _split_blocks_into_fields(lines)
            for idx, field_value in enumerate(field_values):
                field_name = "帖子列表" if idx == 0 else f"帖子列表（续 {idx}）"
                embed.add_field(name=field_name, value=field_value, inline=False)
        else:
            embed.add_field(name="帖子列表", value="暂无帖子。", inline=False)

        profile_url = self.cog.db.get_user_booklist_thread_url(self.user_id, self.guild_id)
        profile_text = f"[点击跳转]({profile_url})" if profile_url else "该用户暂无书单帖"
        embed.add_field(name="书单帖连结", value=profile_text, inline=False)

        overview_text = " | ".join([f"{x['list_id']}:{x['post_count']}" for x in overview])
        embed.set_footer(
            text=(
                f"书单页码 {self.current_entry_page}/{total_pages}（每页 {MANAGE_BOOKLIST_PAGE_SIZE} 帖）"
                f" | 10 张书单概览（ID:数量） {overview_text}"
            )
        )
        return embed

    @discord.ui.button(label="上一张", style=discord.ButtonStyle.secondary, emoji="📚", row=0)
    async def prev_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        old_list_id = self.current_list_id
        old_entry_page = self.current_entry_page
        self.current_list_id = (self.current_list_id - 1) % MAX_BOOKLISTS
        self.current_entry_page = 1
        try:
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        except Exception:
            self.current_list_id = old_list_id
            self.current_entry_page = old_entry_page
            logger.exception("切换到上一张书单失败，已回滚索引")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ 切换失败，已回滚到原书单。", ephemeral=True)
            else:
                await interaction.followup.send("❌ 切换失败，已回滚到原书单。", ephemeral=True)

    @discord.ui.button(label="下一张", style=discord.ButtonStyle.secondary, emoji="📚", row=0)
    async def next_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        old_list_id = self.current_list_id
        old_entry_page = self.current_entry_page
        self.current_list_id = (self.current_list_id + 1) % MAX_BOOKLISTS
        self.current_entry_page = 1
        try:
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        except Exception:
            self.current_list_id = old_list_id
            self.current_entry_page = old_entry_page
            logger.exception("切换到下一张书单失败，已回滚索引")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ 切换失败，已回滚到原书单。", ephemeral=True)
            else:
                await interaction.followup.send("❌ 切换失败，已回滚到原书单。", ephemeral=True)

    @discord.ui.button(label="上一页", style=discord.ButtonStyle.primary, emoji="📄", row=1)
    async def prev_entries_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_entry_page > 1:
            self.current_entry_page -= 1
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="下一页", style=discord.ButtonStyle.primary, emoji="📄", row=1)
    async def next_entries_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_entry_page += 1
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="改标题", style=discord.ButtonStyle.primary, emoji="✏️", row=2)
    async def rename_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RenameBooklistModal(self))

    @discord.ui.button(label="删帖子", style=discord.ButtonStyle.danger, emoji="🗑️", row=2)
    async def delete_entry(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DeleteEntryModal(self))

    @discord.ui.button(label="搬帖子", style=discord.ButtonStyle.success, emoji="📦", row=2)
    async def move_entry(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MoveEntryModal(self))

    @discord.ui.button(label="改评价", style=discord.ButtonStyle.success, emoji="📝", row=3)
    async def edit_review(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditReviewModal(self))

    @discord.ui.button(label="刷新", style=discord.ButtonStyle.secondary, emoji="🔄", row=3)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="连结书单帖", style=discord.ButtonStyle.primary, emoji="🔗", row=4)
    async def link_booklist_thread(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LinkBooklistThreadModal(self))

    @discord.ui.button(label="加帖子", style=discord.ButtonStyle.success, emoji="➕", row=4)
    async def add_post_by_url(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddPostByUrlModal(self))


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
            lines = [_build_book_entry_block(entry, idx) for idx, entry in enumerate(page_entries, start + 1)]
            field_values = _split_blocks_into_fields(lines)
            for field_idx, field_value in enumerate(field_values):
                field_name = (
                    f"帖子列表（第 {self.current_page}/{total_pages} 页，共 {total_entries} 帖）"
                    if field_idx == 0
                    else f"帖子列表（续 {field_idx}）"
                )
                embed.add_field(name=field_name, value=field_value, inline=False)
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

            lines = [_build_book_entry_block(entry, row_idx) for row_idx, entry in enumerate(chunk_entries, start + 1)]
            field_values = _split_blocks_into_fields(lines)

            if field_values:
                for field_idx, field_value in enumerate(field_values):
                    field_name = (
                        f"帖子列表（第 {chunk_idx + 1}/{total_chunks} 组，共 {total_entries} 帖）"
                        if field_idx == 0
                        else f"帖子列表（续 {field_idx}）"
                    )
                    embed.add_field(name=field_name, value=field_value, inline=False)
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


class GuildBooklistAdminView(discord.ui.View):
    def __init__(self, cog, guild_id: int, operator_id: int, page: int = 1):
        super().__init__(timeout=600)
        self.cog = cog
        self.guild_id = guild_id
        self.operator_id = operator_id
        self.page = page
        self.per_page = 10

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.operator_id:
            await interaction.response.send_message("❌ 这是他人的管理面板。", ephemeral=True)
            return False
        return True

    def build_embed(self) -> tuple[discord.Embed, int]:
        rows, total_pages = self.cog.db.get_guild_booklist_summary(self.guild_id, self.page, self.per_page)
        whitelist_forum_id = self.cog.db.get_booklist_thread_whitelist(self.guild_id)

        embed = discord.Embed(
            title="📚 全服书单列表",
            description=f"本服有书单内容的用户（第 {self.page}/{total_pages} 页）",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        if whitelist_forum_id:
            embed.add_field(
                name="🔒 书单帖白名单",
                value=f"<#{whitelist_forum_id}>（仅该论坛下帖子可绑定）",
                inline=False
            )
        else:
            embed.add_field(
                name="🔓 书单帖白名单",
                value="未设置（允许任意论坛帖绑定）",
                inline=False
            )

        if rows:
            lines = []
            for idx, row in enumerate(rows, 1):
                thread_url = self.cog.db.get_user_booklist_thread_url(row['user_id'], self.guild_id)
                thread_text = f"[点击跳转]({thread_url})" if thread_url else "未绑定"
                lines.append(
                    f"`{idx:02}` 👤 <@{row['user_id']}> | 📚 非空书单: {row['active_list_count']} | 🔗 书单连结帖: {thread_text}"
                )
            embed.add_field(name="用户概览", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="用户概览", value="暂无用户创建书单内容。", inline=False)

        self.prev_page.disabled = self.page <= 1
        self.next_page.disabled = self.page >= total_pages
        return embed, total_pages

    @discord.ui.button(label="上一页", style=discord.ButtonStyle.secondary, emoji="◀️")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        embed, _ = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="下一页", style=discord.ButtonStyle.secondary, emoji="▶️")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        embed, _ = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="设为当前论坛白名单", style=discord.ButtonStyle.primary, emoji="📌", row=1)
    async def set_whitelist_current_forum(self, interaction: discord.Interaction, button: discord.ui.Button):
        forum_channel = None
        if isinstance(interaction.channel, discord.ForumChannel):
            forum_channel = interaction.channel
        elif isinstance(interaction.channel, discord.Thread) and interaction.channel.parent and interaction.channel.parent.type == discord.ChannelType.forum:
            forum_channel = interaction.channel.parent

        if forum_channel is None:
            await interaction.response.send_message("❌ 请在论坛频道或其帖子内使用该按钮。", ephemeral=True)
            return

        self.cog.db.set_booklist_thread_whitelist(self.guild_id, forum_channel.id)
        embed, _ = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="清除白名单", style=discord.ButtonStyle.danger, emoji="🧹", row=1)
    async def clear_whitelist(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.db.clear_booklist_thread_whitelist(self.guild_id)
        embed, _ = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="解绑全服书单帖连结", style=discord.ButtonStyle.danger, emoji="🧨", row=2)
    async def clear_all_links(self, interaction: discord.Interaction, button: discord.ui.Button):
        affected = self.cog.db.clear_all_booklist_thread_links_in_guild(self.guild_id)
        embed, _ = self.build_embed()
        embed.add_field(name="批量操作结果", value=f"✅ 已清除 {affected} 条书单帖连结绑定。", inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="刷新", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, _ = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)


class BooklistCommands(commands.Cog):
    """书单独立模块"""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

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

    @app_commands.command(name="添加至书单", description="将当前帖子添加到你的书单（仅自己可见）")
    async def add_to_booklist(self, interaction: discord.Interaction):
        if not _is_thread_channel(interaction.channel):
            await interaction.response.send_message("❌ 此命令只能在帖子中使用。", ephemeral=True)
            return

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

    @app_commands.command(name="全服书单列表", description="查看全服书单概览并设置书单帖白名单（管理组）")
    async def guild_booklist_overview(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ 该命令只能在服务器内使用。", ephemeral=True)
            return

        if not _has_booklist_admin_permission(interaction.user):
            await interaction.response.send_message("❌ 仅管理组可使用该命令。", ephemeral=True)
            return

        view = GuildBooklistAdminView(self, interaction.guild_id, interaction.user.id, page=1)
        embed, _ = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
