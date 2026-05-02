import logging
from datetime import datetime

import discord

import config
from app.bot.client import FeaturedMessageBot

logger = logging.getLogger(__name__)

class FeaturedRecordsView(discord.ui.View):
    """精選記錄分頁視圖"""
    def __init__(self, bot: FeaturedMessageBot, user_id: int, guild_id: int, current_page: int = 1, record_type: str = "featured"):
        super().__init__(timeout=config.VIEW_TIMEOUT)  # 使用配置的超時時間
        self.bot = bot
        self.user_id = user_id
        self.guild_id = guild_id
        self.current_page = current_page
        self.per_page = config.USER_RECORDS_PER_PAGE
        self.record_type = record_type  # "featured" 或 "referral"

    def _build_booklist_link_text(self) -> str:
        thread_url = self.bot.db.get_user_booklist_thread_url(self.user_id, self.guild_id)
        if not thread_url:
            return "該用戶暫無書單帖"
        return f"[點擊跳轉]({thread_url})"
    
    async def get_records_embed(self) -> discord.Embed:
        """獲取當前頁面的記錄嵌入訊息"""
        # 獲取用戶資訊
        user = self.bot.get_user(self.user_id)
        username = user.display_name if user else f"用戶 {self.user_id}"
        
        if self.record_type == "featured":
            # 獲取被精選記錄
            records, total_pages = self.bot.db.get_user_featured_records(
                self.user_id, self.guild_id, self.current_page, self.per_page
            )
            title = f"🏆 {username} 的被精選記錄"
            description = f"被其他用戶精選的記錄 • 第 {self.current_page} 頁，共 {max(total_pages, 1)} 頁"
            empty_description = "還沒有被精選的記錄"
        else:
            # 獲取引薦記錄（用戶精選別人的記錄）
            records, total_pages = self.bot.db.get_user_referral_records(
                self.user_id, self.guild_id, self.current_page, self.per_page
            )
            title = f"👥 {username} 的引薦記錄"
            description = f"精選其他用戶的記錄 • 第 {self.current_page} 頁，共 {max(total_pages, 1)} 頁"
            empty_description = "還沒有引薦記錄"

        embed = discord.Embed(
            title=title,
            description=description if records else empty_description,
            color=0x00ff00,
            timestamp=discord.utils.utcnow()
        )

        if records:
            for i, record in enumerate(records, 1):
                # 格式化時間
                featured_at = datetime.fromisoformat(record['featured_at'].replace('Z', '+00:00'))
                formatted_time = featured_at.strftime('%Y-%m-%d %H:%M')

                # 創建帖子超連結
                thread_link = f"https://discord.com/channels/{self.guild_id}/{record['thread_id']}"

                # 嘗試獲取帖子標題
                thread_title = None
                try:
                    channel = self.bot.get_channel(record['thread_id'])
                    if channel and hasattr(channel, 'name') and channel.name:
                        thread_title = channel.name
                    else:
                        thread_title = f"帖子 {record['thread_id']}"
                except Exception as e:
                    thread_title = f"帖子 {record['thread_id']}"
                    logger.debug(f"無法獲取帖子標題 {record['thread_id']}: {e}")

                # 創建記錄描述
                if self.record_type == "featured":
                    record_desc = f"📝 **精选原因**: {record['reason'] or '无'}\n"
                    record_desc += f"👤 **精选者**: {record['featured_by_name']}\n"
                    record_desc += f"📅 **精选时间**: {formatted_time}\n"
                else:
                    record_desc = f"👤 **被精选用户**: {record['author_name']}\n"
                    record_desc += f"📝 **精选原因**: {record['reason'] or '无'}\n"
                    record_desc += f"📅 **精选时间**: {formatted_time}\n"

                if thread_title:
                    record_desc += f"🏷️ **原帖**: [{thread_title}]({thread_link})"
                else:
                    record_desc += f"🏷️ **原帖**: [點擊查看]({thread_link})"

                embed.add_field(
                    name=f"{i}. {'被精选记录' if self.record_type == 'featured' else '引荐记录'}",
                    value=record_desc,
                    inline=False
                )

        stats = self.bot.db.get_user_stats(self.user_id, self.guild_id)
        embed.add_field(
            name="📈 精選統計",
            value=f"**被精选次数**: {stats['featured_count']} 次\n"
                  f"**引荐人数**: {stats['featuring_count']} 人",
            inline=False
        )

        embed.add_field(
            name="🔗 書單帖",
            value=self._build_booklist_link_text(),
            inline=False
        )

        if user:
            embed.set_thumbnail(url=user.display_avatar.url)

        # 更新按鈕狀態
        self.update_buttons(total_pages)

        return embed
    
    def update_buttons(self, total_pages: int):
        """更新按鈕狀態"""
        normalized_total_pages = max(total_pages, 1)
        self.first_page.disabled = self.current_page <= 1
        self.prev_page.disabled = self.current_page <= 1
        self.next_page.disabled = self.current_page >= normalized_total_pages
        self.last_page.disabled = self.current_page >= normalized_total_pages
    
    @discord.ui.button(label="第一頁", style=discord.ButtonStyle.gray, emoji="⏮️")
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 1
        embed = await self.get_records_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="上一頁", style=discord.ButtonStyle.primary, emoji="◀️")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 1:
            self.current_page -= 1
            embed = await self.get_records_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="下一頁", style=discord.ButtonStyle.primary, emoji="▶️")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.record_type == "featured":
            _, total_pages = self.bot.db.get_user_featured_records(
                self.user_id, self.guild_id, self.current_page, self.per_page
            )
        else:
            _, total_pages = self.bot.db.get_user_referral_records(
                self.user_id, self.guild_id, self.current_page, self.per_page
            )
        
        if self.current_page < total_pages:
            self.current_page += 1
            embed = await self.get_records_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="最後一頁", style=discord.ButtonStyle.gray, emoji="⏭️")
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.record_type == "featured":
            _, total_pages = self.bot.db.get_user_featured_records(
                self.user_id, self.guild_id, self.current_page, self.per_page
            )
        else:
            _, total_pages = self.bot.db.get_user_referral_records(
                self.user_id, self.guild_id, self.current_page, self.per_page
            )
        
        self.current_page = total_pages
        embed = await self.get_records_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="被精選", style=discord.ButtonStyle.success, emoji="🏆")
    async def switch_to_featured(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.record_type != "featured":
            self.record_type = "featured"
            self.current_page = 1  # 重置到第一頁
            embed = await self.get_records_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("✅ 當前已是被精選記錄模式", ephemeral=True)
    
    @discord.ui.button(label="引薦記錄", style=discord.ButtonStyle.success, emoji="👥")
    async def switch_to_referral(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.record_type != "referral":
            self.record_type = "referral"
            self.current_page = 1  # 重置到第一頁
            embed = await self.get_records_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("✅ 當前已是引薦記錄模式", ephemeral=True)

class EnhancedRankingView(discord.ui.View):
    """增强排行榜视图 - 支持引荐人数排行，支持时间范围"""
    def __init__(self, bot: FeaturedMessageBot, guild_id: int, current_page: int = 1, start_date: str = None, end_date: str = None):
        super().__init__(timeout=config.VIEW_TIMEOUT)  # 使用配置的超時時間
        self.bot = bot
        self.guild_id = guild_id
        self.current_page = current_page
        self.per_page = config.RANKING_PER_PAGE
        self.per_page = config.RANKING_PER_PAGE
        self.start_date = start_date
        self.end_date = end_date
    
    async def get_ranking_embed(self) -> discord.Embed:
        """獲取當前頁面的排行榜嵌入訊息"""
        # 獲取引薦人數排行榜數據
        ranking_data, total_pages = self.bot.db.get_referral_ranking(self.guild_id, self.current_page, self.per_page, self.start_date, self.end_date)
        title = "👥 引薦人數排行榜"
        
        # 根据时间范围调整描述
        if self.start_date and self.end_date:
            description = f"時間範圍: {self.start_date} 至 {self.end_date} • 第 {self.current_page} 頁，共 {total_pages} 頁"
        elif self.start_date:
            description = f"時間範圍: {self.start_date} 至今 • 第 {self.current_page} 頁，共 {total_pages} 頁"
        elif self.end_date:
            description = f"時間範圍: 開始至 {self.end_date} • 第 {self.current_page} 頁，共 {total_pages} 頁"
        else:
            description = f"精選留言引薦統計 • 第 {self.current_page} 頁，共 {total_pages} 頁"
        
        empty_description = "還沒有引薦記錄"
        
        if not ranking_data:
            embed = discord.Embed(
                title=title,
                description=empty_description,
                color=0x00ff00,
                timestamp=discord.utils.utcnow()
            )
            return embed
        
        # 計算當前頁的起始排名
        start_rank = (self.current_page - 1) * self.per_page + 1
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=0x00ff00,
            timestamp=discord.utils.utcnow()
        )
        
        for i, rank_info in enumerate(ranking_data):
            # 獲取用戶資訊
            user = self.bot.get_user(rank_info['user_id'])
            username = user.display_name if user else rank_info['username']
            
            # 計算實際排名
            actual_rank = start_rank + i
            
            value = f"引薦人數: {rank_info['referral_count']} 人"
            
            embed.add_field(
                name=f"{actual_rank}. {username}",
                value=value,
                inline=False
            )
        
        # 更新按鈕狀態
        self.update_buttons(total_pages)
        
        return embed
    
    def update_buttons(self, total_pages: int):
        """更新按鈕狀態"""
        # 第一頁按鈕
        self.children[0].disabled = self.current_page <= 1
        # 上一頁按鈕
        self.children[1].disabled = self.current_page <= 1
        # 下一頁按鈕
        self.children[2].disabled = self.current_page >= total_pages
        # 最後一頁按鈕
        self.children[3].disabled = self.current_page >= total_pages
    
    @discord.ui.button(label="第一頁", style=discord.ButtonStyle.gray, emoji="⏮️")
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 1
        embed = await self.get_ranking_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="上一頁", style=discord.ButtonStyle.primary, emoji="◀️")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 1:
            self.current_page -= 1
            embed = await self.get_ranking_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="下一頁", style=discord.ButtonStyle.primary, emoji="▶️")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        _, total_pages = self.bot.db.get_referral_ranking(self.guild_id, self.current_page, self.per_page, self.start_date, self.end_date)
        
        if self.current_page < total_pages:
            self.current_page += 1
            embed = await self.get_ranking_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="最後一頁", style=discord.ButtonStyle.gray, emoji="⏭️")
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        _, total_pages = self.bot.db.get_referral_ranking(self.guild_id, self.current_page, self.per_page, self.start_date, self.end_date)
        
        self.current_page = total_pages
        embed = await self.get_ranking_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    # 移除積分排行按鈕，僅保留引薦排行
    @discord.ui.button(label="引薦排行", style=discord.ButtonStyle.success, emoji="👥", disabled=True)
    async def switch_to_referral(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ 當前已是引薦排行模式", ephemeral=True)

