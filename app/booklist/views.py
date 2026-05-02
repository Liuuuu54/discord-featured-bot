import logging

import discord

from app.booklist.constants import (
    MANAGE_BOOKLIST_PAGE_SIZE,
    MAX_BOOKLISTS,
    MAX_POSTS_PER_LIST,
    PUBLIC_BOOKLIST_PAGE_SIZE,
)
from app.booklist.formatting import _build_book_entry_block
from app.booklist.modals import (
    AddPostByUrlModal,
    DeleteEntryModal,
    EditReviewModal,
    LinkBooklistThreadModal,
    MoveEntryModal,
    RenameBooklistModal,
)

logger = logging.getLogger(__name__)

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
            embed.add_field(
                name="帖子列表",
                value=f"以下为当前页书目（第 {self.current_entry_page}/{total_pages} 页）：",
                inline=False,
            )
            for offset, entry in enumerate(page_entries, 1):
                idx = start_idx + offset
                embed.add_field(
                    name=f"ID {idx:02}",
                    value=_build_book_entry_block(entry, idx, title_max_len=40),
                    inline=False,
                )
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
            embed.add_field(
                name=f"帖子列表（第 {self.current_page}/{total_pages} 页，共 {total_entries} 帖）",
                value="以下为本页书目：",
                inline=False,
            )
            for idx, entry in enumerate(page_entries, start + 1):
                embed.add_field(
                    name=f"ID {idx:02}",
                    value=_build_book_entry_block(entry, idx),
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


