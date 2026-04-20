import logging

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not settings.OPENAI_API_KEY:
            raise AppError(
                detail="OPENAI_API_KEY 未設定，無法呼叫 embedding API",
                response_code=500,
                status_code=500,
            )
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


async def embed(text: str) -> list[float]:
    """
    將輸入文字轉為 1536 維向量。失敗會拋 AppError（呼叫端自行決定重試或降級）。
    """
    cleaned = (text or "").strip()
    if not cleaned:
        raise AppError(
            detail="embedding 輸入為空", response_code=400, status_code=400
        )
    try:
        client = _get_client()
        resp = await client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=cleaned,
        )
    except AppError:
        raise
    except Exception as exc:
        logger.warning("OpenAI embedding 失敗: %s", exc)
        raise AppError(
            detail="embedding 呼叫失敗",
            response_code=502,
            status_code=502,
        ) from exc

    if not resp.data:
        raise AppError(
            detail="embedding 回應為空", response_code=502, status_code=502
        )
    vector = resp.data[0].embedding
    return list(vector)
