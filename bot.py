import discord
from discord.ext import commands
from discord import app_commands
import config
from database import DatabaseManager
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')

class FeaturedMessageBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        
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
        logger.info('📋 可用命令: /精選, /积分, /帖子统计, /排行榜, /帮助')
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

class ThreadStatsView(discord.ui.View):
    """帖子統計分頁視圖"""
    def __init__(self, bot: FeaturedMessageBot, thread_id: int, guild_id: int, current_page: int = 1):
        super().__init__(timeout=300)  # 5分鐘超時
        self.bot = bot
        self.thread_id = thread_id
        self.guild_id = guild_id
        self.current_page = current_page
        self.per_page = 5
    
    async def get_stats_embed(self) -> discord.Embed:
        """獲取當前頁面的統計嵌入訊息"""
        # 獲取所有統計數據
        all_stats = self.bot.db.get_thread_stats(self.thread_id)
        
        if not all_stats:
            embed = discord.Embed(
                title="📊 帖子精選統計",
                description="此帖子還沒有精選記錄",
                color=discord.Color.light_grey(),
                timestamp=discord.utils.utcnow()
            )
            return embed
        
        # 計算分頁
        total_records = len(all_stats)
        total_pages = (total_records + self.per_page - 1) // self.per_page
        start_idx = (self.current_page - 1) * self.per_page
        end_idx = min(start_idx + self.per_page, total_records)
        current_stats = all_stats[start_idx:end_idx]
        
        embed = discord.Embed(
            title="📊 帖子精選統計",
            description=f"共 {total_records} 條精選記錄 • 第 {self.current_page} 頁，共 {total_pages} 頁",
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
            
            # 構建記錄內容
            record_content = f"**精選留言**: [點擊查看]({message_link})\n"
            record_content += f"**時間**: {formatted_time}"
            
            # 如果有精選原因，添加到內容中
            if stat.get('reason'):
                record_content += f"\n**精選原因**: {stat['reason']}"
            
            embed.add_field(
                name=f"{i}. {stat['author_name']}",
                value=record_content,
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
            title=f"📊 {username} 的精選記錄",
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
                
                record_content += f"**精選留言**: [點擊查看]({message_link})\n"
                record_content += f"**精選者**: {record['featured_by_name']}\n"
                record_content += f"**時間**: {formatted_time}"
                
                # 如果有精選原因，添加到內容中
                if record['reason']:
                    record_content += f"\n**精選原因**: {record['reason']}"
                
                embed.add_field(
                    name=f"{i}. 精選記錄",
                    value=record_content,
                    inline=False
                )
        
        # 更新按鈕狀態
        self.update_buttons(total_pages)
        
        return embed
    
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
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有記錄擁有者才能操作分頁！", ephemeral=True)
            return
        
        self.current_page = 1
        embed = await self.get_records_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="上一頁", style=discord.ButtonStyle.primary, emoji="◀️")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有記錄擁有者才能操作分頁！", ephemeral=True)
            return
        
        if self.current_page > 1:
            self.current_page -= 1
            embed = await self.get_records_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="下一頁", style=discord.ButtonStyle.primary, emoji="▶️")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有記錄擁有者才能操作分頁！", ephemeral=True)
            return
        
        records, total_pages = self.bot.db.get_user_featured_records(
            self.user_id, self.guild_id, self.current_page, self.per_page
        )
        
        if self.current_page < total_pages:
            self.current_page += 1
            embed = await self.get_records_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="最後一頁", style=discord.ButtonStyle.gray, emoji="⏭️")
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有記錄擁有者才能操作分頁！", ephemeral=True)
            return
        
        records, total_pages = self.bot.db.get_user_featured_records(
            self.user_id, self.guild_id, self.current_page, self.per_page
        )
        
        self.current_page = total_pages
        embed = await self.get_records_embed()
        await interaction.response.edit_message(embed=embed, view=self)

