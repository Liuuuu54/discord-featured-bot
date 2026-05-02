import asyncio
import logging

import discord

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

