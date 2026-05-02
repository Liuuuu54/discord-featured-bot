import re
from typing import Optional


DISCORD_CHANNEL_URL_PATTERN = re.compile(r"^https://discord\.com/channels/(\d+)/(\d+)(?:/\d+)?$")
DISCORD_MESSAGE_URL_PATTERN = re.compile(r"https://discord\.com/channels/\d+/\d+/(\d+)")


def is_valid_discord_url(url: str) -> bool:
    return DISCORD_CHANNEL_URL_PATTERN.match(url.strip()) is not None


def parse_discord_url(url: str) -> Optional[tuple[int, int]]:
    match = DISCORD_CHANNEL_URL_PATTERN.match(url.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def extract_message_id_from_url(url: str) -> int:
    match = DISCORD_MESSAGE_URL_PATTERN.search(url)
    if match:
        return int(match.group(1))
    raise ValueError("Invalid Discord message URL")
