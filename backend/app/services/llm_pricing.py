"""LLM 成本計算工具（v1.3.0）。

依據 model_prices.yaml 計算單筆 LLM 呼叫的：
- 實際成本（actual）
- counterfactual baseline 成本（假設全走 EXPENSIVE 模型會花的錢）
- skip 路線的 baseline 估算（粗估，給 v1.3.4 classifier 預留）

設計依據：docs/Arch/01-observability-and-metrics.md §4-2 / §5-3 / §5-4
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path
from typing import Final

import yaml

from app.core.config import settings

logger = logging.getLogger(__name__)

# 預設 expensive 模型（counterfactual baseline 計價基準）
# 由 settings.LLM_BASELINE_EXPENSIVE_MODEL 環境變數覆寫；env 未設時走此預設
EXPENSIVE_MODEL_ID: Final[str] = "anthropic/claude-sonnet-4-6"

# skip 路線估算常數（對齊 Arch §5-3）
_SKIP_OUTPUT_TOKENS: Final[int] = 200      # 預估 output tokens
_CHARS_PER_TOKEN_RATIO: Final[int] = 4     # len(text) / 4 估 input tokens

# 價格表單位：$/M tokens（百萬 tokens 美元數）
_PER_MILLION: Final[Decimal] = Decimal("1000000")

# 模組層 cache：載入一次 yaml 後重複使用，避免每次呼叫 IO
_PRICES_CACHE: dict[str, dict[str, Decimal]] | None = None
_PRICES_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent / "config" / "model_prices.yaml"
)


def _load_prices() -> dict[str, dict[str, Decimal]]:
    """讀取 model_prices.yaml，回傳 {model_id: {"input": Decimal, "output": ...}}。"""
    global _PRICES_CACHE
    if _PRICES_CACHE is not None:
        return _PRICES_CACHE

    try:
        with _PRICES_PATH.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning("model_prices.yaml 找不到（path=%s），所有成本計算將回 0", _PRICES_PATH)
        _PRICES_CACHE = {}
        return _PRICES_CACHE
    except Exception as exc:  # pragma: no cover - 落入此 branch 表示 yaml 損毀
        logger.exception("model_prices.yaml 載入失敗: %s", exc)
        _PRICES_CACHE = {}
        return _PRICES_CACHE

    parsed: dict[str, dict[str, Decimal]] = {}
    if not isinstance(raw, dict):
        logger.warning("model_prices.yaml 根節點非 dict，忽略")
        _PRICES_CACHE = {}
        return _PRICES_CACHE

    for model_id, fields in raw.items():
        if not isinstance(fields, dict):
            continue
        try:
            parsed[str(model_id)] = {
                "input": Decimal(str(fields.get("input", 0) or 0)),
                "output": Decimal(str(fields.get("output", 0) or 0)),
                "cache_read": Decimal(str(fields.get("cache_read", 0) or 0)),
                "cache_creation": Decimal(
                    str(fields.get("cache_creation", 0) or 0)
                ),
            }
        except Exception as exc:
            logger.warning(
                "model_prices.yaml 解析失敗 model=%s: %s", model_id, exc
            )
            continue

    _PRICES_CACHE = parsed
    return _PRICES_CACHE


def get_expensive_model_id() -> str:
    """讀取當前 baseline expensive 模型 id（settings 覆寫優先）。"""
    return settings.LLM_BASELINE_EXPENSIVE_MODEL or EXPENSIVE_MODEL_ID


def _to_int(v: object) -> int:
    """安全轉 int；非數值或 None 回 0。"""
    if v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def compute_cost(model: str | None, usage: dict | None) -> Decimal:
    """依 model_prices.yaml 與 usage 計算單筆呼叫實際成本（USD）。

    usage 可能來源：
    - OpenRouter chat: ``{"prompt_tokens": ..., "completion_tokens": ...,
      "cache_read_tokens": ..., "cache_creation_tokens": ...}``
    - Anthropic 風格: ``{"input_tokens": ..., "output_tokens": ...,
      "cache_read_tokens": ..., "cache_creation_tokens": ...}``

    為相容兩種 schema，本函式同時讀 prompt_tokens / input_tokens 等別名。
    模型不在 yaml 表中 → log warning 並回 ``Decimal("0")``，不 raise（不擋呼叫）。
    """
    if not model:
        return Decimal("0")
    prices = _load_prices()
    if model not in prices:
        logger.warning("compute_cost: 模型 %s 不在 model_prices.yaml，回 0", model)
        return Decimal("0")
    cfg = prices[model]
    if not isinstance(usage, dict):
        usage = {}

    input_tokens = _to_int(usage.get("input_tokens") or usage.get("prompt_tokens"))
    output_tokens = _to_int(
        usage.get("output_tokens") or usage.get("completion_tokens")
    )
    cache_read = _to_int(usage.get("cache_read_tokens"))
    cache_creation = _to_int(usage.get("cache_creation_tokens"))

    cost = (
        Decimal(input_tokens) * cfg["input"]
        + Decimal(output_tokens) * cfg["output"]
        + Decimal(cache_read) * cfg["cache_read"]
        + Decimal(cache_creation) * cfg["cache_creation"]
    ) / _PER_MILLION
    return cost


def compute_baseline_cost(
    usage: dict | None, expensive_model: str | None = None
) -> Decimal:
    """以 EXPENSIVE_MODEL_ID 重算 baseline 成本（counterfactual：沒 classifier 會花多少）。"""
    model = expensive_model or get_expensive_model_id()
    return compute_cost(model, usage)


def estimate_baseline_for_skip(user_input: str) -> Decimal:
    """skip 路線的 baseline 估算（對齊 Arch §5-3）。

    演算法：
    - input_tokens = len(user_input) / 4
    - output_tokens = 200
    - 套 EXPENSIVE_MODEL_ID 單價

    粗估即可，重點在於「skip 路線確實有省到錢」這件事被記下。
    """
    text = user_input or ""
    input_tokens = max(0, len(text) // _CHARS_PER_TOKEN_RATIO)
    fake_usage = {
        "input_tokens": input_tokens,
        "output_tokens": _SKIP_OUTPUT_TOKENS,
    }
    return compute_baseline_cost(fake_usage)


def reset_cache_for_tests() -> None:
    """測試用：清掉模組層 cache，讓下一次呼叫重新讀 yaml。"""
    global _PRICES_CACHE
    _PRICES_CACHE = None