class FeaturedCommands(commands.Cog):
    def __init__(self, bot: FeaturedMessageBot):
        self.bot = bot
        self.db = bot.db
    
    @app_commands.command(name="精選", description="将指定用户的留言设为精選，该用户获得1积分")
    @app_commands.describe(
        message_id="要精選的留言ID",
        reason="精選原因（可选）"
    )
    async def feature_message(self, interaction: discord.Interaction, message_id: str, reason: str = None):
        """精選留言命令"""
        try:
            # 检查是否在帖子中
            if not interaction.channel.type == discord.ChannelType.public_thread:
                await interaction.response.send_message("❌ 此命令只能在帖子中使用！", ephemeral=True)
                return
            
            thread_id = interaction.channel.id
            thread_owner_id = interaction.channel.owner_id
            
            # 检查是否为楼主
            if interaction.user.id != thread_owner_id:
                await interaction.response.send_message("❌ 只有楼主才能精選留言！", ephemeral=True)
                return
            
            # 获取要精選的留言
            try:
                message = await interaction.channel.fetch_message(int(message_id))
            except (ValueError, discord.NotFound):
                await interaction.response.send_message("❌ 找不到指定的留言！请检查留言ID是否正确。", ephemeral=True)
                return
            
            # 检查是否精選自己的留言
            if message.author.id == interaction.user.id:
                await interaction.response.send_message("❌ 不能精選自己的留言！", ephemeral=True)
                return
            
            # 检查是否已经精選过该用户
            if self.db.is_already_featured(thread_id, message.author.id):
                await interaction.response.send_message(
                    f"❌ 您已经精選过 {message.author.display_name} 的留言了！每个帖子中只能精選每位用户一次。", 
                    ephemeral=True
                )
                return
            
            # 添加精選记录
            success = self.db.add_featured_message(
                guild_id=interaction.guild_id,
                thread_id=thread_id,
                message_id=message.id,
                author_id=message.author.id,
                author_name=message.author.display_name,
                featured_by_id=interaction.user.id,
                featured_by_name=interaction.user.display_name,
                reason=reason
            )
            
            if not success:
                await interaction.response.send_message("❌ 精選失败，该用户可能已经被精選过了。", ephemeral=True)
                return
            
            # 给用户添加积分（總積分）
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
            
            # 创建精選通知
            embed = discord.Embed(
                title="🌟 留言精選",
                description=f"{message.author.display_name} 的留言被设为精選！",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="精選的留言",
                value=f"[点击查看]({message.jump_url})",
                inline=False
            )
            
            embed.add_field(
                name="精選者",
                value=interaction.user.display_name,
                inline=True
            )
            
            if reason:
                embed.add_field(
                    name="精選原因",
                    value=reason,
                    inline=False
                )
            
            embed.set_footer(text=f"留言ID: {message.id}")
            
            # 在訊息內容中 @ 留言者，這樣會真正觸發 Discord 的 @ 通知
            await interaction.response.send_message(content=f"{message.author.mention}", embed=embed)
            
        except Exception as e:
            logger.error(f"精選留言时发生错误: {e}")
            # 檢查是否已經回應過或 interaction 是否有效
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 精選留言时发生错误，请稍后重试。", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 精選留言时发生错误，请稍后重试。", ephemeral=True)
            except Exception as followup_error:
                logger.error(f"发送错误消息时发生错误: {followup_error}")
                # 如果連 followup 都失敗，就記錄錯誤但不拋出異常
    
    @app_commands.command(name="排行榜", description="查看月度積分排行榜")
    async def ranking(self, interaction: discord.Interaction):
        """查看月度積分排行榜"""
        try:
            ranking_data = self.db.get_monthly_ranking(interaction.guild_id, 10)
            current_month = self.db.get_current_month()
            
            embed = discord.Embed(
                title=f"🏆 {current_month} 月度積分排行榜",
                description="本月精選積分排名前十名",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow()
            )
            
            if not ranking_data:
                embed.add_field(
                    name="📝 排行榜",
                    value="本月還沒有積分記錄",
                    inline=False
                )
            else:
                for i, rank_info in enumerate(ranking_data, 1):
                    # 獲取用戶資訊
                    user = self.bot.get_user(rank_info['user_id'])
                    username = user.display_name if user else rank_info['username']
                    
                    # 設置排名圖標
                    if i == 1:
                        rank_icon = "🥇"
                    elif i == 2:
                        rank_icon = "🥈"
                    elif i == 3:
                        rank_icon = "🥉"
                    else:
                        rank_icon = f"{i}."
                    
                    embed.add_field(
                        name=f"{rank_icon} {username}",
                        value=f"積分: {rank_info['points']} 分",
                        inline=False
                    )
            
            embed.set_footer(text=f"每月1日重置積分 • 當前月份: {current_month}")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看排行榜时发生错误: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 查看排行榜时发生错误，请稍后重试。", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 查看排行榜时发生错误，请稍后重试。", ephemeral=True)
            except Exception as followup_error:
                logger.error(f"发送错误消息时发生错误: {followup_error}")
    
    @app_commands.command(name="积分", description="查看自己的积分和精選记录（仅自己可见）")
    async def check_points(self, interaction: discord.Interaction):
        """查看积分命令（隱藏回應）"""
        try:
            user_id = interaction.user.id
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
                      f"**本月積分**: {monthly_points} 積分\n"
                      f"**被精選次數**: {stats['featured_count']} 次\n"
                      f"**精選他人次數**: {stats['featuring_count']} 次",
                inline=False
            )
            
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            # 使用 ephemeral=True 讓回應只有使用者自己可見
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看积分时发生错误: {e}")
            # 檢查是否已經回應過
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ 查看积分时发生错误，请稍后重试。", ephemeral=True)
            else:
                # 如果已經回應過，使用 followup
                await interaction.followup.send("❌ 查看积分时发生错误，请稍后重试。", ephemeral=True)
    
    @app_commands.command(name="帖子统计", description="查看当前帖子的精選统计（仅自己可见）")
    async def thread_stats(self, interaction: discord.Interaction):
        """查看帖子统计命令（隱藏回應）"""
        try:
            # 检查是否在帖子中
            if not interaction.channel.type == discord.ChannelType.public_thread:
                await interaction.response.send_message("❌ 此命令只能在帖子中使用！", ephemeral=True)
                return
            
            thread_id = interaction.channel.id
            
            # 創建分頁視圖
            view = ThreadStatsView(self.bot, thread_id, interaction.guild_id, 1)
            
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
    
    @app_commands.command(name="帮助", description="查看机器人使用说明")
    async def help_command(self, interaction: discord.Interaction):
        """帮助命令"""
        embed = discord.Embed(
            title=f"🤖 {config.BOT_NAME} 使用说明",
            description="这是一个留言精選机器人，帮助楼主管理优质留言并奖励用户。",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="🌟 /精選",
            value="将指定用户的留言设为精選\n• 只有楼主可以使用\n• 每个帖子中每位用户只能被精選一次\n• 被精選用户获得1积分\n• 跨帖子可以重复精選",
            inline=False
        )
        
        embed.add_field(
            name="📊 /积分",
            value="查看自己的积分和精選记录（仅自己可见）",
            inline=False
        )
        
        embed.add_field(
            name="🏆 /排行榜",
            value="查看月度積分排行榜（仅自己可见）\n• 显示本月精選積分排名前十名\n• 每月1日自動重置積分",
            inline=False
        )
        
        embed.add_field(
            name="📈 /帖子统计",
            value="查看当前帖子的精選统计（仅自己可见）\n• 只能在帖子中使用",
            inline=False
        )
        
        embed.add_field(
            name="📋 使用规则",
            value="1. 只有楼主可以精選留言\n2. 不能精選自己的留言\n3. 每个帖子中每位用户只能被精選一次\n4. 跨帖子可以重复精選\n5. 每次精選获得1积分",
            inline=False
        )
        
        embed.set_footer(text="如有问题请联系管理员")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def main():
    """主函数"""
    bot = FeaturedMessageBot()
    
    try:
        await bot.start(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("机器人正在关闭...")
    except Exception as e:
        logger.error(f"启动机器人时发生错误: {e}")

def start_bot():
    """啟動 Discord Bot"""
    import asyncio
    asyncio.run(main())

if __name__ == "__main__":
    start_bot() 