"""Skill 推薦器（v1.3.6 Phase 3）。

訊息送達 Agent 時，依 user_uid + 訊息向量 + suggestion 來源記憶比對，
回推薦清單給前端 SSE。

設計原則（task §3-1 / 已確認決策 #10）：
- 不呼叫 LLM 做意圖分類（避免每則訊息多一次成本）
- 三段過濾：
  1. confidence >= recommender.min_confidence（預設 0.75）
  2. 訊息向量 vs 來源記憶向量 cosine 相似度 >= cosine_threshold（預設 0.65）
  3. suggestion 來源記憶 keywords 與訊息提取 keywords 交集 >= 1（無 keyword 時略過）
- 已掛載到目標 agent 的 suggestion 自動排除
- 同 (user, agent, suggestion) 1 小時內不重複推（Redis dedup, TTL 3600）

API 入口（task §4-2）：直接列該 user 對該 agent 的 active 推薦，
不依賴訊息向量（純按 confidence + 未掛載過濾），給 Agent 詳情頁 / 對話入口用。
"""

from __future__ import annotations

import logging
import math
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.models.agentic_skill_suggestion import AgenticSkillSuggestion
from app.repositories import (
    agent_repository,
    agentic_skill_suggestion_repository,
    chat_memory_repository,
    project_memory_repository,
    user_memory_repository,
)
from app.services import system_setting_service

logger = logging.getLogger(__name__)

# 預設值（fallback）
DEFAULT_MIN_CONFIDENCE = 0.75
DEFAULT_COSINE_THRESHOLD = 0.65
DEFAULT_MAX_PER_REQUEST = 3
DEFAULT_DEDUP_TTL_SECONDS = 3600

REC_DEDUP_KEY_FMT = "skill_rec:dedup:{user_uid}:{agent_uid}:{suggestion_uid}"


# ---------- helpers ----------


