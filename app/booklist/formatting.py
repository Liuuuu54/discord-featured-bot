from typing import Optional

from app.utils.text import truncate as _truncate

def _build_book_entry_block(entry: dict, index: int, *, title_max_len: int = 60, review_max_len: Optional[int] = None) -> str:
    title = _truncate(entry['thread_title'], title_max_len)
    review = entry['review'].strip() if entry['review'] else ""
    if review and review_max_len is not None:
        review = _truncate(review, review_max_len)
    review_text = review if review else "（无评价）"
    return (
        f"🆔 ID：`{index:02}`\n"
        f"📌 标题：{title}\n"
        f"🔗 连结：{entry['thread_url']}\n"
        f"📝 评价：{review_text}"
    )

