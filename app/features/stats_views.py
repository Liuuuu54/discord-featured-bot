import asyncio
import logging
from datetime import datetime

import discord

import config
from app.bot.client import FeaturedMessageBot

logger = logging.getLogger(__name__)

class ThreadStatsView(discord.ui.View):
    """帖子統計分頁視圖"""
    def __init__(self, bot: FeaturedMessageBot, thread_id: int, guild_id: int, current_page: int = 1, sort_mode: str = "time"):
        super().__init__(timeout=config.VIEW_TIMEOUT)  # 使用配置的超時時間
        self.bot = bot
        self.thread_id = thread_id
        self.guild_id = guild_id
        self.current_page = current_page
        self.per_page = config.THREAD_STATS_PER_PAGE
        self.sort_mode = sort_mode  # "time" 或 "reactions"
    
    async def get_stats_embed(self) -> discord.Embed:
        """獲取當前頁面的統計嵌入訊息"""
        # 獲取所有統計數據
        all_stats = self.bot.db.get_thread_stats(self.thread_id)
        
        if not all_stats:
            embed = discord.Embed(
                        title="📊 帖子精选统计",
        description="此帖子还没有精选记录",
                color=discord.Color.light_grey(),
                timestamp=discord.utils.utcnow()
            )
            return embed
        
        # 記錄開始時間
        start_time = datetime.now()
        
        # 根據排序模式處理數據
        if self.sort_mode == "reactions":
            # 讚數排序：需要獲取所有消息的表情符號數量
            stats_with_reactions = []
            for stat in all_stats:
                reaction_count = await self.get_message_reaction_count(stat['message_id'])
                stats_with_reactions.append({
                    **stat,
                    'reaction_count': reaction_count
                })
            
            # 按表情符號數量降序排序
            all_stats = sorted(stats_with_reactions, key=lambda x: x['reaction_count'], reverse=True)
        else:
            # 時間排序：已經是默認的時間排序（精選時間）
            pass
        
        # 計算分頁
        total_records = len(all_stats)
        total_pages = (total_records + self.per_page - 1) // self.per_page
        start_idx = (self.current_page - 1) * self.per_page
        end_idx = min(start_idx + self.per_page, total_records)
        current_stats = all_stats[start_idx:end_idx]
        
        # 根據排序模式設置標題和描述
        if self.sort_mode == "reactions":
            title = "📊 帖子精选统计 (按讚數排序)"
            description = f"共 {total_records} 条精选记录 • 第 {self.current_page} 页，共 {total_pages} 页 • 按讚數排序"
        else:
            title = "📊 帖子精选统计 (按時間排序)"
            description = f"共 {total_records} 条精选记录 • 第 {self.current_page} 页，共 {total_pages} 页 • 按精選時間排序"
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        for i, stat in enumerate(current_stats, start_idx + 1):
            # 格式化時間
            try:
                featured_time = datetime.fromisoformat(stat['featured_at'].replace('Z', '+00:00'))
                formatted_time = featured_time.strftime("%Y-%m-%d %H:%M")
            except:
                formatted_time = stat['featured_at']
            
            # 創建留言連結
            message_link = f"https://discord.com/channels/{self.guild_id}/{self.thread_id}/{stat['message_id']}"
            
            # 實時獲取表情符號統計
            reaction_count = await self.get_message_reaction_count(stat['message_id'])
            
            # 構建記錄內容
            record_content = f"**精选留言**: [点击查看]({message_link})\n"
            record_content += f"**時間**: {formatted_time}"
            
            # 添加表情符號統計
            if reaction_count > 0:
                record_content += f"\n**👍 最高表情數**: {reaction_count}"
            
            # 如果有精选原因，添加到内容中
            if stat.get('reason'):
                record_content += f"\n**精选原因**: {stat['reason']}"
            
            embed.add_field(
                name=f"{i}. {stat['author_name']}",
                value=record_content,
                inline=False
            )
        
        # 計算並記錄處理時間
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"📊 帖子統計處理完成 - 頁面 {self.current_page}, 排序模式: {self.sort_mode}, 處理 {len(current_stats)} 條記錄, 耗時 {processing_time:.2f}秒")
        
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
        embed = await self.get_stats_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="上一頁", style=discord.ButtonStyle.primary, emoji="◀️")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 1:
            self.current_page -= 1
            embed = await self.get_stats_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="下一頁", style=discord.ButtonStyle.primary, emoji="▶️")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        all_stats = self.bot.db.get_thread_stats(self.thread_id)
        total_pages = (len(all_stats) + self.per_page - 1) // self.per_page
        
        if self.current_page < total_pages:
            self.current_page += 1
            embed = await self.get_stats_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="最後一頁", style=discord.ButtonStyle.gray, emoji="⏭️")
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        all_stats = self.bot.db.get_thread_stats(self.thread_id)
        total_pages = (len(all_stats) + self.per_page - 1) // self.per_page
        
        self.current_page = total_pages
        embed = await self.get_stats_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="時間排序", style=discord.ButtonStyle.success, emoji="⏰")
    async def sort_by_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.sort_mode != "time":
            self.sort_mode = "time"
            self.current_page = 1  # 重置到第一頁
            embed = await self.get_stats_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("✅ 當前已是時間排序模式", ephemeral=True)
    
    @discord.ui.button(label="讚數排序", style=discord.ButtonStyle.success, emoji="👍")
    async def sort_by_reactions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.sort_mode != "reactions":
            self.sort_mode = "reactions"
            self.current_page = 1  # 重置到第一頁
            embed = await self.get_stats_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("✅ 當前已是讚數排序模式", ephemeral=True)
    
    async def get_message_reaction_count(self, message_id: int) -> int:
        """獲取消息的最高表情符號數量（帶緩存）"""
        # 簡單的內存緩存，避免短時間內重複請求
        cache_key = f"{self.thread_id}_{message_id}"
        if hasattr(self, '_reaction_cache') and cache_key in self._reaction_cache:
            cache_time, count = self._reaction_cache[cache_key]
            # 緩存5秒
            if (datetime.now() - cache_time).total_seconds() < 5:
                return count
        
        try:
            # 獲取消息對象
            message = await self.bot.get_channel(self.thread_id).fetch_message(message_id)
            
            if not message or not message.reactions:
                return 0
            
            # 計算所有表情符號中的最高數量
            max_count = 0
            for reaction in message.reactions:
                if reaction.count > max_count:
                    max_count = reaction.count
            
            # 緩存結果
            if not hasattr(self, '_reaction_cache'):
                self._reaction_cache = {}
            self._reaction_cache[cache_key] = (datetime.now(), max_count)
            
            return max_count
            
        except Exception as e:
            # 如果無法獲取消息或表情符號，返回 0
            logger.debug(f"無法獲取消息 {message_id} 的表情符號: {e}")
            return 0

