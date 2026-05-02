import asyncio
import logging
import re
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

import config
from app.bot.client import FeaturedMessageBot
from app.features.featured_views import (
    AllFeaturedMessagesView,
    AppreciatorApplicationView,
    EnhancedRankingView,
    FeaturedRecordsView,
    FeatureMessageModal,
    ThreadStatsView,
    UnfeatureConfirmView,
)
from app.utils.discord_links import extract_message_id_from_url

logger = logging.getLogger(__name__)

class FeaturedCommands(commands.Cog):
    message_group = app_commands.Group(name="留言", description="留言精选相关指令")

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
        return extract_message_id_from_url(url)
    
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
    
    @message_group.command(name="精选", description="将指定用户的留言设为精选（留言需至少10字符且不能只含表情）")
    @app_commands.describe(
        message_url="要精选的留言URL（右键留言 -> 复制链接）",
        reason="精选原因（可选）"
    )
    async def feature_message(self, interaction: discord.Interaction, message_url: str, reason: str = None):
        """精選留言命令"""
        # 记录命令使用
        logger.info(f"🔍 用户 {interaction.user.name} (ID: {interaction.user.id}) 在群组 {interaction.guild.name} (ID: {interaction.guild.id}) 使用了 /留言 精选 命令，留言URL: {message_url}")
        
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
    
    @message_group.command(name="精选取消", description="取消指定留言的精选状态（仅楼主可用）")
    @app_commands.describe(
        message_url="要取消精选的留言URL（右键留言 -> 复制链接）"
    )
    async def unfeature_message(self, interaction: discord.Interaction, message_url: str):
        """取消精選留言命令"""
        # 记录命令使用
        logger.info(f"🔍 用户 {interaction.user.name} (ID: {interaction.user.id}) 在群组 {interaction.guild.name} (ID: {interaction.guild.id}) 使用了 /留言 精选取消 命令，留言URL: {message_url}")
        
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
                
    @message_group.command(name="总排行", description="查看引荐人数排行榜（管理组，支持时间范围）")
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
    
    @message_group.command(name="精选记录", description="查看用户精选记录与引荐统计（如果没有指定用户，默认查看自己）")
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
    
    @message_group.command(name="帖子统计", description="查看当前帖子的精选统计（仅自己可见）")
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
    


    @message_group.command(name="鉴赏申请窗口", description="创建鉴赏家申请窗口（管理组）")
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
                      f"• 已绑定书单帖链接（可在 `/书单 管理书单` 设置）",
                inline=False
            )
            embed.add_field(
                name="🎯 获得身份",
                value=f"**身份组**: {config.APPRECIATOR_ROLE_NAME}",
                inline=False
            )
            embed.add_field(
                name="💡 说明",
                value="• 满足条件的用户可点击按钮自动获得身份\n• 已拥有该身份的用户无法重复申请\n• 机器人会自动检查您的精选记录和引荐人数\n• 如遇权限问题，请联系群组管理员",
                inline=False
            )
            embed.add_field(
                name="📖 快速使用指南",
                value="**如何参与精选系统？**\n"
                      "• `/留言 精选` - 楼主可精选优质留言（右键留言→复制链接）\n"
                      "• `/留言 精选记录` - 查看自己的精选记录与引荐统计\n"
                      "• `/留言 帖子统计` - 在帖子中查看精选统计\n\n"
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

    @message_group.command(name="全服精选列表", description="查看全服精选留言列表（管理组，支持时间范围和时间/赞数排序）")
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
