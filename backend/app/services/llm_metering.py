"""LLM 呼叫單一進入點 wrapper（v1.3.0）。

**集中進入點規範**（docs/Arch/01-observability-and-metrics.md §2-3）：

> 除本檔（``app.services.llm_metering``）外，禁止其他模組直接
> ``from app.clients.openrouter import`` 任何 LLM 呼叫函式。
> 所有 service / worker 一律呼叫 ``call_llm_metered`` / ``call_llm_metered_stream``。

任何繞過 wrapper 的呼叫 = 漏記 = metrics 失真，code review 必檢。

責任：
1. 計時、記錄 input/output tokens、cache tokens
2. 同時計算 actual_cost_usd 與 baseline_cost_usd（counterfactual）
3. 失敗時仍寫一筆 error log（500 字元上限），再 raise 原例外
4. streaming 路線採 pass-through async generator，邊 yield 邊累積 usage
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

from app.clients.openrouter import client as openrouter_client
from app.core.database import AsyncSessionLocal
from app.repositories import llm_call_log_repository
from app.services import llm_pricing

logger = logging.getLogger(__name__)

# purpose 常數（避免拼字錯誤）
PURPOSE_CHAT = "chat"
PURPOSE_MEMORY_EXTRACT = "memory_extract"
PURPOSE_EMBEDDING = "embedding"
PURPOSE_IMAGE_DESCRIBE = "image_describe"
PURPOSE_SKILL_FACTORY = "skill_factory"
PURPOSE_CLASSIFIER = "classifier"  # v1.3.4 預留

# error 欄位截斷上限（決策 #8）
_ERROR_MAX_LEN = 500

# embedding 模型專用：baseline = actual（無 cheap / expensive 區別，決策 #12）
_EMBEDDING_PURPOSES = {PURPOSE_EMBEDDING}


def _truncate_error(exc_text: str | None) -> str | None:
    if not exc_text:
        return None
    return str(exc_text)[:_ERROR_MAX_LEN]


def _normalize_usage(raw: object) -> dict[str, int]:
    """OpenRouter / Anthropic usage 抽欄位，統一成 metering 用的 dict。

    回傳 dict 必含四鍵：input_tokens / output_tokens / cache_creation_tokens / cache_read_tokens。
    """
    usage: dict[str, Any] = raw if isinstance(raw, dict) else {}
    input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
    output_tokens = (
        usage.get("output_tokens") or usage.get("completion_tokens") or 0
    )
    cache_creation = usage.get("cache_creation_tokens") or 0
    cache_read = usage.get("cache_read_tokens") or 0
    try:
        return {
            "input_tokens": int(input_tokens or 0),
            "output_tokens": int(output_tokens or 0),
            "cache_creation_tokens": int(cache_creation or 0),
            "cache_read_tokens": int(cache_read or 0),
        }
    except (TypeError, ValueError):
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
        }


async def _persist_log(payload: dict) -> None:
    """獨立 AsyncSession 寫入 llm_call_log，與呼叫端 transaction 解耦。

    寫入失敗只會 log warning（repository 內已自我保護），不 raise。
    """
    try:
        async with AsyncSessionLocal() as db:
            await llm_call_log_repository.log(payload, db)
            await db.commit()
    except Exception as exc:
        logger.warning("llm_metering 持久化失敗（已忽略）: %s", exc)


def _build_payload(
    *,
    purpose: str,
    route: str | None,
    session_uid: str | None,
    user_uid: str | None,
    agent_uid: str | None,
    model: str | None,
    rag_hit_count: int | None,
    rag_max_score: float | None,
) -> dict:
    return {
        "purpose": purpose,
        "route": route,
        "session_uid": session_uid,
        "user_uid": user_uid,
        "agent_uid": agent_uid,
        "model": model,
        "rag_hit_count": rag_hit_count,
        "rag_max_score": (
            Decimal(str(rag_max_score)) if rag_max_score is not None else None
        ),
    }


def _compute_costs(
    purpose: str, model: str | None, usage: dict
) -> tuple[Decimal, Decimal]:
    """回傳 (actual_cost_usd, baseline_cost_usd)。"""
    actual = llm_pricing.compute_cost(model, usage)
    if purpose in _EMBEDDING_PURPOSES:
        # embedding 無 cheap / expensive 區別（決策 #12）
        baseline = actual
    else:
        baseline = llm_pricing.compute_baseline_cost(usage)
    return actual, baseline


async def call_llm_metered(
    *,
    purpose: str,
    route: str | None = None,
    session_uid: str | None = None,
    user_uid: str | None = None,
    agent_uid: str | None = None,
    rag_hit_count: int | None = None,
    rag_max_score: float | None = None,
    **call_kwargs: Any,
) -> Any:
    """非 streaming 場景的 metered LLM 呼叫進入點。

    依 ``purpose`` 分派到對應 OpenRouter client 函式：
    - ``memory_extract``  → ``extract_memory(messages, model)``
    - ``embedding``       → ``embed(text)``（call_kwargs 傳入 ``text``）
    - ``image_describe``  → ``describe_image(image_data_url, model)``
    - ``skill_factory``   → ``generate_skill_suggestion(memories_payload, model)``

    成功與失敗皆會寫入一筆 ``llm_call_log``。失敗時：
    - ``error`` 截斷至 500 字元
    - 仍 raise 原例外，呼叫端原本的錯誤處理不變
    """
    start = time.time()
    model = call_kwargs.get("model")

    payload = _build_payload(
        purpose=purpose,
        route=route,
        session_uid=session_uid,
        user_uid=user_uid,
        agent_uid=agent_uid,
        model=model,
        rag_hit_count=rag_hit_count,
        rag_max_score=rag_max_score,
    )

    try:
        result, usage_raw = await _dispatch_non_stream(purpose, call_kwargs)
        usage = _normalize_usage(usage_raw)
        actual_cost, baseline_cost = _compute_costs(purpose, model, usage)
        payload.update(
            {
                **usage,
                "actual_cost_usd": actual_cost,
                "baseline_cost_usd": baseline_cost,
                "latency_ms": int((time.time() - start) * 1000),
            }
        )
        await _persist_log(payload)
        return result
    except Exception as exc:
        payload.update(
            {
                "error": _truncate_error(str(exc)),
                "latency_ms": int((time.time() - start) * 1000),
            }
        )
        await _persist_log(payload)
        raise


async def _dispatch_non_stream(
    purpose: str, call_kwargs: dict
) -> tuple[Any, object]:
    """分派非 streaming 呼叫到 OpenRouter client；回 (結果, usage_raw)。

    各分支依 client 函式 signature 抽欄位；本函式為 metering 與 client 之間
    的唯一耦合點，新增 purpose 須同步改這裡。
    """
    if purpose == PURPOSE_MEMORY_EXTRACT:
        # extract_memory(messages, model) → MemoryExtractResult，本身不回 usage
        # OpenRouter API 回應的 usage 在 client 內部已被丟棄，此處 baseline / actual 將為 0
        # （v1.3.0 暫不回填，後續若需精確計費再擴 client 介面）
        result = await openrouter_client.extract_memory(
            messages=call_kwargs["messages"],
            model=call_kwargs["model"],
        )
        return result, None

    if purpose == PURPOSE_EMBEDDING:
        result = await openrouter_client.embed(text=call_kwargs["text"])
        # embed 回 list[float]，無 usage；以「估算」方式給 input_tokens
        # （len/4 估算，避免 cost 全 0；同 skip 路線估法）
        text_len = len(call_kwargs.get("text") or "")
        fake_usage = {"input_tokens": max(0, text_len // 4), "output_tokens": 0}
        return result, fake_usage

    if purpose == PURPOSE_IMAGE_DESCRIBE:
        result = await openrouter_client.describe_image(
            image_data_url=call_kwargs["image_data_url"],
            model=call_kwargs["model"],
        )
        return result, None

    if purpose == PURPOSE_SKILL_FACTORY:
        result = await openrouter_client.generate_skill_suggestion(
            memories_payload=call_kwargs["memories_payload"],
            model=call_kwargs["model"],
        )
        return result, None

    raise ValueError(f"call_llm_metered 不支援的 purpose: {purpose}")


async def call_llm_metered_stream(
    *,
    purpose: str = PURPOSE_CHAT,
    route: str | None = None,
    session_uid: str | None = None,
    user_uid: str | None = None,
    agent_uid: str | None = None,
    rag_hit_count: int | None = None,
    rag_max_score: float | None = None,
    **call_kwargs: Any,
) -> AsyncIterator[dict]:
    """streaming 場景（chat 主對話）的 metered 進入點。

    實作為 pass-through async generator：
    - 逐個 yield chunk 給呼叫端，**不**緩衝整段（前端 SSE 體驗不受影響）
    - 邊累積 usage / latency / error
    - generator 結束（正常 / 例外）時寫一筆 llm_call_log

    呼叫端使用：

    ::

        async for chunk in call_llm_metered_stream(
            purpose="chat", route="expensive",
            session_uid=..., user_uid=...,
            messages=..., model=..., temperature=..., max_tokens=...,
        ):
            ...
    """
    start = time.time()
    model = call_kwargs.get("model")

    payload = _build_payload(
        purpose=purpose,
        route=route,
        session_uid=session_uid,
        user_uid=user_uid,
        agent_uid=agent_uid,
        model=model,
        rag_hit_count=rag_hit_count,
        rag_max_score=rag_max_score,
    )

    usage_raw: dict | None = None
    err: BaseException | None = None
    try:
        async for chunk in openrouter_client.stream_chat_completion(
            messages=call_kwargs["messages"],
            model=call_kwargs["model"],
            temperature=call_kwargs.get("temperature"),
            max_tokens=call_kwargs.get("max_tokens"),
        ):
            # 攔截最後一個 chunk 的 usage
            if isinstance(chunk, dict):
                u = chunk.get("usage")
                if isinstance(u, dict):
                    usage_raw = u
            yield chunk
    except BaseException as exc:  # noqa: BLE001 - 仍要 raise，但需先寫 log
        err = exc
        raise
    finally:
        usage = _normalize_usage(usage_raw)
        actual_cost, baseline_cost = _compute_costs(purpose, model, usage)
        payload.update(
            {
                **usage,
                "actual_cost_usd": actual_cost,
                "baseline_cost_usd": baseline_cost,
                "latency_ms": int((time.time() - start) * 1000),
            }
        )
        if err is not None:
            payload["error"] = _truncate_error(str(err))
        await _persist_log(payload)


async def log_skip_call(
    *,
    session_uid: str | None,
    user_uid: str | None,
    agent_uid: str | None = None,
    user_input: str,
) -> None:
    """為 v1.3.4 classifier 預留：寫一筆 route='skip' 的 baseline log。

    v1.3.0 不會被任何 caller 呼叫，但介面先定好；對齊 docs/Arch §5-3。
    """
    baseline = llm_pricing.estimate_baseline_for_skip(user_input)
    payload: dict[str, Any] = {
        "purpose": PURPOSE_CHAT,
        "route": "skip",
        "session_uid": session_uid,
        "user_uid": user_uid,
        "agent_uid": agent_uid,
        "model": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "actual_cost_usd": Decimal("0"),
        "baseline_cost_usd": baseline,
        "latency_ms": 0,
    }
    await _persist_log(payload)
