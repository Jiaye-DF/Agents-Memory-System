import time

from app.clients.openrouter import fetch_model_ids
from app.core.exceptions import AppError

CACHE_TTL_SECONDS = 60 * 60

_cache: dict[str, object] = {"ids": None, "expires_at": 0.0}


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


async def verify_model_id(model_id: str) -> None:
    ids = await get_valid_model_ids()
    if model_id.lower() not in ids:
        raise AppError(
            detail=f"OpenRouter 不存在此模型：{model_id}",
            response_code=400,
            status_code=400,
        )
