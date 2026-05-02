import discord


def has_admin_permission(member: discord.Member, admin_role_names: list[str]) -> bool:
    has_role = any(role.name in admin_role_names for role in member.roles)
    has_perm = member.guild_permissions.manage_messages or member.guild_permissions.administrator
    return has_role or has_perm