class AllFeaturedMessagesView(discord.ui.View):
    """全服精選留言分頁視圖"""
    def __init__(self, bot: FeaturedMessageBot, guild_id: int, current_page: int = 1, 
                 sort_mode: str = "time", start_date: str = None, end_date: str = None):
        super().__init__(timeout=config.VIEW_TIMEOUT)  # 使用配置的超時時間
        self.bot = bot
        self.guild_id = guild_id
        self.current_page = current_page
        self.per_page = config.RECORDS_PER_PAGE  # 使用配置的每頁記錄數
        self.sort_mode = sort_mode  # "time" 或 "reactions"
        self.start_date = start_date
        self.end_date = end_date
        self._reactions_cache = {}  # 緩存表情符號數量
        self._sorted_messages = None  # 緩存排序後的消息
    
    async def get_messages_embed(self, interaction: discord.Interaction = None) -> discord.Embed:
        """獲取當前頁面的全服精選留言嵌入訊息"""
        # 記錄開始時間
        start_time = datetime.now()
        
        # 根據排序模式獲取數據
        if self.sort_mode == "reactions":
            # 讚數排序：需要獲取所有記錄進行全局排序
            all_messages, _ = self.bot.db.get_all_featured_messages(
                self.guild_id, 1, 10000,  # 獲取所有記錄
                "time", self.start_date, self.end_date  # 先按時間排序獲取
            )
            
            if not all_messages:
                embed = discord.Embed(
                    title="🌟 全服精選留言",
                    description="目前沒有精選留言記錄",
                    color=discord.Color.light_grey(),
                    timestamp=discord.utils.utcnow()
                )
                return embed
            
            # 檢查是否有緩存的排序結果
            cache_key = f"{self.start_date}_{self.end_date}"
            if self._sorted_messages is None or cache_key not in self._sorted_messages:
                # 需要重新掃描
                messages_with_reactions = []
                total_messages = len(all_messages)
                progress_message = None  # 單一進度條訊息
                
                # 發送初始進度條訊息
                if interaction:
                    try:
                        initial_embed = discord.Embed(
                            title="🌟 全服精選留言 - 掃描中",
                            description="正在掃描所有精選留言的表情符號數量...\n這可能需要一些時間，請稍候。",
                            color=discord.Color.blue(),
                            timestamp=discord.utils.utcnow()
                        )
                        progress_message = await interaction.followup.send(embed=initial_embed, ephemeral=True)
                    except:
                        pass  # 如果發送失敗，繼續執行
                
                for i, msg in enumerate(all_messages, 1):
                    # 更新進度條（每10個或最後一個）
                    if interaction and progress_message and (i % 10 == 0 or i == total_messages):
                        progress = (i / total_messages) * 100
                        progress_bar = self.create_progress_bar(progress)
                        
                        progress_embed = discord.Embed(
                            title="🌟 全服精選留言 - 掃描中",
                            description=f"正在掃描表情符號數量...\n{progress_bar} {progress:.1f}% ({i}/{total_messages})",
                            color=discord.Color.blue(),
                            timestamp=discord.utils.utcnow()
                        )
                        try:
                            await progress_message.edit(embed=progress_embed)
                        except:
                            pass  # 如果編輯失敗，繼續執行
                    
                    # 獲取表情符號數量
                    reaction_count = await self.get_message_reaction_count(msg['thread_id'], msg['message_id'])
                    messages_with_reactions.append({
                        **msg,
                        'reaction_count': reaction_count
                    })
                    
                    # 添加延遲以避免 Discord API 限制
                    if i % 5 == 0:  # 每5個請求後稍作延遲
                        await asyncio.sleep(0.1)
                
                # 按表情符號數量降序排序
                all_messages_sorted = sorted(messages_with_reactions, key=lambda x: x['reaction_count'], reverse=True)
                
                # 緩存結果
                if self._sorted_messages is None:
                    self._sorted_messages = {}
                self._sorted_messages[cache_key] = all_messages_sorted
            else:
                # 使用緩存的結果
                all_messages_sorted = self._sorted_messages[cache_key]
            
            # 計算分頁
            total_records = len(all_messages_sorted)
            total_pages = (total_records + self.per_page - 1) // self.per_page
            start_idx = (self.current_page - 1) * self.per_page
            end_idx = min(start_idx + self.per_page, total_records)
            messages = all_messages_sorted[start_idx:end_idx]
        else:
            # 時間排序：使用原有的分頁邏輯
            messages, total_pages = self.bot.db.get_all_featured_messages(
                self.guild_id, self.current_page, self.per_page, 
                self.sort_mode, self.start_date, self.end_date
            )
            
            if not messages:
                embed = discord.Embed(
                    title="🌟 全服精選留言",
                    description="目前沒有精選留言記錄",
                    color=discord.Color.light_grey(),
                    timestamp=discord.utils.utcnow()
                )
                return embed
        
        # 根據排序模式設置標題和描述
        if self.sort_mode == "reactions":
            title = "🌟 全服精選留言 (按讚數排序)"
            description = f"共 {len(messages)} 条精选记录 • 第 {self.current_page} 页，共 {total_pages} 页 • 按讚數排序"
        else:
            title = "🌟 全服精選留言 (按時間排序)"
            description = f"共 {len(messages)} 条精选记录 • 第 {self.current_page} 页，共 {total_pages} 页 • 按精選時間排序"
        
        # 添加時間範圍信息
        if self.start_date or self.end_date:
            time_range = "時間範圍: "
            if self.start_date and self.end_date:
                time_range += f"{self.start_date} 至 {self.end_date}"
            elif self.start_date:
                time_range += f"{self.start_date} 至今"
            elif self.end_date:
                time_range += f"開始至 {self.end_date}"
            description += f"\n{time_range}"
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        for i, msg in enumerate(messages, 1):
            # 格式化時間
            try:
                featured_time = datetime.fromisoformat(msg['featured_at'].replace('Z', '+00:00'))
                formatted_time = featured_time.strftime("%Y-%m-%d %H:%M")
            except:
                formatted_time = msg['featured_at']
            
            # 創建留言連結
            message_link = f"https://discord.com/channels/{self.guild_id}/{msg['thread_id']}/{msg['message_id']}"
            
            # 嘗試獲取帖子標題
            thread_title = await self.get_thread_title(msg['thread_id'])
            
            # 構建記錄內容
            record_content = f"**作者**: {msg['author_name']}\n"
            record_content += f"**精选者**: {msg['featured_by_name']}\n"
            record_content += f"**時間**: {formatted_time}\n"
            
            # 添加表情符號統計（如果是讚數排序模式）
            if self.sort_mode == "reactions" and 'reaction_count' in msg:
                record_content += f"**👍 最高表情數**: {msg['reaction_count']}\n"
            
            # 如果有精选原因，添加到内容中
            if msg.get('reason'):
                record_content += f"**精选原因**: {msg['reason']}\n"
            
            # 添加留言連結
            if thread_title:
                record_content += f"**原帖**: [{thread_title}]({message_link})"
            else:
                record_content += f"**留言連結**: [点击查看]({message_link})"
            
            embed.add_field(
                name=f"{i}. 精选留言",
                value=record_content,
                inline=False
            )
        
        # 計算並記錄處理時間
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"🌟 全服精選留言處理完成 - 頁面 {self.current_page}, 排序模式: {self.sort_mode}, 處理 {len(messages)} 條記錄, 耗時 {processing_time:.2f}秒")
        
        # 更新按鈕狀態
        self.update_buttons(total_pages)
        
        return embed
    
    def create_progress_bar(self, percentage: float, width: int = 20) -> str:
        """創建進度條字符串"""
        filled = int(width * percentage / 100)
        empty = width - filled
        return "█" * filled + "░" * empty
    
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
        embed = await self.get_messages_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="上一頁", style=discord.ButtonStyle.primary, emoji="◀️")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 1:
            self.current_page -= 1
            embed = await self.get_messages_embed(interaction)
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="下一頁", style=discord.ButtonStyle.primary, emoji="▶️")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 獲取總頁數
        if self.sort_mode == "reactions":
            # 讚數排序：需要重新計算總頁數
            all_messages, _ = self.bot.db.get_all_featured_messages(
                self.guild_id, 1, 10000, "time", self.start_date, self.end_date
            )
            total_pages = (len(all_messages) + self.per_page - 1) // self.per_page
        else:
            # 時間排序：使用數據庫查詢
            messages, total_pages = self.bot.db.get_all_featured_messages(
                self.guild_id, self.current_page, self.per_page, 
                self.sort_mode, self.start_date, self.end_date
            )
        
        if self.current_page < total_pages:
            # 如果是讚數排序，先回應交互避免超時
            if self.sort_mode == "reactions":
                await interaction.response.defer()
            
            self.current_page += 1
            embed = await self.get_messages_embed(interaction)
            
            if self.sort_mode == "reactions":
                # 使用 followup 更新訊息
                try:
                    await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)
                except:
                    await interaction.followup.send(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="最後一頁", style=discord.ButtonStyle.gray, emoji="⏭️")
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 獲取總頁數
        if self.sort_mode == "reactions":
            # 讚數排序：需要重新計算總頁數
            all_messages, _ = self.bot.db.get_all_featured_messages(
                self.guild_id, 1, 10000, "time", self.start_date, self.end_date
            )
            total_pages = (len(all_messages) + self.per_page - 1) // self.per_page
        else:
            # 時間排序：使用數據庫查詢
            messages, total_pages = self.bot.db.get_all_featured_messages(
                self.guild_id, self.current_page, self.per_page, 
                self.sort_mode, self.start_date, self.end_date
            )
        
        # 如果是讚數排序，先回應交互避免超時
        if self.sort_mode == "reactions":
            await interaction.response.defer()
        
        self.current_page = total_pages
        embed = await self.get_messages_embed(interaction)
        
        if self.sort_mode == "reactions":
            # 使用 followup 更新訊息
            try:
                await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)
            except:
                await interaction.followup.send(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="時間排序", style=discord.ButtonStyle.success, emoji="⏰")
    async def sort_by_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.sort_mode != "time":
            # 先回應交互，避免超時
            await interaction.response.defer()
            
            self.sort_mode = "time"
            self.current_page = 1  # 重置到第一頁
            embed = await self.get_messages_embed(interaction)
            
            # 使用 followup 更新訊息
            try:
                await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)
            except:
                # 如果 followup 失敗，嘗試發送新訊息
                await interaction.followup.send(embed=embed, view=self)
        else:
            await interaction.response.send_message("✅ 當前已是時間排序模式", ephemeral=True)
    
    @discord.ui.button(label="讚數排序", style=discord.ButtonStyle.success, emoji="👍")
    async def sort_by_reactions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.sort_mode != "reactions":
            # 先回應交互，避免超時
            await interaction.response.defer()
            
            self.sort_mode = "reactions"
            self.current_page = 1  # 重置到第一頁
            embed = await self.get_messages_embed(interaction)
            
            # 使用 followup 更新訊息
            try:
                await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)
            except:
                # 如果 followup 失敗，嘗試發送新訊息
                await interaction.followup.send(embed=embed, view=self)
        else:
            await interaction.response.send_message("✅ 當前已是讚數排序模式", ephemeral=True)
    
    async def get_message_reaction_count(self, thread_id: int, message_id: int) -> int:
        """獲取消息的最高表情符號數量（帶緩存）"""
        # 簡單的內存緩存，避免短時間內重複請求
        cache_key = f"{thread_id}_{message_id}"
        if hasattr(self, '_reaction_cache') and cache_key in self._reaction_cache:
            cache_time, count = self._reaction_cache[cache_key]
            # 使用配置的緩存時間
            if (datetime.now() - cache_time).total_seconds() < config.REACTION_CACHE_DURATION:
                return count
        
        try:
            # 獲取消息對象
            message = await self.bot.get_channel(thread_id).fetch_message(message_id)
            
            if not message or not message.reactions:
                return 0
            
            # 計算所有表情符號中的最高數量
            max_count = 0
            for reaction in message.reactions:
                if reaction.count > max_count:
                    max_count = reaction.count
            
            # 緩存結果
            if not hasattr(self, '_reaction_cache'):
                self._reaction_cache = {}
            self._reaction_cache[cache_key] = (datetime.now(), max_count)
            
            return max_count
            
        except Exception as e:
            # 如果無法獲取消息或表情符號，返回 0
            logger.debug(f"無法獲取消息 {message_id} 的表情符號: {e}")
            return 0
    
    async def get_thread_title(self, thread_id: int) -> str:
        """獲取帖子標題"""
        try:
            # 嘗試獲取頻道
            channel = self.bot.get_channel(thread_id)
            if not channel or not hasattr(channel, 'name'):
                return None
            
            # 返回帖子標題
            return channel.name
            
        except Exception:
            # 如果無法獲取帖子標題，返回 None
            return None

