import discord
from discord.ext import commands
from discord import app_commands
import config
from database import DatabaseManager
import logging
import asyncio
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()  # 同时输出到控制台
    ]
)
logger = logging.getLogger('discord')

class FeaturedMessageBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True  # 需要members权限来管理角色
        
        super().__init__(
            command_prefix=config.BOT_PREFIX,
            intents=intents,
            help_command=None
        )
        
        self.db = DatabaseManager(config.DATABASE_FILE)
        
    async def setup_hook(self):
        """机器人启动时的设置"""
        await self.add_cog(FeaturedCommands(self))
        await self.tree.sync()
        logger.info('🤖 机器人设置完成，正在连接...')
    
    async def on_ready(self):
        """机器人准备就绪时的回调"""
        logger.info('=' * 50)
        logger.info(f'🤖 机器人已成功启动！')
        logger.info(f'📝 机器人名称: {self.user.name}')
        logger.info(f'🆔 机器人ID: {self.user.id}')
        logger.info(f'📅 启动时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        logger.info(f'🌐 连接状态: 已连接到 {len(self.guilds)} 个服务器')
        logger.info('=' * 50)
        logger.info('✅ 机器人已准备就绪，可以开始使用！')
        logger.info('📋 可用命令: /精选, /积分, /帖子统计, /总排行, /鉴赏申请窗口')
        logger.info('=' * 50)

class FeaturedRecordsView(discord.ui.View):
    """精選記錄分頁視圖"""
    def __init__(self, bot: FeaturedMessageBot, user_id: int, guild_id: int, current_page: int = 1):
        super().__init__(timeout=300)  # 5分鐘超時
        self.bot = bot
        self.user_id = user_id
        self.guild_id = guild_id
        self.current_page = current_page
        self.per_page = 5
    
    async def get_records_embed(self) -> discord.Embed:
        """獲取當前頁面的精選記錄嵌入訊息"""
        # 獲取精選記錄數據
        records, total_pages = self.bot.db.get_user_featured_records(
            self.user_id, self.guild_id, self.current_page, self.per_page
        )
        
        # 獲取用戶資訊
        user = self.bot.get_user(self.user_id)
        username = user.display_name if user else f"用戶 {self.user_id}"
        
        if not records:
            embed = discord.Embed(
                        title=f"🏆 {username} 的精选记录",
        description="还没有精选记录",
                color=0x00ff00,
                timestamp=discord.utils.utcnow()
            )
            return embed
        
        embed = discord.Embed(
            title=f"🏆 {username} 的精选记录",
            description=f"第 {self.current_page} 頁，共 {total_pages} 頁",
            color=0x00ff00,
            timestamp=discord.utils.utcnow()
        )
        
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
            description = f"📝 **精选原因**: {record['reason'] or '无'}\n"
            description += f"👤 **精选者**: {record['featured_by_name']}\n"
            description += f"📅 **精选时间**: {formatted_time}\n"
            
            # 使用帖子超連結
            if thread_title:
                description += f"🏷️ **原帖**: [{thread_title}]({thread_link})"
            else:
                description += f"🏷️ **原帖**: [點擊查看]({thread_link})"
            
            embed.add_field(
                name=f"{i}. 精选记录",
                value=description,
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
        _, total_pages = self.bot.db.get_user_featured_records(
            self.user_id, self.guild_id, self.current_page, self.per_page
        )
        
        if self.current_page < total_pages:
            self.current_page += 1
            embed = await self.get_records_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="最後一頁", style=discord.ButtonStyle.gray, emoji="⏭️")
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        _, total_pages = self.bot.db.get_user_featured_records(
            self.user_id, self.guild_id, self.current_page, self.per_page
        )
        
        self.current_page = total_pages
        embed = await self.get_records_embed()
        await interaction.response.edit_message(embed=embed, view=self)

class EnhancedRankingView(discord.ui.View):
    """增强排行榜视图 - 支持积分排行和引荐人数排行切换，支持时间范围"""
    def __init__(self, bot: FeaturedMessageBot, guild_id: int, current_page: int = 1, ranking_type: str = "points", start_date: str = None, end_date: str = None):
        super().__init__(timeout=300)  # 5分鐘超時
        self.bot = bot
        self.guild_id = guild_id
        self.current_page = current_page
        self.per_page = 20
        self.ranking_type = ranking_type  # "points" 或 "referral"
        self.start_date = start_date
        self.end_date = end_date
    
    async def get_ranking_embed(self) -> discord.Embed:
        """獲取當前頁面的排行榜嵌入訊息"""
        if self.ranking_type == "points":
            # 獲取積分排行榜數據
            ranking_data, total_pages = self.bot.db.get_total_ranking(self.guild_id, self.current_page, self.per_page, self.start_date, self.end_date)
            title = "🏆 總積分排行榜"
            
            # 根据时间范围调整描述
            if self.start_date and self.end_date:
                description = f"時間範圍: {self.start_date} 至 {self.end_date} • 第 {self.current_page} 頁，共 {total_pages} 頁"
            elif self.start_date:
                description = f"時間範圍: {self.start_date} 至今 • 第 {self.current_page} 頁，共 {total_pages} 頁"
            elif self.end_date:
                description = f"時間範圍: 開始至 {self.end_date} • 第 {self.current_page} 頁，共 {total_pages} 頁"
            else:
                description = f"所有時間的積分統計 • 第 {self.current_page} 頁，共 {total_pages} 頁"
            
            empty_description = "還沒有積分記錄"
        else:
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
            
            if self.ranking_type == "points":
                value = f"積分: {rank_info['points']} 分"
            else:
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
        if self.ranking_type == "points":
            _, total_pages = self.bot.db.get_total_ranking(self.guild_id, self.current_page, self.per_page, self.start_date, self.end_date)
        else:
            _, total_pages = self.bot.db.get_referral_ranking(self.guild_id, self.current_page, self.per_page, self.start_date, self.end_date)
        
        if self.current_page < total_pages:
            self.current_page += 1
            embed = await self.get_ranking_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="最後一頁", style=discord.ButtonStyle.gray, emoji="⏭️")
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ranking_type == "points":
            _, total_pages = self.bot.db.get_total_ranking(self.guild_id, self.current_page, self.per_page, self.start_date, self.end_date)
        else:
            _, total_pages = self.bot.db.get_referral_ranking(self.guild_id, self.current_page, self.per_page, self.start_date, self.end_date)
        
        self.current_page = total_pages
        embed = await self.get_ranking_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="積分排行", style=discord.ButtonStyle.success, emoji="🏆")
    async def switch_to_points(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ranking_type != "points":
            self.ranking_type = "points"
            self.current_page = 1  # 重置到第一頁
            embed = await self.get_ranking_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("✅ 當前已是積分排行模式", ephemeral=True)
    
    @discord.ui.button(label="引薦排行", style=discord.ButtonStyle.secondary, emoji="👥")
    async def switch_to_referral(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ranking_type != "referral":
            self.ranking_type = "referral"
            self.current_page = 1  # 重置到第一頁
            embed = await self.get_ranking_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("✅ 當前已是引薦排行模式", ephemeral=True)

class TotalRankingView(discord.ui.View):
    """總排行榜分頁視圖"""
    def __init__(self, bot: FeaturedMessageBot, guild_id: int, current_page: int = 1):
        super().__init__(timeout=300)  # 5分鐘超時
        self.bot = bot
        self.guild_id = guild_id
        self.current_page = current_page
        self.per_page = 20
    
    async def get_ranking_embed(self) -> discord.Embed:
        """獲取當前頁面的排行榜嵌入訊息"""
        # 獲取排行榜數據
        ranking_data, total_pages = self.bot.db.get_total_ranking(self.guild_id, self.current_page, self.per_page)
        
        if not ranking_data:
            embed = discord.Embed(
                title="🏆 總積分排行榜",
                description="還沒有積分記錄",
                color=0x00ff00,
                timestamp=discord.utils.utcnow()
            )
            return embed
        
        # 計算當前頁的起始排名
        start_rank = (self.current_page - 1) * self.per_page + 1
        
        embed = discord.Embed(
            title="🏆 總積分排行榜",
            description=f"所有時間的積分統計 • 第 {self.current_page} 頁，共 {total_pages} 頁",
            color=0x00ff00,
            timestamp=discord.utils.utcnow()
        )
        
        for i, rank_info in enumerate(ranking_data):
            # 獲取用戶資訊
            user = self.bot.get_user(rank_info['user_id'])
            username = user.display_name if user else rank_info['username']
            
            # 計算實際排名
            actual_rank = start_rank + i
            
            embed.add_field(
                name=f"{actual_rank}. {username}",
                value=f"積分: {rank_info['points']} 分",
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
        _, total_pages = self.bot.db.get_total_ranking(self.guild_id, self.current_page, self.per_page)
        
        if self.current_page < total_pages:
            self.current_page += 1
            embed = await self.get_ranking_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="最後一頁", style=discord.ButtonStyle.gray, emoji="⏭️")
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        _, total_pages = self.bot.db.get_total_ranking(self.guild_id, self.current_page, self.per_page)
        
        self.current_page = total_pages
        embed = await self.get_ranking_embed()
        await interaction.response.edit_message(embed=embed, view=self)



class ThreadStatsView(discord.ui.View):
    """帖子統計分頁視圖"""
    def __init__(self, bot: FeaturedMessageBot, thread_id: int, guild_id: int, current_page: int = 1, sort_mode: str = "time"):
        super().__init__(timeout=300)  # 5分鐘超時
        self.bot = bot
        self.thread_id = thread_id
        self.guild_id = guild_id
        self.current_page = current_page
        self.per_page = 5
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
    
    @discord.ui.button(label="讚數排序", style=discord.ButtonStyle.secondary, emoji="👍")
    async def sort_by_reactions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.sort_mode != "reactions":
            self.sort_mode = "reactions"
            self.current_page = 1  # 重置到第一頁
            embed = await self.get_stats_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("✅ 當前已是讚數排序模式", ephemeral=True)
    
    async def get_records_embed(self) -> discord.Embed:
        """獲取當前頁面的記錄嵌入訊息"""
        records, total_pages = self.bot.db.get_user_featured_records(
            self.user_id, self.guild_id, self.current_page, self.per_page
        )
        
        # 獲取用戶資訊
        user = self.bot.get_user(self.user_id)
        if user:
            username = user.display_name
        else:
            # 如果用戶不在快取中，嘗試從資料庫獲取用戶名
            try:
                stats = self.bot.db.get_user_stats(self.user_id, self.guild_id)
                username = stats['username'] if stats['username'] else f"用戶{self.user_id}"
            except:
                username = f"用戶{self.user_id}"
        
        embed = discord.Embed(
            title=f"📊 {username} 的精选记录",
            description=f"第 {self.current_page} 頁，共 {total_pages} 頁",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        if not records:
            embed.add_field(
                name="📝 記錄",
                value="還沒有被精選的記錄",
                inline=False
            )
        else:
            for i, record in enumerate(records, 1):
                # 格式化時間
                try:
                    featured_time = datetime.fromisoformat(record['featured_at'].replace('Z', '+00:00'))
                    formatted_time = featured_time.strftime("%Y-%m-%d %H:%M")
                except:
                    formatted_time = record['featured_at']
                
                # 創建連結
                thread_link = f"https://discord.com/channels/{self.guild_id}/{record['thread_id']}"
                message_link = f"https://discord.com/channels/{self.guild_id}/{record['thread_id']}/{record['message_id']}"
                
                # 嘗試獲取帖子標題
                try:
                    thread_title = await self.get_thread_title(record['thread_id'])
                except Exception:
                    thread_title = None
                
                # 構建記錄內容
                if thread_title:
                    record_content = f"**原帖**: [{thread_title}]({thread_link})\n"
                else:
                    record_content = f"**原帖**: [點擊查看]({thread_link})\n"
                
                record_content += f"**精选留言**: [点击查看]({message_link})\n"
                record_content += f"**精选者**: {record['featured_by_name']}\n"
                record_content += f"**時間**: {formatted_time}"
                
                # 如果有精选原因，添加到内容中
                if record['reason']:
                    record_content += f"\n**精选原因**: {record['reason']}"
                
                embed.add_field(
                    name=f"{i}. 精选记录",
                    value=record_content,
                    inline=False
                )
        
        # 更新按鈕狀態
        self.update_buttons(total_pages)
        
        return embed
    
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
        records, total_pages = self.bot.db.get_user_featured_records(
            self.user_id, self.guild_id, self.current_page, self.per_page
        )
        
        if self.current_page < total_pages:
            self.current_page += 1
            embed = await self.get_records_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="最後一頁", style=discord.ButtonStyle.gray, emoji="⏭️")
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        records, total_pages = self.bot.db.get_user_featured_records(
            self.user_id, self.guild_id, self.current_page, self.per_page
        )
        
        self.current_page = total_pages
        embed = await self.get_records_embed()
        await interaction.response.edit_message(embed=embed, view=self)

class AppreciatorApplicationView(discord.ui.View):
    """鉴赏申请窗口视图"""
    def __init__(self, bot: FeaturedMessageBot):
        super().__init__(timeout=None)  # 永久有效
        self.bot = bot
    
    @discord.ui.button(label="申请鉴赏家身份", style=discord.ButtonStyle.success, emoji="📜")
    async def apply_appreciator(self, interaction: discord.Interaction, button: discord.ui.Button):
        """申请鉴赏家身份"""
        try:
            # 获取用户统计信息
            stats = self.bot.db.get_user_stats(interaction.user.id, interaction.guild_id)
            
            # 检查积分或引荐人数要求（满足其中一个即可）
            points_ok = stats['points'] >= config.APPRECIATOR_MIN_POINTS
            referrals_ok = stats['featuring_count'] >= config.APPRECIATOR_MIN_REFERRALS
            
            if not points_ok and not referrals_ok:
                await interaction.response.send_message(
                    f"❌ 申请条件不满足！\n"
                    f"需要满足以下条件之一：\n"
                    f"• 积分至少 {config.APPRECIATOR_MIN_POINTS} 分（您当前有 {stats['points']} 分）\n"
                    f"• 引荐人数至少 {config.APPRECIATOR_MIN_REFERRALS} 人（您当前引荐了 {stats['featuring_count']} 人）",
                    ephemeral=True
                )
                return
            
            # 检查是否已经有鉴赏家身份
            member = interaction.guild.get_member(interaction.user.id)
            if member:
                for role in member.roles:
                    if role.name == config.APPRECIATOR_ROLE_NAME:
                        await interaction.response.send_message(
                            f"❌ 您已经拥有 {config.APPRECIATOR_ROLE_NAME} 身份了！",
                            ephemeral=True
                        )
                        return
            
            # 查找或创建鉴赏家角色
            appreciator_role = None
            for role in interaction.guild.roles:
                if role.name == config.APPRECIATOR_ROLE_NAME:
                    appreciator_role = role
                    break
            
            if not appreciator_role:
                # 创建鉴赏家角色
                try:
                    appreciator_role = await interaction.guild.create_role(
                        name=config.APPRECIATOR_ROLE_NAME,
                        color=discord.Color.gold(),
                        reason=f"{config.APPRECIATOR_ROLE_NAME}身份组"
                    )
                    logger.info(f"✅ 在群组 {interaction.guild.name} 创建了 {config.APPRECIATOR_ROLE_NAME} 角色")
                except discord.Forbidden:
                    embed = discord.Embed(
                        title="❌ 权限不足",
                        description="机器人无法创建鉴赏家角色",
                        color=0xff0000,
                        timestamp=discord.utils.utcnow()
                    )
                    embed.add_field(
                        name="🔧 解决方案",
                        value="请群组管理员：\n"
                              "1. 手动创建 `鉴赏家` 角色\n"
                              "2. 确保机器人有 `管理角色` 权限\n"
                              "3. 确保机器人角色在鉴赏家角色之上",
                        inline=False
                    )
                    embed.add_field(
                        name="📋 所需权限",
                        value="• 管理角色\n• 管理成员",
                        inline=False
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
            
            # 分配角色
            try:
                await member.add_roles(appreciator_role, reason=f"用户申请{config.APPRECIATOR_ROLE_NAME}身份")
                
                # 记录申请成功
                logger.info(f"📜 用户 {interaction.user.name} (ID: {interaction.user.id}) 在群组 {interaction.guild.name} 成功申请获得 {config.APPRECIATOR_ROLE_NAME} 身份")
                
                # 发送成功消息
                embed = discord.Embed(
                    title=f"📜 {config.APPRECIATOR_ROLE_NAME}申请成功！",
                    description=f"恭喜您成功获得 **{config.APPRECIATOR_ROLE_NAME}** 身份！",
                    color=0x00ff00,
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(
                    name="📊 您的成就",
                    value=f"**总积分**: {stats['points']} 分\n**引荐人数**: {stats['featuring_count']} 人",
                    inline=False
                )
                # 显示用户满足的条件
                conditions_met = []
                if points_ok:
                    conditions_met.append(f"✅ 积分 {stats['points']} 分（满足 {config.APPRECIATOR_MIN_POINTS} 分要求）")
                if referrals_ok:
                    conditions_met.append(f"✅ 引荐 {stats['featuring_count']} 人（满足 {config.APPRECIATOR_MIN_REFERRALS} 人要求）")
                
                embed.add_field(
                    name="🎯 申请条件",
                    value=f"**满足条件**：\n" + "\n".join(conditions_met) + f"\n\n**完整要求**：\n• 积分至少 {config.APPRECIATOR_MIN_POINTS} 分\n• 引荐人数至少 {config.APPRECIATOR_MIN_REFERRALS} 人",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
            except discord.Forbidden:
                embed = discord.Embed(
                    title="❌ 权限不足",
                    description="机器人无法分配鉴赏家角色",
                    color=0xff0000,
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(
                    name="🔧 解决方案",
                    value="请群组管理员：\n"
                          "1. 确保机器人有 `管理角色` 权限\n"
                          "2. 确保机器人角色在鉴赏家角色之上\n"
                          "3. 检查鉴赏家角色是否存在",
                    inline=False
                )
                embed.add_field(
                    name="📋 所需权限",
                    value="• 管理角色\n• 管理成员",
                    inline=False
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
                
        except Exception as e:
            logger.error(f"申请{config.APPRECIATOR_ROLE_NAME}身份时发生错误: {e}")
            await interaction.response.send_message(
                "❌ 申请过程中发生错误，请稍后重试。",
                ephemeral=True
            )

class FeaturedCommands(commands.Cog):
    def __init__(self, bot: FeaturedMessageBot):
        self.bot = bot
        self.db = bot.db
    
    def extract_message_id_from_url(self, url: str) -> int:
        """从Discord消息URL中提取消息ID"""
        import re
        # Discord消息URL格式: https://discord.com/channels/guild_id/channel_id/message_id
        pattern = r'https://discord\.com/channels/\d+/\d+/(\d+)'
        match = re.search(pattern, url)
        if match:
            return int(match.group(1))
        else:
            raise ValueError("无效的Discord消息URL格式")
    
    def check_message_quality(self, message) -> dict:
        """检查留言内容质量"""
        # 检查是否为bot消息或包含embed
        if message.author.bot or message.embeds:
            return {'valid': False, 'reason': '不能精选bot消息或系统消息！'}
        
        # 获取文字内容
        content = message.content.strip()
        
        # 检查是否为空
        if not content:
            return {'valid': False, 'reason': '留言内容不能为空！'}
        
        # 检查长度（最少10个字符）
        if len(content) < 10:
            return {'valid': False, 'reason': '留言内容至少需要10个字符！'}
        
        # 检查是否有贴纸
        if message.stickers:
            return {'valid': False, 'reason': '不能精选只包含贴纸的留言！'}
        
        # 检查是否只包含表情符号
        # 移除所有表情符号和空白字符
        text_only = content
        # 移除Discord表情符号格式 <:name:id>
        import re
        text_only = re.sub(r'<a?:[^:]+:\d+>', '', text_only)
        # 移除Unicode表情符号
        text_only = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002600-\U000027BF\U0001F900-\U0001F9FF]', '', text_only)
        # 移除空白字符
        text_only = text_only.strip()
        
        if not text_only:
            return {'valid': False, 'reason': '留言不能只包含表情符号！'}
        
        # 检查是否只包含重复字符
        if len(set(text_only)) <= 2 and len(text_only) > 5:
            return {'valid': False, 'reason': '留言内容过于简单，请提供更有价值的回复！'}
        
        # 检查是否包含常见垃圾内容
        spam_patterns = [
            r'^[^\w\s]*$',  # 只包含特殊字符
            r'^[a-zA-Z]{1,3}$',  # 只有1-3个字母
            r'^[0-9]{1,3}$',  # 只有1-3个数字
            r'^[^\w\s]{3,}$',  # 3个以上特殊字符
        ]
        
        for pattern in spam_patterns:
            if re.match(pattern, content):
                return {'valid': False, 'reason': '留言内容不符合精选标准！'}
        
        return {'valid': True, 'reason': '内容检查通过'}
    
    @app_commands.command(name="精选", description="将指定用户的留言设为精选，该用户获得1积分（留言需至少10字符且不能只含表情）")
    @app_commands.describe(
        message_url="要精选的留言URL（右键留言 -> 复制链接）",
        reason="精选原因（可选）"
    )
    async def feature_message(self, interaction: discord.Interaction, message_url: str, reason: str = None):
        """精選留言命令"""
        # 记录命令使用
        logger.info(f"🔍 用户 {interaction.user.name} (ID: {interaction.user.id}) 在群组 {interaction.guild.name} (ID: {interaction.guild.id}) 使用了 /精选 命令，留言URL: {message_url}")
        
        try:
            # 检查是否在帖子中
            if not interaction.channel.type == discord.ChannelType.public_thread:
                await interaction.response.send_message("❌ 此命令只能在帖子中使用！", ephemeral=True)
                return
            
            thread_id = interaction.channel.id
            thread_owner_id = interaction.channel.owner_id
            
            # 检查是否为楼主
            if interaction.user.id != thread_owner_id:
                await interaction.response.send_message("❌ 只有楼主才能精选留言！", ephemeral=True)
                return
            
            # 从URL中提取消息ID
            try:
                message_id = self.extract_message_id_from_url(message_url)
            except ValueError:
                await interaction.response.send_message("❌ 无效的留言URL格式！请右键留言选择'复制链接'获取正确的URL。", ephemeral=True)
                return
            
            # 获取要精選的留言
            try:
                message = await interaction.channel.fetch_message(message_id)
            except discord.NotFound:
                await interaction.response.send_message("❌ 找不到指定的留言！请检查留言URL是否正确，或确认留言在当前帖子中。", ephemeral=True)
                return
            
            # 检查是否精選自己的留言
            if message.author.id == interaction.user.id:
                await interaction.response.send_message("❌ 不能精选自己的留言！", ephemeral=True)
                return
            
            # 检查留言内容质量
            content_check = self.check_message_quality(message)
            if not content_check['valid']:
                await interaction.response.send_message(f"❌ {content_check['reason']}", ephemeral=True)
                return
            
            # 检查是否已经精選过该用户
            if self.db.is_already_featured(thread_id, message.author.id):
                await interaction.response.send_message(
                    f"❌ 您已经精选过 {message.author.display_name} 的留言了！每个帖子中只能精选每位用户一次。", 
                    ephemeral=True
                )
                return
            
            # 创建精选通知
            embed = discord.Embed(
                title="🌟 留言精选",
                description=f"{message.author.display_name} 的留言被设为精选！",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="精选的留言",
                value=f"[点击查看]({message.jump_url})",
                inline=False
            )
            
            embed.add_field(
                name="精选者",
                value=interaction.user.display_name,
                inline=True
            )
            
            if reason:
                embed.add_field(
                    name="精选原因",
                    value=reason,
                    inline=False
                )
            
            embed.set_footer(text=f"留言ID: {message.id}")
            
            # 在訊息內容中 @ 留言者，這樣會真正觸發 Discord 的 @ 通知
            await interaction.response.send_message(content=f"{message.author.mention}", embed=embed)
            
            # 等待一下让消息发送完成，然后获取机器人发送的消息ID
            await asyncio.sleep(0.5)
            
            # 获取机器人发送的最新消息ID
            bot_message_id = None
            try:
                # 获取频道的最新消息
                async for bot_msg in interaction.channel.history(limit=10):
                    if bot_msg.author.id == self.bot.user.id and bot_msg.embeds:
                        # 检查是否是精选消息（通过检查embed标题）
                        if bot_msg.embeds[0].title == "🌟 留言精选":
                            bot_message_id = bot_msg.id
                            break
            except Exception as e:
                logger.warning(f"⚠️ 无法获取机器人消息ID: {e}")
            
            # 添加精选记录（包含机器人消息ID）
            success = self.db.add_featured_message(
                guild_id=interaction.guild_id,
                thread_id=thread_id,
                message_id=message.id,
                author_id=message.author.id,
                author_name=message.author.display_name,
                featured_by_id=interaction.user.id,
                featured_by_name=interaction.user.display_name,
                reason=reason,
                bot_message_id=bot_message_id
            )
            
            if not success:
                await interaction.response.send_message("❌ 精选失败，该用户可能已经被精选过了。", ephemeral=True)
                return
            
            # 给用户添加积分（總積分）
            logger.info(f"🎯 给用户 {message.author.display_name} (ID: {message.author.id}) 添加 {config.POINTS_PER_FEATURE} 积分")
            new_points = self.db.add_user_points(
                user_id=message.author.id,
                username=message.author.display_name,
                points=config.POINTS_PER_FEATURE,
                guild_id=interaction.guild_id
            )
            
            # 给用户添加月度积分
            new_monthly_points = self.db.add_monthly_points(
                user_id=message.author.id,
                username=message.author.display_name,
                points=config.POINTS_PER_FEATURE,
                guild_id=interaction.guild_id
            )
            
            logger.info(f"✅ 用户 {message.author.display_name} 积分更新完成 - 總積分: {new_points}, 月度積分: {new_monthly_points}")
            
        except Exception as e:
            logger.error(f"精选留言时发生错误: {e}")
            # 檢查是否已經回應過或 interaction 是否有效
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 精选留言时发生错误，请稍后重试。", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 精选留言时发生错误，请稍后重试。", ephemeral=True)
            except Exception as followup_error:
                logger.error(f"发送错误消息时发生错误: {followup_error}")
                # 如果連 followup 都失敗，就記錄錯誤但不拋出異常
    
    @app_commands.command(name="精选取消", description="取消指定留言的精选状态（仅楼主可用）")
    @app_commands.describe(
        message_url="要取消精选的留言URL（右键留言 -> 复制链接）"
    )
    async def unfeature_message(self, interaction: discord.Interaction, message_url: str):
        """取消精選留言命令"""
        # 记录命令使用
        logger.info(f"🔍 用户 {interaction.user.name} (ID: {interaction.user.id}) 在群组 {interaction.guild.name} (ID: {interaction.guild.id}) 使用了 /精选取消 命令，留言URL: {message_url}")
        
        try:
            # 检查是否在帖子中
            if not interaction.channel.type == discord.ChannelType.public_thread:
                await interaction.response.send_message("❌ 此命令只能在帖子中使用！", ephemeral=True)
                return
            
            thread_id = interaction.channel.id
            thread_owner_id = interaction.channel.owner_id
            
            # 检查是否为楼主
            if interaction.user.id != thread_owner_id:
                await interaction.response.send_message("❌ 只有楼主才能取消精选留言！", ephemeral=True)
                return
            
            # 从URL中提取消息ID
            try:
                message_id_int = self.extract_message_id_from_url(message_url)
            except ValueError:
                await interaction.response.send_message("❌ 无效的留言URL格式！请右键留言选择'复制链接'获取正确的URL。", ephemeral=True)
                return
            
            # 检查精選记录是否存在
            featured_info = self.db.get_featured_message_by_id(message_id_int, thread_id)
            if not featured_info:
                await interaction.response.send_message("❌ 找不到该留言的精选记录！请检查留言ID是否正确。", ephemeral=True)
                return
            
            # 尝试删除机器人的精选消息
            bot_message_deleted = False
            if featured_info.get('bot_message_id'):
                try:
                    bot_message = await interaction.channel.fetch_message(featured_info['bot_message_id'])
                    await bot_message.delete()
                    bot_message_deleted = True
                    logger.info(f"🗑️ 已删除机器人精选消息 ID: {featured_info['bot_message_id']}")
                except discord.NotFound:
                    logger.warning(f"⚠️ 找不到机器人精选消息 ID: {featured_info['bot_message_id']}")
                except discord.Forbidden:
                    logger.warning(f"⚠️ 没有权限删除机器人精选消息 ID: {featured_info['bot_message_id']}")
                except Exception as e:
                    logger.error(f"❌ 删除机器人精选消息时发生错误: {e}")
            
            # 移除精选记录
            success = self.db.remove_featured_message(message_id_int, thread_id)
            if not success:
                await interaction.response.send_message("❌ 取消精选失败，请稍后重试。", ephemeral=True)
                return
            
            # 创建成功消息
            embed = discord.Embed(
                title="✅ 精选已取消",
                description=f"已成功取消 {featured_info['author_name']} 留言的精选状态",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="被取消精选的用户",
                value=featured_info['author_name'],
                inline=True
            )
            
            embed.add_field(
                name="取消者",
                value=interaction.user.display_name,
                inline=True
            )
            
            embed.add_field(
                name="積分變更",
                value=f"{featured_info['author_name']} 的積分已減少 1 分",
                inline=False
            )
            
            if bot_message_deleted:
                embed.add_field(
                    name="🗑️ 消息清理",
                    value="已自动删除精选通知消息",
                    inline=False
                )
            
            embed.set_footer(text=f"留言ID: {message_id}")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"取消精选留言时发生错误: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 取消精选留言时发生错误，请稍后重试。", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 取消精选留言时发生错误，请稍后重试。", ephemeral=True)
            except Exception as followup_error:
                logger.error(f"发送错误消息时发生错误: {followup_error}")
                
    @app_commands.command(name="总排行", description="查看总积分排行榜和引荐人数排行榜（仅管理组可用，支持时间范围）")
    @app_commands.describe(
        start_date="起始日期（可选，格式：YYYY-MM-DD，例如：2024-01-01）",
        end_date="结束日期（可选，格式：YYYY-MM-DD，例如：2024-12-31）"
    )
    async def total_ranking(self, interaction: discord.Interaction, start_date: str = None, end_date: str = None):
        """查看總排行榜命令（僅管理組可用）- 支持積分排行和引薦人數排行切換，支持時間範圍"""
        # 记录命令使用
        logger.info(f"🔍 用户 {interaction.user.name} (ID: {interaction.user.id}) 在群组 {interaction.guild.name} (ID: {interaction.guild.id}) 查看了總排行榜，时间范围: {start_date} 至 {end_date}")
        
        try:
            # 檢查是否為管理組（檢查特定角色或權限）
            has_admin_role = False
            
            # 方法1: 檢查是否有管理組角色（從配置文件讀取）
            for role in interaction.user.roles:
                if role.name in config.ADMIN_ROLE_NAMES:
                    has_admin_role = True
                    logger.info(f"✅ 用户 {interaction.user.name} 通过角色 '{role.name}' 获得管理权限")
                    break
            
            # 方法2: 如果沒有特定角色，檢查是否有管理權限
            if not has_admin_role:
                has_admin_role = interaction.user.guild_permissions.manage_messages or \
                                interaction.user.guild_permissions.administrator
            
            if not has_admin_role:
                await interaction.response.send_message("❌ 此命令僅限管理組使用！", ephemeral=True)
                return
            
            # 验证日期格式
            if start_date:
                try:
                    datetime.strptime(start_date, '%Y-%m-%d')
                except ValueError:
                    await interaction.response.send_message("❌ 起始日期格式錯誤！請使用 YYYY-MM-DD 格式，例如：2024-01-01", ephemeral=True)
                    return
            
            if end_date:
                try:
                    datetime.strptime(end_date, '%Y-%m-%d')
                except ValueError:
                    await interaction.response.send_message("❌ 結束日期格式錯誤！請使用 YYYY-MM-DD 格式，例如：2024-12-31", ephemeral=True)
                    return
            
            # 創建增強排行榜視圖（預設為積分排行）
            view = EnhancedRankingView(self.bot, interaction.guild_id, 1, "points", start_date, end_date)
            
            # 獲取嵌入訊息
            embed = await view.get_ranking_embed()
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看總排行榜时发生错误: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 查看總排行榜时发生错误，请稍后重试。", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 查看總排行榜时发生错误，请稍后重试。", ephemeral=True)
            except Exception as followup_error:
                logger.error(f"发送错误消息时发生错误: {followup_error}")
    
    @app_commands.command(name="积分", description="查看用户积分和精选记录（如果没有指定用户，默认查看自己）")
    async def check_points(self, interaction: discord.Interaction, user: discord.Member = None):
        """查看积分命令（支持查看其他用户）"""
        # 记录命令使用
        target_user = user.name if user else interaction.user.name
        logger.info(f"🔍 用户 {interaction.user.name} (ID: {interaction.user.id}) 在群组 {interaction.guild.name} (ID: {interaction.guild.id}) 查看了用户 {target_user} 的积分")
        
        try:
            # 如果沒有指定用戶，默認查看自己
            if user is None:
                user = interaction.user
            
            user_id = user.id
            stats = self.db.get_user_stats(user_id, interaction.guild_id)
            
            # 創建分頁視圖
            view = FeaturedRecordsView(self.bot, user_id, interaction.guild_id, 1)
            
            # 先準備好嵌入訊息，避免在發送回應後再調用異步方法
            embed = await view.get_records_embed()
            
            # 獲取月度積分
            monthly_points = self.db.get_user_monthly_points(user_id, interaction.guild_id)
            
            # 添加積分統計到嵌入訊息
            embed.add_field(
                name="📈 積分統計",
                value=f"**總積分**: {stats['points']} 積分\n"
                      # f"**本月積分**: {monthly_points} 積分\n"
                      f"**被精选次数**: {stats['featured_count']} 次\n"
                      f"**引荐人数**: {stats['featuring_count']} 人",
                inline=False
            )
            
            embed.set_thumbnail(url=user.display_avatar.url)
            
            # 所有積分查看都使用 ephemeral=True，避免聊天頻道被塞爆
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看积分时发生错误: {e}")
            # 檢查是否已經回應過
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ 查看积分时发生错误，请稍后重试。", ephemeral=True)
            else:
                # 如果已經回應過，使用 followup
                await interaction.followup.send("❌ 查看积分时发生错误，请稍后重试。", ephemeral=True)
    
    @app_commands.command(name="帖子统计", description="查看当前帖子的精选统计（仅自己可见）")
    async def thread_stats(self, interaction: discord.Interaction):
        """查看帖子统计命令（隱藏回應）"""
        # 记录命令使用
        logger.info(f"🔍 用户 {interaction.user.name} (ID: {interaction.user.id}) 在群组 {interaction.guild.name} (ID: {interaction.guild.id}) 查看了帖子统计")
        
        try:
            # 检查是否在帖子中
            if not interaction.channel.type == discord.ChannelType.public_thread:
                await interaction.response.send_message("❌ 此命令只能在帖子中使用！", ephemeral=True)
                return
            
            thread_id = interaction.channel.id
            
            # 創建分頁視圖（默認時間排序）
            view = ThreadStatsView(self.bot, thread_id, interaction.guild_id, 1, "time")
            
            # 獲取嵌入訊息
            embed = await view.get_stats_embed()
            
            # 使用 ephemeral=True 讓回應只有使用者自己可見
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看帖子统计时发生错误: {e}")
            # 檢查是否已經回應過
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 查看帖子统计时发生错误，请稍后重试。", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 查看帖子统计时发生错误，请稍后重试。", ephemeral=True)
            except Exception as followup_error:
                logger.error(f"发送错误消息时发生错误: {followup_error}")
                # 如果連 followup 都失敗，就記錄錯誤但不拋出異常
    


    @app_commands.command(name="鉴赏申请窗口", description="创建鉴赏家申请窗口（仅管理组可用）")
    async def create_appreciator_window(self, interaction: discord.Interaction):
        """创建鉴赏申请窗口命令（仅管理组可用）"""
        # 记录命令使用
        logger.info(f"🔍 用户 {interaction.user.name} (ID: {interaction.user.id}) 在群组 {interaction.guild.name} (ID: {interaction.guild.id}) 创建了鉴赏申请窗口")
        
        try:
            # 检查是否为管理组（检查特定角色或权限）
            has_admin_role = False
            for role in interaction.user.roles:
                if role.name in config.ADMIN_ROLE_NAMES:
                    has_admin_role = True
                    logger.info(f"✅ 用户 {interaction.user.name} 通过角色 '{role.name}' 获得管理权限")
                    break
            if not has_admin_role:
                has_admin_role = interaction.user.guild_permissions.manage_messages or \
                                interaction.user.guild_permissions.administrator
            if not has_admin_role:
                await interaction.response.send_message("❌ 此命令仅限管理组使用！", ephemeral=True)
                return
            
            # 创建鉴赏申请窗口
            embed = discord.Embed(
                title=f"📜 {config.APPRECIATOR_ROLE_NAME}申请窗口",
                description=f"点击下方按钮申请{config.APPRECIATOR_ROLE_NAME}身份",
                color=0x00ff00,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(
                name="📋 申请条件",
                value=f"**满足以下条件之一即可**：\n"
                      f"• 积分至少 {config.APPRECIATOR_MIN_POINTS} 分\n"
                      f"• 引荐人数至少 {config.APPRECIATOR_MIN_REFERRALS} 人",
                inline=False
            )
            embed.add_field(
                name="🎯 获得身份",
                value=f"**身份组**: {config.APPRECIATOR_ROLE_NAME}",
                inline=False
            )
            embed.add_field(
                name="💡 说明",
                value="• 满足条件的用户可点击按钮自动获得身份\n• 已拥有该身份的用户无法重复申请\n• 机器人会自动检查您的积分和引荐人数\n• 如遇权限问题，请联系群组管理员",
                inline=False
            )
            embed.add_field(
                name="📖 快速使用指南",
                value="**如何参与精选系统？**\n"
                      "• `/精选` - 楼主可精选优质留言（右键留言→复制链接）\n"
                      "• `/积分` - 查看自己的积分和精选记录\n"
                      "• `/帖子统计` - 在帖子中查看精选统计\n\n"
                      "**精选要求**：留言至少10字符，支持附件+文字",
                inline=False
            )
            
            # 创建视图
            view = AppreciatorApplicationView(self.bot)
            
            # 发送窗口
            await interaction.response.send_message(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"创建鉴赏申请窗口时发生错误: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 创建鉴赏申请窗口时发生错误，请稍后重试。", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 创建鉴赏申请窗口时发生错误，请稍后重试。", ephemeral=True)
            except Exception as followup_error:
                logger.error(f"发送错误消息时发生错误: {followup_error}")

async def main():
    """主函数"""
    bot = FeaturedMessageBot()
    
    try:
        await bot.start(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("🛑 收到停止信號，正在關閉機器人...")
    except Exception as e:
        logger.error(f"❌ 機器人運行時發生錯誤: {e}")
    finally:
        await bot.close()

def start_bot():
    """啟動 Discord Bot"""
    import asyncio
    asyncio.run(main()) 

if __name__ == "__main__":
    start_bot() 