"""三層 RAG 服務（v1.3.5）。

責任：
- session 層 retrieval（v1.1 既有；保留為 thin wrapper）
- project / user 層 retrieval（v1.3.5 新增）
- RRF 融合（純算術，無 IO）
- 對外提供 `retrieve_three_layer`（chat_service 取記憶呼叫點）
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_memory import ChatMemory
from app.models.project_memory import ProjectMemory
from app.models.user_memory import UserMemory
from app.repositories import (
    chat_memory_repository,
    project_memory_repository,
    user_memory_repository,
)
from app.schemas.chat.three_layer_memory_schemas import FusedMemoryItem
from app.services import llm_metering, system_setting_service

logger = logging.getLogger(__name__)

# v1.1 預設值（保留向後相容）
DEFAULT_TOP_K = 5
DEFAULT_MIN_SCORE = 0.7

# 三層預設值（與 V46 seed 對齊）
DEFAULT_SESSION_TOP_K = 10
DEFAULT_SESSION_MIN_SCORE = 0.7
DEFAULT_PROJECT_TOP_K = 5
DEFAULT_PROJECT_MIN_SCORE = 0.65
DEFAULT_USER_TOP_K = 5
DEFAULT_USER_MIN_SCORE = 0.6
DEFAULT_FUSION_K = 60
DEFAULT_FINAL_TOP_K = 8


# ---------- v1.1：session 層單層檢索（保留為 thin wrapper） ----------


async def retrieve(
    chat_session_uid: str, query_text: str, db: AsyncSession
) -> list[ChatMemory]:
    """v1.1 session-only 檢索；v1.3.5 起標 deprecated，新呼叫點改 `retrieve_three_layer`。

    保留簽名給尚未升級的呼叫點；內部仍走單層 cosine。
    """
    try:
        enabled = await system_setting_service.get_bool("rag.enabled", True, db)
        if not enabled:
            return []
        # v1.1 鍵名沿用，無新 key 時 fallback 預設
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
        vector = await llm_metering.call_llm_metered(
            purpose=llm_metering.PURPOSE_EMBEDDING,
            session_uid=chat_session_uid,
            text=cleaned[:4000],
        )
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


# ---------- v1.3.5：RRF 融合（純算術，無 IO） ----------


def rrf_fuse(
    layers: dict[str, list[tuple[object, float]]],
    k: int = 60,
    final_top_k: int = 8,
) -> list[FusedMemoryItem]:
    """Reciprocal Rank Fusion：跨層融合排名（不混分數）。

    參數：
    - layers：`{"session": [(mem, score), ...], "project": [...], "user": [...]}`，
      每層內部已依分數降序（呼叫端責任）。
    - k：RRF 常數（Elasticsearch 慣例 60）。
    - final_top_k：最終回傳上限。

    公式（propose §3-2）：每筆 `score = Σ 1/(k + rank)`；rank 從 1 起算。
    本實作中同一筆 memory 不會跨層出現（不同 scope 的 UID 不衝突），
    所以單筆只在自己那層算一次，等於 `1/(k + rank_in_layer)`。

    回傳依 RRF 分數降序，截 final_top_k。
    """
    fused: list[FusedMemoryItem] = []
    for scope, items in (layers or {}).items():
        if not items:
            continue
        if scope not in ("session", "project", "user"):
            # 防呆：未知 scope 略過
            continue
        for rank_idx, (mem, _orig_score) in enumerate(items, start=1):
            rrf_score = 1.0 / (k + rank_idx)
            uid = _extract_memory_uid(mem, scope)
            if uid is None:
                continue
            fused.append(
                FusedMemoryItem(
                    scope=scope,  # type: ignore[arg-type]
                    memory_uid=uid,
                    topic=getattr(mem, "topic", None),
                    keywords=list(getattr(mem, "keywords", []) or []),
                    entities=list(getattr(mem, "entities", []) or []),
                    rrf_score=rrf_score,
                    source_rank=rank_idx,
                )
            )

    fused.sort(key=lambda x: x.rrf_score, reverse=True)
    return fused[:final_top_k]


def _extract_memory_uid(mem: object, scope: str) -> str | None:
    """從不同 scope 的 ORM 物件抽 UID 字串。"""
    if scope == "session":
        uid = getattr(mem, "chat_memory_uid", None)
    elif scope == "project":
        uid = getattr(mem, "project_memory_uid", None)
    elif scope == "user":
        uid = getattr(mem, "user_memory_uid", None)
    else:
        return None
    return str(uid) if uid is not None else None


# ---------- v1.3.5：三層融合 retrieval ----------


async def retrieve_three_layer(
    chat_session_uid: str,
    chat_project_uid: str | None,
    owner_user_uid: str,
    query_text: str,
    db: AsyncSession,
) -> dict[str, object]:
    """三層 RAG 融合：embedding 一次 → 並行三層 search → RRF 融合。

    回傳 dict（避免 Pydantic 物件對舊呼叫點造成負擔）：
        {
            "session": [(ChatMemory, score), ...],
            "project": [(ProjectMemory, score), ...],
            "user":    [(UserMemory, score), ...],
            "fused":   [FusedMemoryItem, ...],
        }

    任一層失敗 → log warning + 該層回空（其他層仍融合）。
    """
    empty: dict[str, object] = {
        "session": [],
        "project": [],
        "user": [],
        "fused": [],
    }

    try:
        enabled = await system_setting_service.get_bool("rag.enabled", True, db)
        if not enabled:
            return empty
        session_top_k = await system_setting_service.get_int(
            "rag.session.top_k", DEFAULT_SESSION_TOP_K, db
        )
        session_min_score = await system_setting_service.get_float(
            "rag.session.min_score", DEFAULT_SESSION_MIN_SCORE, db
        )
        project_top_k = await system_setting_service.get_int(
            "rag.project.top_k", DEFAULT_PROJECT_TOP_K, db
        )
        project_min_score = await system_setting_service.get_float(
            "rag.project.min_score", DEFAULT_PROJECT_MIN_SCORE, db
        )
        user_top_k = await system_setting_service.get_int(
            "rag.user.top_k", DEFAULT_USER_TOP_K, db
        )
        user_min_score = await system_setting_service.get_float(
            "rag.user.min_score", DEFAULT_USER_MIN_SCORE, db
        )
        fusion_k = await system_setting_service.get_int(
            "rag.fusion.k", DEFAULT_FUSION_K, db
        )
        final_top_k = await system_setting_service.get_int(
            "rag.fusion.final_top_k", DEFAULT_FINAL_TOP_K, db
        )
    except Exception as exc:
        logger.warning("rag_service 讀取三層設定失敗: %s", exc)
        return empty

    cleaned = (query_text or "").strip()
    if not cleaned:
        return empty

    try:
        vector = await llm_metering.call_llm_metered(
            purpose=llm_metering.PURPOSE_EMBEDDING,
            session_uid=chat_session_uid,
            user_uid=owner_user_uid,
            text=cleaned[:4000],
        )
    except Exception as exc:
        logger.warning("rag_service 三層 embedding 失敗，略過: %s", exc)
        return empty

    # 三層並行檢索（任一失敗以空集合代替，不影響其他層）
    session_task = asyncio.create_task(
        _safe_session_search(
            chat_session_uid, vector, session_top_k, session_min_score, db
        )
    )
    if chat_project_uid:
        project_task = asyncio.create_task(
            _safe_project_search(
                chat_project_uid, vector, project_top_k, project_min_score, db
            )
        )
    else:
        project_task = None
    user_task = asyncio.create_task(
        _safe_user_search(
            owner_user_uid, vector, user_top_k, user_min_score, db
        )
    )

    session_rows: list[tuple[ChatMemory, float]] = await session_task
    project_rows: list[tuple[ProjectMemory, float]] = (
        await project_task if project_task is not None else []
    )
    user_rows: list[tuple[UserMemory, float]] = await user_task

    fused = rrf_fuse(
        {
            "session": session_rows,
            "project": project_rows,
            "user": user_rows,
        },
        k=fusion_k,
        final_top_k=final_top_k,
    )

    logger.info(
        "rag_three_layer session=%s project=%s user=%s "
        "hits=session:%d/project:%d/user:%d fused=%d",
        chat_session_uid,
        chat_project_uid,
        owner_user_uid,
        len(session_rows),
        len(project_rows),
        len(user_rows),
        len(fused),
    )

    return {
        "session": session_rows,
        "project": project_rows,
        "user": user_rows,
        "fused": fused,
    }


async def _safe_session_search(
    chat_session_uid: str,
    vector: list[float],
    top_k: int,
    min_score: float,
    db: AsyncSession,
) -> list[tuple[ChatMemory, float]]:
    try:
        return await chat_memory_repository.search_similar(
            chat_session_uid, vector, top_k, min_score, db
        )
    except Exception as exc:
        logger.warning("rag_three_layer session 檢索失敗: %s", exc)
        return []


async def _safe_project_search(
    chat_project_uid: str,
    vector: list[float],
    top_k: int,
    min_score: float,
    db: AsyncSession,
) -> list[tuple[ProjectMemory, float]]:
    try:
        return await project_memory_repository.search_similar(
            chat_project_uid, vector, top_k, min_score, db
        )
    except Exception as exc:
        logger.warning("rag_three_layer project 檢索失敗: %s", exc)
        return []


async def _safe_user_search(
    owner_user_uid: str,
    vector: list[float],
    top_k: int,
    min_score: float,
    db: AsyncSession,
) -> list[tuple[UserMemory, float]]:
    try:
        return await user_memory_repository.search_similar(
            owner_user_uid, vector, top_k, min_score, db
        )
    except Exception as exc:
        logger.warning("rag_three_layer user 檢索失敗: %s", exc)
        return []
