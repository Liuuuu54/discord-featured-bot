import logging

import discord

import config
from app.bot.client import FeaturedMessageBot

logger = logging.getLogger(__name__)

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
            stats = self.bot.db.get_user_stats(
                interaction.user.id,
                interaction.guild_id,
                include_all_guilds=config.APPRECIATOR_CROSS_GUILD_STATS
            )
            
            # 检查被引荐人数或引荐人数要求（满足其中一个即可）
            featured_ok = stats['featured_count'] >= config.APPRECIATOR_MIN_FEATURED
            referrals_ok = stats['featuring_count'] >= config.APPRECIATOR_MIN_REFERRALS
            booklist_link = self.bot.db.get_user_booklist_thread_url(interaction.user.id, interaction.guild_id)
            booklist_ok = bool(booklist_link)
            
            stats_scope_label = "全服累计" if config.APPRECIATOR_CROSS_GUILD_STATS else "本服累计"

            if not featured_ok and not referrals_ok and not booklist_ok:
                await interaction.followup.send(
                    f"❌ 申请条件不满足！\n"
                    f"需要满足以下条件之一：\n"
                    f"• 被引荐至少 {config.APPRECIATOR_MIN_FEATURED} 次（{stats_scope_label}：{stats['featured_count']} 次）\n"
                    f"• 引荐人数至少 {config.APPRECIATOR_MIN_REFERRALS} 人（{stats_scope_label}：{stats['featuring_count']} 人）\n"
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
                    value=f"**引荐人数**（{stats_scope_label}）: {stats['featuring_count']} 人",
                    inline=False
                )
                # 显示用户满足的条件
                conditions_met = []
                if stats['featured_count'] >= config.APPRECIATOR_MIN_FEATURED:
                    conditions_met.append(f"✅ 被引荐 {stats['featured_count']} 次（{stats_scope_label}，满足 {config.APPRECIATOR_MIN_FEATURED} 次要求）")
                if stats['featuring_count'] >= config.APPRECIATOR_MIN_REFERRALS:
                    conditions_met.append(f"✅ 引荐 {stats['featuring_count']} 人（{stats_scope_label}，满足 {config.APPRECIATOR_MIN_REFERRALS} 人要求）")
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

