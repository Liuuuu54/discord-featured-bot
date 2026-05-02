from typing import Optional


def safe_int(value: str) -> Optional[int]:
    try:
        return int(value.strip())
    except Exception:
        return None


def truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def split_blocks_into_fields(blocks: list[str], max_field_len: int = 1000) -> list[str]:
    if not blocks:
        return []

    fields: list[str] = []
    current = ""
    separator = "\n\n"

    for block in blocks:
        if len(block) > max_field_len:
            block = truncate(block, max_field_len)

        candidate = f"{current}{separator}{block}" if current else block
        if len(candidate) <= max_field_len:
            current = candidate
            continue

        if current:
            fields.append(current)
        current = block

    if current:
        fields.append(current)
    return fields
