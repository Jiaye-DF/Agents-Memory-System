import asyncio
import json
import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.openrouter import embed as openrouter_embed
from app.clients.openrouter import extract_memory
from app.core.database import AsyncSessionLocal
from app.core.redis import get_redis
from app.models.chat_message import ChatMessage
from app.repositories import (
    chat_memory_repository,
    chat_message_repository,
)
from app.services import memory_prefilter, system_setting_service

logger = logging.getLogger(__name__)

QUEUE_KEY = "chat:memory:queue"
DLQ_KEY = "chat:memory:dlq"
BRPOP_TIMEOUT = 5
MAX_RETRY = 3
DEFAULT_EXTRACTOR_MODEL = "anthropic/claude-haiku-4-5"
DEFAULT_BATCH_SIZE = 5
DEFAULT_IDLE_SECONDS = 60
DEFAULT_SKIP_RULES: dict = {
    "min_length": 15,
    "greeting_whitelist": ["hi", "hello", "好", "好的", "收到", "謝謝", "ok"],
    "max_tokens": 2000,
}


async def run() -> None:
    """Memory Worker 主迴圈：消費 Redis 佇列 → 批次抽取 → embedding → 寫入 chat_memory。"""
    logger.info("memory_worker 啟動")
    buffer: dict[str, list[str]] = {}
    last_seen: dict[str, float] = {}

    while True:
        try:
            redis = get_redis()
        except RuntimeError:
            await asyncio.sleep(1)
            continue

        try:
            item = await redis.brpop(QUEUE_KEY, timeout=BRPOP_TIMEOUT)
        except asyncio.CancelledError:
            logger.info("memory_worker 收到取消訊號，結束")
            raise
        except Exception as exc:
            logger.warning("memory_worker BRPOP 失敗: %s", exc)
            await asyncio.sleep(2)
            continue

        if item is not None:
            try:
                _, raw = item
                data = json.loads(raw)
                sid = data.get("session_uid")
                mid = data.get("message_uid")
                if sid and mid:
                    buffer.setdefault(sid, []).append(mid)
                    last_seen[sid] = time.time()
            except Exception as exc:
                logger.warning("memory_worker 解析 queue item 失敗: %s", exc)

        # 檢查 buffer 是否達批次條件
        if not buffer:
            continue

        try:
            async with AsyncSessionLocal() as cfg_db:
                batch_size = await system_setting_service.get_int(
                    "memory.batch_size", DEFAULT_BATCH_SIZE, cfg_db
                )
                idle_s = await system_setting_service.get_int(
                    "memory.idle_seconds", DEFAULT_IDLE_SECONDS, cfg_db
                )
        except Exception as exc:
            logger.warning("memory_worker 讀取設定失敗，使用預設: %s", exc)
            batch_size = DEFAULT_BATCH_SIZE
            idle_s = DEFAULT_IDLE_SECONDS

        now = time.time()
        for sid in list(buffer.keys()):
            mids = buffer.get(sid, [])
            if not mids:
                continue
            is_full = len(mids) >= batch_size
            is_idle = now - last_seen.get(sid, now) >= idle_s
            if not (is_full or is_idle):
                continue
            try:
                async with AsyncSessionLocal() as db:
                    await _process_batch(sid, list(mids), db)
                    await db.commit()
            except Exception as exc:
                logger.exception("memory_worker 處理批次失敗 session=%s: %s", sid, exc)
            buffer.pop(sid, None)
            last_seen.pop(sid, None)


async def _process_batch(
    session_uid: str, message_uids: list[str], db: AsyncSession
) -> None:
    # 讀設定
    rules = await system_setting_service.get_json(
        "memory.skip_rules", DEFAULT_SKIP_RULES, db
    )
    if not isinstance(rules, dict):
        rules = DEFAULT_SKIP_RULES
    max_tokens = int(rules.get("max_tokens", 2000) or 2000)
    model = await system_setting_service.get(
        "memory.extractor_model", DEFAULT_EXTRACTOR_MODEL, db
    )
    if not model:
        model = DEFAULT_EXTRACTOR_MODEL

    # 讀訊息
    messages: list[ChatMessage] = []
    for mid in message_uids:
        m = await chat_message_repository.get_by_uid(mid, db)
        if m is not None:
            messages.append(m)
    if not messages:
        return

    kept = [m for m in messages if not memory_prefilter.should_skip(m, rules)]
    if not kept:
        logger.debug("memory_worker 全數被預篩掉 session=%s", session_uid)
        return

    # 組送給小模型的 messages
    combined_lines: list[str] = []
    for m in kept:
        text = memory_prefilter.truncate_for_extraction(m.content, max_tokens)
        combined_lines.append(f"[{m.role}] {text}")
    combined = "\n".join(combined_lines)
    combined = memory_prefilter.truncate_for_extraction(combined, max_tokens)

    llm_messages = [{"role": "user", "content": combined}]

    # 抽取 + embedding（合併重試）
    last_err: Exception | None = None
    for attempt in range(MAX_RETRY):
        try:
            extract_result = await extract_memory(llm_messages, model=model)
            embed_input = "，".join(
                list(extract_result.keywords)
                + list(extract_result.entities)
                + ([extract_result.topic] if extract_result.topic else [])
            )
            if not embed_input.strip():
                embed_input = combined[:1000]
            vector = await openrouter_embed(embed_input)
            await chat_memory_repository.create(
                {
                    "chat_session_uid": session_uid,
                    "source_chat_message_uids": [m.chat_message_uid for m in kept],
                    "keywords": list(extract_result.keywords),
                    "entities": list(extract_result.entities),
                    "topic": extract_result.topic or None,
                    "embedding": vector,
                },
                db,
            )
            logger.info(
                "memory_worker 寫入記憶 session=%s, src=%s",
                session_uid,
                len(kept),
            )
            return
        except Exception as exc:
            last_err = exc
            logger.warning(
                "memory_worker 處理失敗 session=%s attempt=%s: %s",
                session_uid,
                attempt + 1,
                exc,
            )
            await asyncio.sleep(1 + attempt)

    # 超過重試上限 → DLQ
    try:
        redis = get_redis()
        await redis.lpush(
            DLQ_KEY,
            json.dumps(
                {
                    "session_uid": session_uid,
                    "message_uids": message_uids,
                    "error": str(last_err) if last_err else "unknown",
                    "ts": time.time(),
                }
            ),
        )
        logger.error(
            "memory_worker 失敗超過上限，已推入 DLQ session=%s", session_uid
        )
    except Exception as exc:
        logger.exception("memory_worker 推入 DLQ 失敗: %s", exc)
