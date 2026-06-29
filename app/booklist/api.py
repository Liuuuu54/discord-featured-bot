"""书单发布 HTTP 接口。

网页后端在校验用户身份与书单归属后，把「发布到 Discord」请求转发到这里，
由 bot 在目标论坛帖内发出（或更新）一条书单 embed 消息。

设计要点：
- 与 discord.py 同进程、同事件循环（aiohttp.web 背景站点）。
- server-to-server 共享密钥认证（请求头 X-API-Key），前端不参与。
- 幂等：同一网页书单在同一频道重复发布时，编辑既有消息而非新发，天然支持后续更新。
"""

import hmac
import logging
from typing import Optional, Tuple
from urllib.parse import urlparse

import discord
from aiohttp import web

import config
from app.utils.text import truncate as _truncate

logger = logging.getLogger(__name__)


def _parse_thread_url(url: str) -> Optional[Tuple[int, int]]:
    """从 Discord 链接解析 (guild_id, thread_id)。

    形如 https://discord.com/channels/{guild_id}/{thread_id}
    """
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return None
    if parsed.netloc not in ("discord.com", "www.discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com"):
        return None
    parts = [p for p in parsed.path.split("/") if p]
    # ['channels', guild_id, thread_id, (optional message_id)]
    if len(parts) < 3 or parts[0] != "channels":
        return None
    try:
        guild_id = int(parts[1])
        thread_id = int(parts[2])
    except ValueError:
        return None
    return guild_id, thread_id


def _build_entry_block(item: dict, index: int) -> str:
    title = _truncate(str(item.get("title") or "（无标题）"), 80)
    url = str(item.get("url") or "").strip()
    review = str(item.get("review") or "").strip()
    review_text = _truncate(review, 300) if review else "（无评价）"
    url_text = _truncate(url, 400) if url else "（无链接）"
    block = (
        f"📌 标题：{title}\n"
        f"🔗 连结：{url_text}\n"
        f"📝 评价：{review_text}"
    )
    # Discord 单个 field value 上限 1024
    return _truncate(block, 1024)


def _build_embed(payload: dict, publisher_user_id: int) -> discord.Embed:
    title = _truncate(str(payload.get("title") or "未命名书单"), 200)
    description = str(payload.get("description") or "").strip()
    cover = str(payload.get("cover_image_url") or "").strip()
    items = payload.get("items") or []

    head = f"发布者：<@{publisher_user_id}>"
    desc = f"{head}\n\n{description}" if description else head

    embed = discord.Embed(
        title=f"📖 公开书单：{title}",
        description=_truncate(desc, 4000),
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow(),
    )
    if cover.startswith("http"):
        embed.set_thumbnail(url=cover)

    total = len(items)
    max_entries = max(1, config.BOOKLIST_API_MAX_ENTRIES)
    shown = items[:max_entries]

    embed.add_field(
        name=f"帖子列表（共 {total} 帖）",
        value="以下为本书单收录：",
        inline=False,
    )
    for idx, item in enumerate(shown, 1):
        embed.add_field(
            name=f"ID {idx:02}",
            value=_build_entry_block(item, idx),
            inline=False,
        )
    if total > len(shown):
        embed.add_field(
            name="……",
            value=f"还有 {total - len(shown)} 项，完整书单请见网页版。",
            inline=False,
        )

    booklist_id = payload.get("booklist_id")
    if booklist_id is not None:
        embed.set_footer(text=f"网页书单 #{booklist_id}")
    return embed


