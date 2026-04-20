import logging
import time

import httpx

from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
CACHE_TTL_SECONDS = 60 * 60

_cache: dict = {"ids": None, "expires_at": 0.0}


async def _fetch_model_ids() -> set[str]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(OPENROUTER_MODELS_URL)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("OpenRouter 模型清單取得失敗: %s", exc)
        raise AppError(
            detail="無法連線至 OpenRouter 驗證模型，請稍後再試",
            response_code=503,
            status_code=503,
        )

    data = payload.get("data") or []
    return {item["id"].lower() for item in data if isinstance(item.get("id"), str)}


async def get_valid_model_ids() -> set[str]:
    now = time.time()
    cached_ids = _cache.get("ids")
    if cached_ids is not None and now < _cache["expires_at"]:
        return cached_ids

    ids = await _fetch_model_ids()
    _cache["ids"] = ids
    _cache["expires_at"] = now + CACHE_TTL_SECONDS
    return ids


async def verify_model_id(model_id: str) -> None:
    ids = await get_valid_model_ids()
    if model_id.lower() not in ids:
        raise AppError(
            detail=f"OpenRouter 不存在此模型：{model_id}",
            response_code=400,
            status_code=400,
        )
