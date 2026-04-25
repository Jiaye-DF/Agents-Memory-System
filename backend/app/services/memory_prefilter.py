from app.core.text_utils import EMOJI_PATTERN as _EMOJI_PATTERN
from app.models.chat_message import ChatMessage


def should_skip(message: ChatMessage, rules: dict | None) -> bool:
    """規則預篩：True 表示跳過此訊息（不進記憶）。"""
    if message is None:
        return True
    # v1.1 直接略過 tool 訊息
    if message.role == "tool":
        return True

    rules = rules or {}
    content = (message.content or "").strip()
    if not content:
        return True

    min_length = int(rules.get("min_length", 0) or 0)
    if min_length and len(content) < min_length:
        return True

    whitelist = rules.get("greeting_whitelist") or []
    if isinstance(whitelist, list):
        normalized = content.lower().strip("。！？!?.…～~ 　")
        for item in whitelist:
            if isinstance(item, str) and normalized == item.lower().strip():
                return True

    # 去除 emoji 後若空白，視為純 emoji 訊息
    without_emoji = _EMOJI_PATTERN.sub("", content).strip()
    if not without_emoji:
        return True

    return False


def truncate_for_extraction(content: str, max_tokens: int) -> str:
    """簡單 token 估算（4 char ≈ 1 token），超過則頭尾保留、中間截斷。"""
    if not content:
        return ""
    if max_tokens <= 0:
        return content
    max_chars = max_tokens * 4
    if len(content) <= max_chars:
        return content
    half = max_chars // 2
    head = content[: half - 10]
    tail = content[-(half - 10):]
    return f"{head}\n...（已截斷）...\n{tail}"
