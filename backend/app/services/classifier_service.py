"""路由分類器（Routing Classifier）— v1.3.4 規則引擎實作。

決定 chat 訊息該走哪條路：``skip`` / ``cheap`` / ``expensive``。
output 直接是「動作」，不是「標籤」（對齊 docs/Arch/00-memory-system.md §4 命名澄清）。

# 演進路徑（規則 → model）：
# 1. 規則引擎（v1.3.4 本版）— 零成本、可解釋
# 2. 規則撐不住時：local DistilBERT 二分類器 / 三分類器（待定）
# 3. 量大穩定後：雲端極小 model（haiku 級判斷）
# classifier.model 欄位即為未來切換點，當前固定 "rule-based"。

# TODO(follow-up)：誤判率指標
# 訊號：同 session 連續 user 訊息語意相似度 > 0.8 或 < 5 秒內重發 → 視為「使用者重問」
# 觀察基準：route='skip' / 'cheap' 後立即被使用者重問的比率
# 達成條件：v1.3.0 metrics 累積 7+ 天資料、且 chat 量級足夠統計顯著

設計決策（對齊 tasks-v1.3.4.md「已確認決策」）：
- 規則引擎延伸自 v1.1 ``memory_prefilter`` 概念（greeting whitelist / 純 emoji /
  min_length），但**不**直接 import 該模組——共用 emoji pattern 由
  ``app.core.text_utils`` 提供。memory_prefilter 服務 memory_worker（背景批次），
  classifier_service 服務 chat 入口（同步請求），生命週期 / 設定來源不同。
- multimodal 強制路由：訊息含 ``kind=='image'`` 附件 → 直接走 expensive，
  不論 ``classifier.enabled`` 為何。
- cheap 條件保守：未命中 skip 即進 expensive；cheap 僅命中極短純問答 +
  歷史輪次少 + 無多句結構的少數情境（避免規則誤判把複雜問題丟給 cheap）。
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.text_utils import is_emoji_only
from app.services import llm_pricing, system_setting_service

logger = logging.getLogger(__name__)

RouteDecision = Literal["skip", "cheap", "expensive"]

# 預設 fallback（與 V43 seed 同步）。當 system_setting 抓不到 / 解析失敗時使用。
DEFAULT_THRESHOLDS: dict[str, object] = {
    "min_length": 3,
    "greeting_whitelist": [
        "hi",
        "hello",
        "嗨",
        "你好",
        "好",
        "好的",
        "收到",
        "謝謝",
        "ok",
        "thanks",
        "thx",
    ],
    "cheap_max_length": 60,
    "cheap_max_history_turns": 4,
    "skip_response_template_fallback": "收到。",
}

DEFAULT_SKIP_RESPONSE = "收到,繼續~"
DEFAULT_CHEAP_MODEL = "anthropic/claude-haiku-4-5"
DEFAULT_CLASSIFIER_MODEL = "rule-based"

# greeting 比對前的標點 / 空白裁切字元
_GREETING_TRIM_CHARS = "。!?！？.…～~ 　"

# cheap 路線啟發式：句末標點上限（簡單啟發式判斷單句 vs 多句結構）
_CHEAP_MAX_SENTENCE_PUNCTS = 1


def _normalize_for_greeting(text: str) -> str:
    """轉小寫 + 去頭尾常見標點 / 空白，給 greeting whitelist 比對用。"""
    return text.lower().strip(_GREETING_TRIM_CHARS).strip()


def _count_sentence_puncts(text: str) -> int:
    """計算 ``. ? ! 。 ! ?`` 數量，用於判斷是否為多句結構。"""
    count = 0
    for ch in text:
        if ch in (".", "?", "!", "。", "！", "？"):
            count += 1
    return count


def _has_image_attachment(attachments: list[dict] | None) -> bool:
    if not attachments:
        return False
    for a in attachments:
        if isinstance(a, dict) and a.get("kind") == "image":
            return True
    return False


def _decision(
    route: RouteDecision, reason: str, matched_rule: str
) -> dict[str, str]:
    return {"route": route, "reason": reason, "matched_rule": matched_rule}


async def classify(
    content: str,
    *,
    attachments: list[dict] | None,
    history_turns: int,
    db: AsyncSession,
) -> dict[str, str]:
    """分類訊息該走哪條路。

    Args:
        content: 使用者本則訊息（純文字）
        attachments: 已 load 的附件 list（dict 含 ``kind`` 欄位）
        history_turns: 該 session 已有的對話輪數（user+assistant 合計訊息數 // 2）
        db: AsyncSession，給 system_setting helper 用

    Returns:
        dict 含三欄：``route`` / ``reason`` / ``matched_rule``
        - ``route``：``"skip"`` / ``"cheap"`` / ``"expensive"``
        - ``reason``：給 metrics / debug log 用的簡述
        - ``matched_rule``：命中的規則名稱（multimodal / greeting_whitelist:hi 等）
    """
    # 1. multimodal 強制路由：永遠優先，不受 classifier.enabled 影響
    if _has_image_attachment(attachments):
        return _decision("expensive", "multimodal_force", "image_attachment")

    cleaned = (content or "").strip()

    # 2. 讀設定（含 fallback）
    config = await get_classifier_config(db)
    if not config["enabled"]:
        return _decision("expensive", "classifier_disabled", "disabled")

    thresholds = config["thresholds"]

    # 3. skip 條件
    # 順序：greeting whitelist → 純 emoji → min_length
    # 為何 whitelist 優先於 min_length：whitelist 條目（"hi" / "ok"）多半短於
    # min_length=3，需先比對命中讓 matched_rule 帶出語意化資訊；
    # 否則 task §6 驗收「matched_rule='greeting_whitelist:<word>'」無法滿足。
    whitelist = thresholds.get("greeting_whitelist") or []
    if cleaned and isinstance(whitelist, list):
        normalized = _normalize_for_greeting(cleaned)
        for item in whitelist:
            if not isinstance(item, str):
                continue
            target = item.lower().strip()
            if target and normalized == target:
                return _decision(
                    "skip",
                    f"greeting_whitelist:{target}",
                    f"greeting_whitelist:{target}",
                )

    if cleaned and is_emoji_only(cleaned):
        return _decision("skip", "emoji_only", "emoji_only")

    min_length = int(thresholds.get("min_length", 0) or 0)
    if min_length and len(cleaned) < min_length:
        return _decision("skip", "length<min_length", f"min_length:{min_length}")

    # 4. cheap 條件（保守：短訊息 + 歷史輪次少 + 非多句結構）
    cheap_max_length = int(thresholds.get("cheap_max_length", 0) or 0)
    cheap_max_history = int(thresholds.get("cheap_max_history_turns", 0) or 0)
    if (
        cheap_max_length > 0
        and len(cleaned) <= cheap_max_length
        and history_turns <= cheap_max_history
        and _count_sentence_puncts(cleaned) <= _CHEAP_MAX_SENTENCE_PUNCTS
    ):
        return _decision(
            "cheap",
            f"short_qa:len={len(cleaned)},turns={history_turns}",
            "short_qa",
        )

    # 5. 預設：expensive
    return _decision("expensive", "default_expensive", "default")


async def get_classifier_config(db: AsyncSession) -> dict[str, object]:
    """聚合讀取 classifier.* 設定，內建 fallback。

    回傳 dict 鍵：
        enabled: bool
        model: str（rule-based 或未來 model id）
        cheap_model: str
        skip_response_template: str
        thresholds: dict
    """
    try:
        enabled = await system_setting_service.get_bool(
            "classifier.enabled", True, db
        )
    except Exception as exc:
        logger.warning("classifier_service 讀 enabled 失敗，fallback True: %s", exc)
        enabled = True

    try:
        model = (
            await system_setting_service.get(
                "classifier.model", DEFAULT_CLASSIFIER_MODEL, db
            )
            or DEFAULT_CLASSIFIER_MODEL
        )
    except Exception as exc:
        logger.warning(
            "classifier_service 讀 model 失敗，fallback %s: %s",
            DEFAULT_CLASSIFIER_MODEL,
            exc,
        )
        model = DEFAULT_CLASSIFIER_MODEL

    try:
        cheap_model = (
            await system_setting_service.get(
                "classifier.cheap_model", DEFAULT_CHEAP_MODEL, db
            )
            or DEFAULT_CHEAP_MODEL
        )
    except Exception as exc:
        logger.warning(
            "classifier_service 讀 cheap_model 失敗，fallback %s: %s",
            DEFAULT_CHEAP_MODEL,
            exc,
        )
        cheap_model = DEFAULT_CHEAP_MODEL

    try:
        skip_template = (
            await system_setting_service.get(
                "classifier.skip_response_template", DEFAULT_SKIP_RESPONSE, db
            )
            or DEFAULT_SKIP_RESPONSE
        )
    except Exception as exc:
        logger.warning(
            "classifier_service 讀 skip_template 失敗，fallback default: %s", exc
        )
        skip_template = DEFAULT_SKIP_RESPONSE

    try:
        thresholds = await system_setting_service.get_json(
            "classifier.thresholds", DEFAULT_THRESHOLDS, db
        )
        if not isinstance(thresholds, dict):
            logger.warning(
                "classifier_service thresholds 非 dict，fallback 預設"
            )
            thresholds = DEFAULT_THRESHOLDS
    except Exception as exc:
        logger.warning(
            "classifier_service 讀 thresholds 失敗，fallback default: %s", exc
        )
        thresholds = DEFAULT_THRESHOLDS

    return {
        "enabled": enabled,
        "model": model,
        "cheap_model": cheap_model,
        "skip_response_template": skip_template,
        "thresholds": thresholds,
    }


def estimate_baseline_for_skip(
    content: str, expensive_model: str | None = None
) -> Decimal:
    """skip 路線 baseline 成本估算。

    對齊 docs/Arch/01-observability-and-metrics.md §5-3：
    - input_tokens = max(len(content) // 4, 0)
    - output_tokens = 200（估算）
    - 套 expensive_model 單價（None 則走 EXPENSIVE_MODEL_ID）

    粗估即可，重點是「skip 確實有省到錢」這件事被記下。
    """
    text = content or ""
    input_tokens = max(len(text) // 4, 0)
    fake_usage = {
        "input_tokens": input_tokens,
        "output_tokens": 200,
    }
    return llm_pricing.compute_baseline_cost(fake_usage, expensive_model)