def _cosine(a: list[float], b: list[float]) -> float:
    """純 Python cosine（避免引入 numpy）。長度不等或全零時回 0。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a <= 0 or norm_b <= 0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def _to_recommend_item(s: AgenticSkillSuggestion) -> dict:
    """共享 schema：給 SSE event / agent recommend API 回傳用。"""
    return {
        "uid": str(s.agentic_skill_suggestion_uid),
        "scope": s.scope,
        "name": s.name,
        "description": s.description,
        "confidence": float(s.confidence),
        "source_memory_count": len(s.source_memory_uids or []),
    }


async def _load_settings(
    db: AsyncSession,
) -> tuple[bool, float, float, int]:
    enabled = await system_setting_service.get_bool(
        "agentic.recommender.enabled", True, db
    )
    min_conf = await system_setting_service.get_float(
        "agentic.recommender.min_confidence", DEFAULT_MIN_CONFIDENCE, db
    )
    cos_thr = await system_setting_service.get_float(
        "agentic.recommender.cosine_threshold", DEFAULT_COSINE_THRESHOLD, db
    )
    max_per = await system_setting_service.get_int(
        "agentic.recommender.max_per_request", DEFAULT_MAX_PER_REQUEST, db
    )
    return enabled, min_conf, cos_thr, max_per


async def _agent_has_skill(
    agent_uid: str, skill_uid: str | None, db: AsyncSession
) -> bool:
    if not skill_uid:
        return False
    try:
        skill_uids = await agent_repository.get_skill_uids(agent_uid, db)
    except Exception as exc:
        logger.warning(
            "skill_recommender: get_skill_uids 失敗 agent=%s: %s",
            agent_uid,
            exc,
        )
        return False
    return str(skill_uid) in {str(u) for u in skill_uids}


async def _load_source_memory_keywords_and_vectors(
    suggestion: AgenticSkillSuggestion,
    db: AsyncSession,
) -> tuple[set[str], list[list[float]]]:
    """依 suggestion.scope + source_memory_uids 撈來源記憶的 keywords / 向量。

    為控制成本：每筆 suggestion 最多取前 3 筆代表向量。
    """
    keywords: set[str] = set()
    vectors: list[list[float]] = []

    src_uids = [str(u) for u in (suggestion.source_memory_uids or [])][:3]
    if not src_uids:
        return keywords, vectors

    if suggestion.scope == "session":
        memories = await chat_memory_repository.list_by_session(
            str(suggestion.scope_uid), db
        )
        target_uids = set(src_uids)
        for m in memories:
            if str(m.chat_memory_uid) in target_uids:
                for kw in (m.keywords or []):
                    keywords.add(kw)
                if m.embedding is not None:
                    vec = list(m.embedding)
                    if vec:
                        vectors.append(vec)
    elif suggestion.scope == "project":
        memories = await project_memory_repository.list_by_project(
            str(suggestion.scope_uid), db
        )
        target_uids = set(src_uids)
        for m in memories:
            if str(m.project_memory_uid) in target_uids:
                for kw in (m.keywords or []):
                    keywords.add(kw)
                if m.embedding is not None:
                    vec = list(m.embedding)
                    if vec:
                        vectors.append(vec)
    else:  # user
        memories = await user_memory_repository.list_by_user(
            str(suggestion.scope_uid), db
        )
        target_uids = set(src_uids)
        for m in memories:
            if str(m.user_memory_uid) in target_uids:
                for kw in (m.keywords or []):
                    keywords.add(kw)
                if m.embedding is not None:
                    vec = list(m.embedding)
                    if vec:
                        vectors.append(vec)

    return keywords, vectors[:3]


def _extract_simple_keywords(text: str) -> set[str]:
    """輕量 keyword 抽取：以非中文字元 / 空白為分隔，取長度 >= 2 的詞。

    避免另呼 LLM；中文 / 英文混合場景接受度有限但足夠做集合交集啟發式。
    """
    if not text:
        return set()
    # 拆英文單詞與中文連續段
    import re

    tokens: list[str] = []
    # 英文單字（含底線 / 連字號）
    for m in re.findall(r"[A-Za-z][A-Za-z0-9_\-]+", text):
        if len(m) >= 2:
            tokens.append(m.lower())
    # 中日韓字段（連續 >= 2）
    for m in re.findall(r"[一-鿿぀-ヿ]{2,}", text):
        tokens.append(m)
    return set(tokens)


# ---------- 核心 API ----------


async def recommend_for_message(
    *,
    user_uid: str,
    agent_uid: str,
    message_text: str,
    message_embedding: list[float] | None,
    db: AsyncSession,
) -> list[dict]:
    """訊息送達後即時推薦。

    若使用者沒有任何 pending suggestion → 直接回 []，跳過向量比對。
    若 message_embedding=None → 跳過 cosine 過濾，只看 keyword + confidence。
    """
    enabled, min_conf, cos_thr, max_per = await _load_settings(db)
    if not enabled:
        return []

    pending = await agentic_skill_suggestion_repository.list_pending_by_user(
        user_uid, db, min_confidence=min_conf
    )
    if not pending:
        return []

    user_kws = _extract_simple_keywords(message_text)

    candidates: list[tuple[float, AgenticSkillSuggestion]] = []
    for s in pending:
        # 已掛載到目標 agent → 排除
        if await _agent_has_skill(
            agent_uid, str(s.created_skill_uid) if s.created_skill_uid else None, db
        ):
            continue

        kws, vectors = await _load_source_memory_keywords_and_vectors(s, db)

        # cosine 過濾
        max_cos = 0.0
        if message_embedding and vectors:
            for v in vectors:
                c = _cosine(message_embedding, v)
                if c > max_cos:
                    max_cos = c
            if max_cos < cos_thr:
                continue
        elif message_embedding and not vectors:
            # 無來源向量可比 → 跳過（避免誤推）
            continue

        # keyword 交集
        if kws and user_kws:
            if not (kws & user_kws):
                continue
        # 來源記憶無 keywords 或訊息無關鍵字 → 略過此檢查（task §3-1 規定）

        candidates.append((max_cos, s))

    # 排序：cosine 高優先 → confidence 次之
    candidates.sort(key=lambda x: (x[0], float(x[1].confidence)), reverse=True)

    # dedup 過濾
    out: list[dict] = []
    for _score, s in candidates:
        if await _check_and_set_dedup(user_uid, agent_uid, s):
            out.append(_to_recommend_item(s))
        if len(out) >= max_per:
            break
    return out


async def _check_and_set_dedup(
    user_uid: str,
    agent_uid: str,
    suggestion: AgenticSkillSuggestion,
) -> bool:
    """SETNX 1h dedup：第一次回 True 並設 key，已存在回 False。

    Redis 不通時 fallback 一律允許推（以使用者體驗為先）。
    """
    try:
        redis = get_redis()
    except RuntimeError:
        return True
    key = REC_DEDUP_KEY_FMT.format(
        user_uid=user_uid,
        agent_uid=agent_uid,
        suggestion_uid=str(suggestion.agentic_skill_suggestion_uid),
    )
    try:
        ok = await redis.set(
            key, "1", ex=DEFAULT_DEDUP_TTL_SECONDS, nx=True
        )
    except Exception as exc:
        logger.warning("skill_rec dedup SETNX 失敗（fallback allow）: %s", exc)
        return True
    return bool(ok)


# ---------- agent 入口（給 GET /agents/{uid}/skill-suggestions 用）----------


async def list_recommendations_for_agent(
    *,
    user_uid: str,
    agent_uid: str,
    db: AsyncSession,
) -> list[dict]:
    """Agent 詳情頁 / 對話入口列推薦：不需訊息向量，只篩 confidence + 未掛載。

    對齊 task §4-2 決策：跳過 §3-1 第 4-6 步的訊息比對。
    本入口**不**消耗 dedup（dedup 只給訊息送達時的即時推薦用）。
    """
    enabled, min_conf, _cos_thr, _max_per = await _load_settings(db)
    if not enabled:
        return []

    pending = await agentic_skill_suggestion_repository.list_pending_by_user(
        user_uid, db, min_confidence=min_conf
    )
    out: list[dict] = []
    for s in pending:
        if await _agent_has_skill(
            agent_uid,
            str(s.created_skill_uid) if s.created_skill_uid else None,
            db,
        ):
            continue
        out.append(_to_recommend_item(s))
    return out


# ---------- SSE publish ----------


def _build_skill_recommendation_payload(items: list[dict]) -> dict:
    """SSE event payload 共用 builder。"""
    import time

    return {
        "event": "skill_recommendation",
        "items": items,
        "ts": int(time.time()),
    }


async def publish_recommendation_event(
    *,
    session_uid: str,
    items: list[dict],
) -> None:
    """publish 推薦事件到該 session channel；失敗僅 log warning。"""
    if not items:
        return
    import json

    from app.services import session_event_service

    try:
        redis = get_redis()
        await redis.publish(
            session_event_service.channel_for_session(session_uid),
            json.dumps(_build_skill_recommendation_payload(items)),
        )
    except Exception as exc:
        logger.warning(
            "skill_recommender publish 失敗 session=%s: %s",
            session_uid,
            exc,
        )


# ---------- 配合 chat_service.send_message 的非阻塞 hook ----------


async def trigger_for_user_message(
    *,
    user_uid: str,
    session_uid: str,
    agent_uid: str,
    message_text: str,
    db: AsyncSession,
) -> None:
    """訊息送達後的入口：撈 pending、inline embed、推薦、publish 到 session SSE。

    全部失敗都只 log warning，**不**阻塞 chat 主流程。
    """
    enabled, min_conf, _cos_thr, _max_per = await _load_settings(db)
    if not enabled:
        return

    # 早退：使用者沒有 pending suggestion → 不需付出 embedding 成本
    pending = await agentic_skill_suggestion_repository.list_pending_by_user(
        user_uid, db, min_confidence=min_conf
    )
    if not pending:
        return

    # 內部 import 避免循環
    from app.services import llm_metering

    message_embedding: list[float] | None = None
    try:
        cleaned = (message_text or "").strip()
        if cleaned:
            message_embedding = await llm_metering.call_llm_metered(
                purpose=llm_metering.PURPOSE_EMBEDDING,
                session_uid=session_uid,
                user_uid=user_uid,
                text=cleaned[:1000],
            )
    except Exception as exc:
        logger.warning(
            "skill_recommender inline embed 失敗 session=%s: %s",
            session_uid,
            exc,
        )
        message_embedding = None

    try:
        items = await recommend_for_message(
            user_uid=user_uid,
            agent_uid=agent_uid,
            message_text=message_text,
            message_embedding=message_embedding,
            db=db,
        )
    except Exception as exc:
        logger.warning(
            "skill_recommender recommend_for_message 失敗 session=%s: %s",
            session_uid,
            exc,
        )
        return

    if items:
        await publish_recommendation_event(session_uid=session_uid, items=items)


# ---------- Agent uid 驗證（給 API 用，避免循環 import）----------


async def ensure_agent_owned_by_user(
    agent_uid: str, user_uid: str, db: AsyncSession
) -> Any:
    """驗證 agent 屬於該 user；非擁有者一律回 None。"""
    try:
        uuid.UUID(agent_uid)
    except ValueError:
        return None
    agent = await agent_repository.get_by_uid(agent_uid, db)
    if agent is None:
        return None
    if str(agent.owner_uid) != user_uid:
        return None
    return agent
