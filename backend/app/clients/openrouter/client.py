import logging

import httpx

from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


async def fetch_model_ids() -> set[str]:
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
        ) from exc

    data = payload.get("data") or []
    return {
        item["id"].lower()
        for item in data
        if isinstance(item.get("id"), str)
    }
