import time

from app.clients.openrouter import fetch_model_ids, fetch_models_catalog
from app.core.exceptions import AppError

CACHE_TTL_SECONDS = 60 * 60

_cache: dict[str, object] = {"ids": None, "expires_at": 0.0}
_catalog_cache: dict[str, object] = {"items": None, "expires_at": 0.0}


async def get_valid_model_ids() -> set[str]:
    now = time.time()
    cached_ids = _cache.get("ids")
    expires_at = _cache.get("expires_at") or 0.0
    if cached_ids is not None and now < float(expires_at):  # type: ignore[arg-type]
        return cached_ids  # type: ignore[return-value]

    ids = await fetch_model_ids()
    _cache["ids"] = ids
    _cache["expires_at"] = now + CACHE_TTL_SECONDS
    return ids


async def list_openrouter_models() -> list[dict]:
    """回傳 OpenRouter 模型清單（id / name / context_length），1 小時 cache。

    供 admin 新增模型 Combobox 使用，避免每次開窗都重新拉清單。
    """
    now = time.time()
    cached_items = _catalog_cache.get("items")
    expires_at = _catalog_cache.get("expires_at") or 0.0
    if cached_items is not None and now < float(expires_at):  # type: ignore[arg-type]
        return cached_items  # type: ignore[return-value]

    items = await fetch_models_catalog()
    _catalog_cache["items"] = items
    _catalog_cache["expires_at"] = now + CACHE_TTL_SECONDS
    return items


async def verify_model_id(model_id: str) -> None:
    ids = await get_valid_model_ids()
    if model_id.lower() not in ids:
        raise AppError(
            detail=f"OpenRouter 不存在此模型：{model_id}",
            response_code=400,
            status_code=400,
        )