class BooklistPublishAPI:
    def __init__(self, bot):
        self.bot = bot

    def _check_auth(self, request: web.Request) -> bool:
        provided = request.headers.get("X-API-Key", "")
        if not provided:
            return False
        return hmac.compare_digest(provided, config.BOOKLIST_API_SECRET)

    async def health(self, request: web.Request) -> web.Response:
        ready = self.bot.is_ready()
        return web.json_response({"ok": True, "ready": ready})

    async def handle_publish(self, request: web.Request) -> web.Response:
        if not self._check_auth(request):
            return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid json"}, status=400)

        # ── 参数校验 ─────────────────────────────────────────
        thread_url = payload.get("thread_url")
        discord_user_id_raw = payload.get("discord_user_id")
        booklist_id_raw = payload.get("booklist_id")
        items = payload.get("items")

        if not thread_url or discord_user_id_raw is None or booklist_id_raw is None:
            return web.json_response(
                {"ok": False, "error": "missing required field: thread_url / discord_user_id / booklist_id"},
                status=400,
            )
        if not isinstance(items, list):
            return web.json_response({"ok": False, "error": "items must be a list"}, status=400)

        try:
            discord_user_id = int(discord_user_id_raw)
            booklist_id = int(booklist_id_raw)
        except (TypeError, ValueError):
            return web.json_response({"ok": False, "error": "discord_user_id / booklist_id must be integers"}, status=400)

        parsed = _parse_thread_url(thread_url)
        if not parsed:
            return web.json_response({"ok": False, "error": "invalid thread_url"}, status=400)
        guild_id, thread_id = parsed

        # ── 频道与权限校验 ──────────────────────────────────
        if not self.bot.is_ready():
            return web.json_response({"ok": False, "error": "bot not ready"}, status=503)

        channel = self.bot.get_channel(thread_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(thread_id)
            except discord.NotFound:
                return web.json_response({"ok": False, "error": "thread not found"}, status=404)
            except discord.Forbidden:
                return web.json_response({"ok": False, "error": "bot has no access to thread"}, status=403)
            except Exception as e:
                logger.warning(f"fetch_channel 失败: {e}")
                return web.json_response({"ok": False, "error": "fetch thread failed"}, status=502)

        if not isinstance(channel, discord.Thread) or not channel.parent or channel.parent.type != discord.ChannelType.forum:
            return web.json_response({"ok": False, "error": "target is not a forum thread"}, status=403)

        if channel.guild and channel.guild.id != guild_id:
            return web.json_response({"ok": False, "error": "guild mismatch"}, status=400)

        if channel.owner_id != discord_user_id:
            return web.json_response({"ok": False, "error": "publisher is not the thread owner"}, status=403)

        # ── 发布或更新 ──────────────────────────────────────
        embed = _build_embed(payload, discord_user_id)
        existing = self.bot.db.get_webpage_published_booklist(booklist_id, thread_id)

        updated = False
        message = None
        if existing:
            try:
                message = await channel.fetch_message(existing["message_id"])
                await message.edit(embed=embed)
                updated = True
            except discord.NotFound:
                message = None  # 旧消息已被删除，改为新发
            except discord.Forbidden:
                return web.json_response({"ok": False, "error": "no permission to edit message"}, status=403)
            except Exception as e:
                logger.warning(f"编辑书单消息失败，将尝试新发: {e}")
                message = None

        if message is None:
            try:
                message = await channel.send(embed=embed)
                updated = False
            except discord.Forbidden:
                return web.json_response({"ok": False, "error": "no permission to send in thread"}, status=403)
            except Exception as e:
                logger.error(f"发送书单消息失败: {e}")
                return web.json_response({"ok": False, "error": "send failed"}, status=502)

        self.bot.db.upsert_webpage_published_booklist(
            webpage_booklist_id=booklist_id,
            guild_id=guild_id,
            channel_id=thread_id,
            message_id=message.id,
            publisher_user_id=discord_user_id,
        )

        logger.info(
            f"📖 网页书单发布{'（更新）' if updated else '（新发）'} | booklist={booklist_id} | "
            f"thread={thread_id} | publisher={discord_user_id} | message={message.id}"
        )
        return web.json_response({
            "ok": True,
            "updated": updated,
            "message_id": str(message.id),
            "message_url": message.jump_url,
        })


async def start_booklist_api(bot) -> Optional[web.AppRunner]:
    """在 bot 事件循环内启动书单发布 HTTP 站点。返回 runner（用于关闭），未启动则返回 None。"""
    if not config.BOOKLIST_API_ENABLED:
        logger.info("📕 书单发布接口未启用（BOOKLIST_API_ENABLED=false），跳过启动。")
        return None
    if not config.BOOKLIST_API_SECRET:
        logger.warning("⚠️ 书单发布接口已启用但未设置 BOOKLIST_API_SECRET，为安全起见不启动。")
        return None

    api = BooklistPublishAPI(bot)
    app = web.Application()
    app.add_routes([
        web.post("/booklist/publish", api.handle_publish),
        web.get("/healthz", api.health),
    ])

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.BOOKLIST_API_HOST, config.BOOKLIST_API_PORT)
    await site.start()
    logger.info(f"📗 书单发布接口已启动：http://{config.BOOKLIST_API_HOST}:{config.BOOKLIST_API_PORT}")
    return runner
