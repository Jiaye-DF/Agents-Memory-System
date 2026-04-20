import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients import openai_embedding
from app.models.chat_memory import ChatMemory
from app.repositories import chat_memory_repository
from app.services import system_setting_service

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 5
DEFAULT_MIN_SCORE = 0.7


async def retrieve(
    chat_session_uid: str, query_text: str, db: AsyncSession
) -> list[ChatMemory]:
    """
    依設定從 chat_memory 檢索與 query 相似的記憶。
    - rag.enabled=False 直接回空
    - embedding / 檢索失敗 log + 回空（不中斷對話）
    """
    try:
        enabled = await system_setting_service.get_bool("rag.enabled", True, db)
        if not enabled:
            return []
        top_k = await system_setting_service.get_int(
            "rag.top_k", DEFAULT_TOP_K, db
        )
        min_score = await system_setting_service.get_float(
            "rag.min_score", DEFAULT_MIN_SCORE, db
        )
    except Exception as exc:
        logger.warning("rag_service 讀取設定失敗: %s", exc)
        return []

    cleaned = (query_text or "").strip()
    if not cleaned:
        return []

    try:
        vector = await openai_embedding.embed(cleaned[:4000])
    except Exception as exc:
        logger.warning("rag_service embedding 失敗，略過注入: %s", exc)
        return []

    try:
        rows = await chat_memory_repository.search_similar(
            chat_session_uid, vector, top_k, min_score, db
        )
    except Exception as exc:
        logger.warning("rag_service 檢索失敗: %s", exc)
        return []

    return [mem for mem, _score in rows]
