import discord
from discord.ext import commands
from discord import app_commands
import config
from database import DatabaseManager
from booklist_system import BooklistCommands
import logging
import asyncio
from datetime import datetime
import sqlite3
import re

# 設置日誌
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler() if config.LOG_TO_CONSOLE else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)

class UnfeatureConfirmView(discord.ui.View):
    """取消精選確認視圖"""
    
    def __init__(self, message, thread_id, bot, db):
        super().__init__(timeout=60)  # 60秒超時
        self.message = message
        self.thread_id = thread_id
        self.bot = bot
        self.db = db
    
    @discord.ui.button(label="✅ 確認取消精選", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_unfeature(self, interaction: discord.Interaction, button: discord.ui.Button):
        """確認取消精選"""
        try:
            # 檢查是否為樓主
            thread_owner_id = interaction.channel.owner_id
            if interaction.user.id != thread_owner_id:
                await interaction.response.send_message("❌ 只有樓主才能取消精選留言！", ephemeral=True)
                return
            
            # 檢查精選記錄是否存在
            featured_info = self.db.get_featured_message_by_id(self.message.id, self.thread_id)
            if not featured_info:
                await interaction.response.send_message("❌ 找不到該留言的精選記錄！", ephemeral=True)
                return
            
            # 嘗試刪除機器人的精選消息
            bot_message_deleted = False
            if featured_info.get('bot_message_id'):
                try:
                    bot_message = await interaction.channel.fetch_message(featured_info['bot_message_id'])
                    await bot_message.delete()
                    bot_message_deleted = True
                    logger.info(f"🗑️ 已刪除機器人精選消息 ID: {featured_info['bot_message_id']}")
                except discord.NotFound:
                    logger.warning(f"⚠️ 找不到機器人精選消息 ID: {featured_info['bot_message_id']}")
                except discord.Forbidden:
                    logger.warning(f"⚠️ 沒有權限刪除機器人精選消息 ID: {featured_info['bot_message_id']}")
                except Exception as e:
                    logger.error(f"❌ 刪除機器人精選消息時發生錯誤: {e}")
            
            # 移除精選記錄
            success = self.db.remove_featured_message(self.message.id, self.thread_id)
            if not success:
                await interaction.response.send_message("❌ 取消精選失敗，請稍後重試。", ephemeral=True)
                return
            
            # 創建成功消息
            embed = discord.Embed(
                title="✅ 精選已取消",
                description=f"已成功取消 {featured_info['author_name']} 留言的精選狀態",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="被取消精選的用戶",
                value=featured_info['author_name'],
                inline=True
            )
            
            embed.add_field(
                name="取消者",
                value=interaction.user.display_name,
                inline=True
            )
            

            
            if bot_message_deleted:
                embed.add_field(
                    name="🗑️ 消息清理",
                    value="已自動刪除精選通知消息",
                    inline=False
                )
            
            embed.set_footer(text=f"留言ID: {self.message.id}")
            
            # 發送私密取消精選通知
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"✅ 用戶 {interaction.user.name} 成功取消精選了 {self.message.author.display_name} 的留言")
            
        except Exception as e:
            logger.error(f"確認取消精選時發生錯誤: {e}")
            await interaction.response.send_message(
                "❌ 取消精選過程中發生錯誤，請稍後重試。",
                ephemeral=True
            )
    
    @discord.ui.button(label="❌ 取消操作", style=discord.ButtonStyle.secondary, emoji="🚫")
    async def cancel_unfeature(self, interaction: discord.Interaction, button: discord.ui.Button):
        """取消操作"""
        embed = discord.Embed(
            title="❌ 操作已取消",
            description="取消精選操作已被取消",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class FeatureMessageModal(discord.ui.Modal):
    """精選留言的互動表單"""
    
    def __init__(self, message: discord.Message, thread_id: int, bot, db):
        # 動態設置標題，包含說明信息
        title = f"🌟 精選留言 - {message.author.display_name}"
        super().__init__(title=title)
        self.message = message
        self.thread_id = thread_id
        self.bot = bot
        self.db = db
        
        # 精選原因輸入框
        self.reason = discord.ui.TextInput(
            label="精選原因",
            placeholder="請輸入精選原因（可選）",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        
        # 精選原因輸入框
        self.reason = discord.ui.TextInput(
            label="精選原因",
            placeholder="請輸入精選原因（可選）",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        
        self.add_item(self.reason)
    
    async def on_submit(self, interaction: discord.Interaction):
        """表單提交處理"""
        try:
            # 再次檢查是否已經精選過該用戶（防止重複提交）
            if self.db.is_already_featured(self.thread_id, self.message.author.id):
                await interaction.response.send_message(
                    f"❌ 您已經精選過 {self.message.author.display_name} 的留言了！每個帖子中只能精選每位用戶一次。", 
                    ephemeral=True
                )
                return
            
            # 獲取精選原因
            reason = self.reason.value.strip() if self.reason.value else "無（右鍵精選）"
            
            # 創建精選通知
            embed = discord.Embed(
                title="🌟 留言精選",
                description=f"{self.message.author.display_name} 的留言被設為精選！",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="精選的留言",
                value=f"[點擊查看]({self.message.jump_url})",
                inline=False
            )
            
            embed.add_field(
                name="精選者",
                value=interaction.user.display_name,
                inline=True
            )
            
            embed.add_field(
                name="精選原因",
                value=reason,
                inline=False
            )
            
            embed.set_footer(text=f"留言ID: {self.message.id}")
            
            # 在訊息內容中 @ 留言者，這樣會真正觸發 Discord 的 @ 通知
            await interaction.response.send_message(content=f"{self.message.author.mention}", embed=embed)
            
            # 等待一下让消息发送完成，然后获取机器人发送的消息ID
            await asyncio.sleep(0.5)
            
            # 获取机器人发送的最新消息ID
            bot_message_id = None
            try:
                # 获取频道的最新消息
                async for bot_msg in interaction.channel.history(limit=10):
                    if bot_msg.author.id == self.bot.user.id and bot_msg.embeds:
                        # 检查是否是精选消息（通过检查embed标题）
                        if bot_msg.embeds[0].title == "🌟 留言精選":
                            bot_message_id = bot_msg.id
                            break
            except Exception as e:
                logger.warning(f"⚠️ 無法獲取機器人消息ID: {e}")
            
            # 添加精選記錄（包含機器人消息ID）
            success = self.db.add_featured_message(
                guild_id=interaction.guild_id,
                thread_id=self.thread_id,
                message_id=self.message.id,
                author_id=self.message.author.id,
                author_name=self.message.author.display_name,
                featured_by_id=interaction.user.id,
                featured_by_name=interaction.user.display_name,
                reason=reason,
                bot_message_id=bot_message_id
            )
            
            if not success:
                await interaction.followup.send("❌ 精選失敗，該用戶可能已經被精選過了。", ephemeral=True)
                return
            
            # 記錄成功
            logger.info(f"✅ 用戶 {interaction.user.name} 成功精選了 {self.message.author.display_name} 的留言")
            
        except Exception as e:
            logger.error(f"精選留言表單提交時發生錯誤: {e}")
            await interaction.followup.send(
                "❌ 精選過程中發生錯誤，請稍後重試。",
                ephemeral=True
            )

class FeaturedMessageBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True  # 需要members权限来管理角色
        
        super().__init__(
            command_prefix='!',  # 虽然使用斜杠命令，但仍保留前缀以防万一
            intents=intents,
            help_command=None
        )
        
        self.db = DatabaseManager(config.DATABASE_FILE)
        
    async def setup_hook(self):
        """机器人启动时的设置"""
        # 註冊 persistent view（重啟後仍可點舊消息按鈕）
        self.add_view(AppreciatorApplicationView(self))
        await self.add_cog(FeaturedCommands(self))
        await self.add_cog(BooklistCommands(self))
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
        logger.info('📋 可用命令: /精选, /精选记录, /帖子统计, /总排行, /鉴赏申请窗口, /全服精选列表, /添加至书单, /管理书单, /公开书单, /全服书单列表')
        logger.info('=' * 50)

    async def on_interaction(self, interaction: discord.Interaction):
        """统一记录交互日志，覆盖斜杠命令/右键菜单/按钮/表单。"""
        try:
            guild_name = interaction.guild.name if interaction.guild else "DM"
            guild_id = interaction.guild.id if interaction.guild else 0
            channel_id = interaction.channel.id if interaction.channel else 0
            user_name = interaction.user.name if interaction.user else "Unknown"
            user_id = interaction.user.id if interaction.user else 0

            # 斜杠命令 / 右键菜单
            if interaction.type == discord.InteractionType.application_command:
                command_name = interaction.command.qualified_name if interaction.command else "unknown"
                logger.info(
                    f"🧭 交互: application_command | 命令: {command_name} | 用户: {user_name}({user_id}) | "
                    f"群组: {guild_name}({guild_id}) | 频道: {channel_id}"
                )
            # 按钮、下拉菜单等组件
            elif interaction.type == discord.InteractionType.component:
                custom_id = interaction.data.get("custom_id") if interaction.data else "unknown"
                logger.info(
                    f"🧭 交互: component | custom_id: {custom_id} | 用户: {user_name}({user_id}) | "
                    f"群组: {guild_name}({guild_id}) | 频道: {channel_id}"
                )
            # Modal 表单提交
            elif interaction.type == discord.InteractionType.modal_submit:
                custom_id = interaction.data.get("custom_id") if interaction.data else "unknown"
                logger.info(
                    f"🧭 交互: modal_submit | custom_id: {custom_id} | 用户: {user_name}({user_id}) | "
                    f"群组: {guild_name}({guild_id}) | 频道: {channel_id}"
                )
        except Exception as e:
            logger.debug(f"记录交互日志失败: {e}")

    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        """当消息被删除时，清理公开书单最小索引，避免数据膨胀。"""
        try:
            self.db.deactivate_public_booklist_index(payload.message_id)
        except Exception as e:
            logger.debug(f"清理公开书单索引失败(单条): {e}")

    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent):
        """当批量删消息时，清理公开书单最小索引。"""
        for message_id in payload.message_ids:
            try:
                self.db.deactivate_public_booklist_index(message_id)
            except Exception as e:
                logger.debug(f"清理公开书单索引失败(批量): {e}")

    async def on_message(self, message: discord.Message):
        """书单帖发言限制：仅绑定者本人可发言，其他人只能反应。"""
        if message.author.bot:
            return

        if message.guild and isinstance(message.channel, discord.Thread):
            bound_owner_id = self.db.get_booklist_thread_owner(message.guild.id, message.channel.id)
            if bound_owner_id and message.author.id != bound_owner_id:
                try:
                    await message.delete()
                    logger.info(
                        f"🧹 已删除书单帖非楼主留言 | 用户: {message.author.name}({message.author.id}) | "
                        f"帖子: {message.channel.id} | 群组: {message.guild.id}"
                    )
                except discord.Forbidden:
                    logger.warning(
                        f"⚠️ 无权限删除书单帖留言 | 用户: {message.author.id} | 帖子: {message.channel.id} | 群组: {message.guild.id}"
                    )
                except Exception as e:
                    logger.warning(f"删除书单帖留言失败: {e}")
                return

        await self.process_commands(message)
    
    async def on_command_error(self, ctx, error):
        """处理命令错误"""
        if isinstance(error, commands.CommandNotFound):
            # 忽略不存在的命令错误，不记录日志
            return
        
        # 记录其他类型的错误
        logger.error(f"命令执行错误: {error}")
        
        # 发送用户友好的错误消息
        try:
            if isinstance(error, commands.MissingPermissions):
                await ctx.send("❌ 您没有权限执行此命令！", delete_after=5)
            elif isinstance(error, commands.BotMissingPermissions):
                await ctx.send("❌ 机器人缺少必要的权限！", delete_after=5)
            elif isinstance(error, commands.CommandOnCooldown):
                await ctx.send(f"⏰ 命令冷却中，请等待 {error.retry_after:.1f} 秒后重试", delete_after=5)
            else:
                await ctx.send("❌ 命令执行时发生错误，请稍后重试", delete_after=5)
        except Exception as e:
            logger.error(f"发送错误消息失败: {e}")
    
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """处理斜杠命令错误"""
        if isinstance(error, app_commands.CommandNotFound):
            # 忽略不存在的斜杠命令错误，不记录日志
            return
        
        # 记录其他类型的错误
        logger.error(f"斜杠命令执行错误: {error}")
        
        # 发送用户友好的错误消息
        try:
            if isinstance(error, app_commands.MissingPermissions):
                await interaction.response.send_message("❌ 您没有权限执行此命令！", ephemeral=True)
            elif isinstance(error, app_commands.BotMissingPermissions):
                await interaction.response.send_message("❌ 机器人缺少必要的权限！", ephemeral=True)
            elif isinstance(error, app_commands.CommandOnCooldown):
                await interaction.response.send_message(f"⏰ 命令冷却中，请等待 {error.retry_after:.1f} 秒后重试", ephemeral=True)
            else:
                await interaction.response.send_message("❌ 命令执行时发生错误，请稍后重试", ephemeral=True)
        except Exception as e:
            logger.error(f"发送斜杠命令错误消息失败: {e}")

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

class AppreciatorApplicationView(discord.ui.View):
    """鉴赏申请窗口视图"""
    def __init__(self, bot: FeaturedMessageBot):
        super().__init__(timeout=None)  # 永久有效
        self.bot = bot
    
    @discord.ui.button(
        label="申请鉴赏家身份",
        style=discord.ButtonStyle.success,
        emoji="📜",
        custom_id="appreciator:apply:v1"
    )
    async def apply_appreciator(self, interaction: discord.Interaction, button: discord.ui.Button):
        """申请鉴赏家身份"""
        # 立即响应交互，避免超时
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 获取用户统计信息
            stats = self.bot.db.get_user_stats(interaction.user.id, interaction.guild_id)
            
            # 检查被引荐人数或引荐人数要求（满足其中一个即可）
            featured_ok = stats['featured_count'] >= config.APPRECIATOR_MIN_FEATURED
            referrals_ok = stats['featuring_count'] >= config.APPRECIATOR_MIN_REFERRALS
            booklist_link = self.bot.db.get_user_booklist_thread_url(interaction.user.id, interaction.guild_id)
            booklist_ok = bool(booklist_link)
            
            if not featured_ok and not referrals_ok and not booklist_ok:
                await interaction.followup.send(
                    f"❌ 申请条件不满足！\n"
                    f"需要满足以下条件之一：\n"
                    f"• 被引荐至少 {config.APPRECIATOR_MIN_FEATURED} 次（您当前被引荐了 {stats['featured_count']} 次）\n"
                    f"• 引荐人数至少 {config.APPRECIATOR_MIN_REFERRALS} 人（您当前引荐了 {stats['featuring_count']} 人）\n"
                    f"• 绑定书单帖链接（您当前：{'已绑定' if booklist_ok else '未绑定'}）",
                    ephemeral=True
                )
                return
            
            # 检查是否已经有鉴赏家身份
            # 使用 fetch_member 而不是 get_member，避免缓存问题
            try:
                member = await interaction.guild.fetch_member(interaction.user.id)
            except discord.NotFound:
                await interaction.followup.send(
                    "❌ 无法找到您的成员信息，请确认您在服务器中。",
                    ephemeral=True
                )
                return
            except discord.HTTPException as e:
                logger.error(f"获取成员信息时发生HTTP错误: {e}")
                await interaction.followup.send(
                    "❌ 获取成员信息时发生错误，请稍后重试。",
                    ephemeral=True
                )
                return
            
            if member:
                for role in member.roles:
                    if role.name == config.APPRECIATOR_ROLE_NAME:
                        await interaction.followup.send(
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
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
            
            # 分配角色
            try:
                # 确认 appreciator_role 不为 None
                if not appreciator_role:
                    await interaction.followup.send(
                        f"❌ 无法找到或创建 {config.APPRECIATOR_ROLE_NAME} 角色，请联系管理员。",
                        ephemeral=True
                    )
                    return
                
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
                    value=f"**引荐人数**: {stats['featuring_count']} 人",
                    inline=False
                )
                # 显示用户满足的条件
                conditions_met = []
                if stats['featured_count'] >= config.APPRECIATOR_MIN_FEATURED:
                    conditions_met.append(f"✅ 被引荐 {stats['featured_count']} 次（满足 {config.APPRECIATOR_MIN_FEATURED} 次要求）")
                if stats['featuring_count'] >= config.APPRECIATOR_MIN_REFERRALS:
                    conditions_met.append(f"✅ 引荐 {stats['featuring_count']} 人（满足 {config.APPRECIATOR_MIN_REFERRALS} 人要求）")
                if booklist_ok:
                    conditions_met.append("✅ 已绑定书单帖链接")
                
                embed.add_field(
                    name="🎯 申请条件",
                    value=f"**满足条件**：\n" + "\n".join(conditions_met) + f"\n\n**完整要求（满足其一即可）**：\n• 被引荐至少 {config.APPRECIATOR_MIN_FEATURED} 次\n• 引荐至少 {config.APPRECIATOR_MIN_REFERRALS} 人\n• 已绑定书单帖链接",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
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
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
                
        except Exception as e:
            logger.error(f"申请{config.APPRECIATOR_ROLE_NAME}身份时发生错误: {e}")
            await interaction.followup.send(
                "❌ 申请过程中发生错误，请稍后重试。",
                ephemeral=True
            )

class FeaturedCommands(commands.Cog):
    def __init__(self, bot: FeaturedMessageBot):
        self.bot = bot
        self.db = bot.db
        
        # 註冊 Message Context Menu
        context_menu = app_commands.ContextMenu(
            name="精选此留言",
            callback=self.context_feature_message
        )
        self.bot.tree.add_command(context_menu)
        logger.info(f"✅ 已註冊 Context Menu: {context_menu.name}")
        
        # 註冊取消精選 Context Menu
        unfeature_menu = app_commands.ContextMenu(
            name="取消精选",
            callback=self.context_unfeature_message
        )
        self.bot.tree.add_command(unfeature_menu)
        logger.info(f"✅ 已註冊 Context Menu: {unfeature_menu.name}")
        
        # 註冊查看精選紀錄 Context Menu
        points_menu = app_commands.ContextMenu(
            name="查看精选记录",
            callback=self.context_check_featured_stats
        )
        self.bot.tree.add_command(points_menu)
        logger.info(f"✅ 已註冊 Context Menu: {points_menu.name}")
    
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
        
        # 检查长度（最少字符数）
        if len(content) < config.MIN_MESSAGE_LENGTH:
            return {'valid': False, 'reason': f'留言内容至少需要{config.MIN_MESSAGE_LENGTH}个字符！'}
        
        # 检查长度（最大字符数）
        if config.MAX_MESSAGE_LENGTH > 0 and len(content) > config.MAX_MESSAGE_LENGTH:
            return {'valid': False, 'reason': f'留言内容不能超过{config.MAX_MESSAGE_LENGTH}个字符！'}
        
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
    
    async def context_feature_message(self, interaction: discord.Interaction, message: discord.Message):
        """Message Context Menu 精選留言回調"""
        # 記錄命令使用
        logger.info(f"🔍 用户 {interaction.user.name} (ID: {interaction.user.id}) 在群组 {interaction.guild.name} (ID: {interaction.guild.id}) 使用了右鍵精選功能，留言ID: {message.id}")
        
        try:
            # 檢查是否在帖子中
            if not interaction.channel.type == discord.ChannelType.public_thread:
                await interaction.response.send_message("❌ 此功能只能在帖子中使用！", ephemeral=True)
                return
            
            thread_id = interaction.channel.id
            thread_owner_id = interaction.channel.owner_id
            
            # 檢查是否為樓主
            if interaction.user.id != thread_owner_id:
                await interaction.response.send_message("❌ 只有樓主才能精選留言！", ephemeral=True)
                return
            
            # 檢查是否精選自己的留言
            if message.author.id == interaction.user.id:
                await interaction.response.send_message("❌ 不能精選自己的留言！", ephemeral=True)
                return
            
            # 檢查留言內容質量
            content_check = self.check_message_quality(message)
            if not content_check['valid']:
                await interaction.response.send_message(f"❌ {content_check['reason']}", ephemeral=True)
                return
            
            # 檢查是否已經精選過該用戶
            if self.db.is_already_featured(thread_id, message.author.id):
                await interaction.response.send_message(
                    f"❌ 您已經精選過 {message.author.display_name} 的留言了！每個帖子中只能精選每位用戶一次。", 
                    ephemeral=True
                )
                return
            
            # 創建精選原因表單
            modal = FeatureMessageModal(message, thread_id, self.bot, self.db)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"右鍵精選留言時發生錯誤: {e}")
            await interaction.response.send_message(
                "❌ 精選過程中發生錯誤，請稍後重試。",
                ephemeral=True
            )
    
    async def context_unfeature_message(self, interaction: discord.Interaction, message: discord.Message):
        """Message Context Menu 取消精選留言回調"""
        # 記錄命令使用
        logger.info(f"🔍 用户 {interaction.user.name} (ID: {interaction.user.id}) 在群组 {interaction.guild.name} (ID: {interaction.guild.id}) 使用了右鍵取消精選功能，留言ID: {message.id}")
        
        try:
            # 檢查是否在帖子中
            if not interaction.channel.type == discord.ChannelType.public_thread:
                await interaction.response.send_message("❌ 此功能只能在帖子中使用！", ephemeral=True)
                return
            
            thread_id = interaction.channel.id
            thread_owner_id = interaction.channel.owner_id
            
            # 檢查是否為樓主
            if interaction.user.id != thread_owner_id:
                await interaction.response.send_message("❌ 只有樓主才能取消精選留言！", ephemeral=True)
                return
            
            # 檢查精選記錄是否存在
            featured_info = self.db.get_featured_message_by_id(message.id, thread_id)
            if not featured_info:
                await interaction.response.send_message("❌ 找不到該留言的精選記錄！", ephemeral=True)
                return
            
            # 創建確認取消精選通知
            embed = discord.Embed(
                title="⚠️ 確認取消精選",
                description=f"您即將取消 {message.author.display_name} 留言的精選狀態",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="被取消精選的用戶",
                value=message.author.display_name,
                inline=True
            )
            
            embed.add_field(
                name="留言連結",
                value=f"[點擊查看]({message.jump_url})",
                inline=True
            )
            
            embed.add_field(
                name="⚠️ 操作後果",
                value=f"• 精選記錄將從數據庫中永久刪除\n"
                      f"• 機器人的精選通知消息將被自動刪除\n"
                      f"• **此操作不可撤銷，請謹慎操作**",
                inline=False
            )
            
            embed.set_footer(text=f"留言ID: {message.id} | 60秒後自動取消")
            
            # 創建確認視圖
            view = UnfeatureConfirmView(message, thread_id, self.bot, self.db)
            
            # 發送確認消息
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"右鍵取消精選留言時發生錯誤: {e}")
            await interaction.response.send_message(
                "❌ 取消精選過程中發生錯誤，請稍後重試。",
                ephemeral=True
            )
    
    async def context_check_featured_stats(self, interaction: discord.Interaction, message: discord.Message):
        """Message Context Menu 查看精選紀錄回調"""
        # 記錄命令使用
        logger.info(f"🔍 用户 {interaction.user.name} (ID: {interaction.user.id}) 在群组 {interaction.guild.name} (ID: {interaction.guild.id}) 使用了右鍵查看精選紀錄功能，目標用戶: {message.author.display_name}")
        
        try:
            # 獲取目標用戶（留言作者）
            target_user = message.author
            user_id = target_user.id
            
            # 創建分頁視圖（默認顯示被精選記錄）
            view = FeaturedRecordsView(self.bot, user_id, interaction.guild_id, 1, "featured")
            
            # 先準備好嵌入訊息，避免在發送回應後再調用異步方法
            embed = await view.get_records_embed()
            
            # 精选记录默认私密回覆，避免洗版
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"右鍵查看精選紀錄時發生錯誤: {e}")
            await interaction.response.send_message(
                "❌ 查看精選紀錄時發生錯誤，請稍後重試。",
                ephemeral=True
            )
    
    @app_commands.command(name="精选", description="将指定用户的留言设为精选（留言需至少10字符且不能只含表情）")
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
            
            embed.set_footer(text=f"留言ID: {message_id_int} | 60秒后自动取消")
            
            # 使用获取到的消息对象，如果获取不到则只传ID
            try:
                message = await interaction.channel.fetch_message(message_id_int)
                view = UnfeatureConfirmView(message, thread_id, self.bot, self.db)
            except Exception:
                # 創建一個帶有 ID 的假 Message 對象
                class FakeMessage:
                    def __init__(self, msg_id):
                        self.id = msg_id
                view = UnfeatureConfirmView(FakeMessage(message_id_int), thread_id, self.bot, self.db)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"取消精选留言时发生错误: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 取消精选留言时发生错误，请稍后重试。", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 取消精选留言时发生错误，请稍后重试。", ephemeral=True)
            except Exception as followup_error:
                logger.error(f"发送错误消息时发生错误: {followup_error}")
                
    @app_commands.command(name="总排行", description="查看引薦人數排行榜（管理組，支持時間範圍）")
    @app_commands.describe(
        start_date="起始日期（可选，格式：YYYY-MM-DD，例如：2024-01-01）",
        end_date="结束日期（可选，格式：YYYY-MM-DD，例如：2024-12-31）"
    )
    async def total_ranking(self, interaction: discord.Interaction, start_date: str = None, end_date: str = None):
        """查看總排行榜命令（僅管理組可用）- 支持引薦人數排行，支持時間範圍"""
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
            
            # 創建增強排行榜視圖（預設為引薦排行）
            view = EnhancedRankingView(self.bot, interaction.guild_id, 1, start_date, end_date)
            
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
    
    @app_commands.command(name="精选记录", description="查看用戶精選紀錄與引荐統計（如果沒有指定用戶，默認查看自己）")
    async def check_featured_stats(self, interaction: discord.Interaction, user: discord.Member = None):
        """查看精選紀錄命令（支持查看其他用戶）"""
        # 记录命令使用
        target_user = user.name if user else interaction.user.name
        logger.info(f"🔍 用户 {interaction.user.name} (ID: {interaction.user.id}) 在群组 {interaction.guild.name} (ID: {interaction.guild.id}) 查看了用户 {target_user} 的精選紀錄")
        
        try:
            # 如果沒有指定用戶，默認查看自己
            if user is None:
                user = interaction.user
            
            user_id = user.id
            
            # 創建分頁視圖（默認顯示被精選記錄）
            view = FeaturedRecordsView(self.bot, user_id, interaction.guild_id, 1, "featured")
            
            # 先準備好嵌入訊息，避免在發送回應後再調用異步方法
            embed = await view.get_records_embed()
            
            # 精选记录默认私密回覆，避免洗版
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看精選紀錄時發生錯誤: {e}")
            # 檢查是否已經回應過
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ 查看精選紀錄時發生錯誤，請稍後重試。", ephemeral=True)
            else:
                # 如果已經回應過，使用 followup
                await interaction.followup.send("❌ 查看精選紀錄時發生錯誤，請稍後重試。", ephemeral=True)
    
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
    


    @app_commands.command(name="鉴赏申请窗口", description="创建鉴赏家申请窗口（管理组）")
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
                      f"• 被引荐至少 {config.APPRECIATOR_MIN_FEATURED} 次\n"
                      f"• 引荐至少 {config.APPRECIATOR_MIN_REFERRALS} 人\n"
                      f"• 已绑定书单帖链接（可在 `/管理书单` 设置）",
                inline=False
            )
            embed.add_field(
                name="🎯 获得身份",
                value=f"**身份组**: {config.APPRECIATOR_ROLE_NAME}",
                inline=False
            )
            embed.add_field(
                name="💡 说明",
                value="• 滿足條件的用户可点击按钮自動獲得身份\n• 已擁有該身份的用户無法重複申請\n• 機器人會自動檢查您的精選紀錄和引薦人數\n• 如遇權限問題，請聯繫群組管理員",
                inline=False
            )
            embed.add_field(
                name="📖 快速使用指南",
                value="**如何参与精选系统？**\n"
                      "• `/精选` - 楼主可精选优质留言（右键留言→复制链接）\n"
                      "• `/精选紀錄` - 查看自己的精選紀錄與引荐統計\n"
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

    @app_commands.command(name="全服精选列表", description="查看全服精選留言列表（管理组，支持时间范围和时间/讚数排序）")
    @app_commands.describe(
        start_date="起始日期（可选，格式：YYYY-MM-DD，例如：2024-01-01）",
        end_date="结束日期（可选，格式：YYYY-MM-DD，例如：2024-12-31）"
    )
    async def all_featured_messages(self, interaction: discord.Interaction, start_date: str = None, end_date: str = None):
        """查看全服精選留言命令（仅管理组可用）"""
        # 记录命令使用
        logger.info(f"🔍 用户 {interaction.user.name} (ID: {interaction.user.id}) 在群组 {interaction.guild.name} (ID: {interaction.guild.id}) 查看了全服精選留言，时间范围: {start_date} 至 {end_date}")
        
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
            
            # 創建全服精選留言視圖（預設為時間排序）
            view = AllFeaturedMessagesView(self.bot, interaction.guild_id, 1, "time", start_date, end_date)
            
            # 獲取嵌入訊息
            embed = await view.get_messages_embed(interaction)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看全服精選留言时发生错误: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 查看全服精選留言时发生错误，请稍后重试。", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 查看全服精選留言时发生错误，请稍后重试。", ephemeral=True)
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
