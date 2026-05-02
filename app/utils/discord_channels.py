import discord


def is_thread_channel(channel: discord.abc.GuildChannel) -> bool:
    return isinstance(channel, discord.Thread)
