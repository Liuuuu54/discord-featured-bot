import discord


def has_admin_permission(member: discord.Member, admin_role_names: list[str]) -> bool:
    has_role = any(role.name in admin_role_names for role in member.roles)
    has_perm = member.guild_permissions.manage_messages or member.guild_permissions.administrator
    return has_role or has_perm


def can_manage_thread_feature(member: discord.Member, channel, admin_role_names: list[str]) -> bool:
    """判断成员是否有权在该帖精选/取消精选：楼主 或 版主。

    版主 = 管理组角色 / manage_messages / administrator（has_admin_permission），
    或对该帖具备 manage_threads 权限（频道级协管）。与 owner 是否在群无关，
    因此帖主被 ban 后版主仍可操作，避免帖子锁死。
    """
    if getattr(channel, "owner_id", None) == member.id:
        return True
    if has_admin_permission(member, admin_role_names):
        return True
    try:
        return channel.permissions_for(member).manage_threads
    except Exception:
        return False
