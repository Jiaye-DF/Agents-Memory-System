"""文字處理共用工具（v1.3.4）。

把 emoji 偵測 / 純表情判斷的 regex 集中於此，供下列模組共用：
- ``app.services.memory_prefilter``（v1.1 既有，memory_worker 用）
- ``app.services.classifier_service``（v1.3.4 新增，chat 入口用）

兩模組生命週期不同（背景批次 vs 同步請求），但共用「純 emoji 訊息」的判斷
邏輯；抽到 core 是為了避免 classifier 直接 import memory_prefilter 內部
私有 pattern 造成耦合。
"""
from __future__ import annotations

import re

# 涵蓋常見 emoji 區段：Emoticons / Misc Symbols & Pictographs / Transport & Map
# Symbols / Supplemental Symbols and Pictographs / Symbols and Pictographs Ext-A
# 與 v1.1 memory_prefilter 既有 pattern 完全一致，避免行為偏移。
EMOJI_PATTERN: re.Pattern[str] = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F000-\U0001F2FF"
    "]+",
    flags=re.UNICODE,
)


def strip_emoji(text: str) -> str:
    """移除字串中所有 emoji，回傳剩餘字元（不 strip 空白）。"""
    if not text:
        return ""
    return EMOJI_PATTERN.sub("", text)


def is_emoji_only(text: str) -> bool:
    """判斷字串是否「去除 emoji 後全為空白」。

    空字串視為 False（語意：沒有任何 emoji，不是 emoji-only）。
    """
    if not text:
        return False
    stripped = strip_emoji(text).strip()
    return stripped == ""
