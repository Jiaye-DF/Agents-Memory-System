import logging
import re
import urllib.parse

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_clients: dict[int, aioredis.Redis] = {}

# 阻塞型命令（BRPOP 等）專用 client 池，與一般 client 分離
_blocking_clients: dict[int, aioredis.Redis] = {}

# redis-py 規則：URL query 參數優先於 from_url 的 kwargs。
# 部署端 REDIS_URL 若帶 socket_timeout < worker 的 BRPOP 阻塞秒數，
# 佇列閒置等待會被誤判為讀取逾時（Timeout reading from ...）。
# 阻塞型 client 一律剝除這些參數，再以明確 kwargs 建立。
_BLOCKING_STRIP_PARAMS = {"socket_timeout", "socket_connect_timeout"}


def _build_redis_url(db: int) -> str:
    """組指定 db 的 Redis URL；若 REDIS_URL 已設則覆寫其末段 db 索引。"""
    if settings.REDIS_URL:
        return re.sub(r"/\d+(?=\?|$)", f"/{db}", settings.REDIS_URL)
    return f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{db}"


async def init_redis() -> None:
    """初始化預設 db client（`settings.REDIS_DB`）並 ping；其餘 db 走 lazy。"""
    default_db = settings.REDIS_DB
    _clients[default_db] = aioredis.from_url(
        _build_redis_url(default_db), decode_responses=True
    )
    try:
        await _clients[default_db].ping()
        logger.info("Redis 連線成功（預設 db=%d）", default_db)
    except Exception as exc:
        # 不 raise：fallback 由後續呼叫端（如下載計數）處理
        logger.warning(
            "Redis ping 失敗，後續依賴 Redis 的功能將走 fallback：%s", exc
        )


async def close_redis() -> None:
    for pool in (_clients, _blocking_clients):
        for db, client in list(pool.items()):
            try:
                await client.aclose()
            except Exception:
                pass
            pool.pop(db, None)


def get_redis(db: int | None = None) -> aioredis.Redis:
    """取得指定 db 的 Redis client；未指定時走 `settings.REDIS_DB`。

    首次對某 db 呼叫時 lazy 建立 client；之後快取重用。
    """
    if not _clients:
        raise RuntimeError("Redis 尚未初始化（請於 lifespan 呼叫 init_redis）")

    target_db = settings.REDIS_DB if db is None else db
    if target_db not in _clients:
        _clients[target_db] = aioredis.from_url(
            _build_redis_url(target_db), decode_responses=True
        )
    return _clients[target_db]


def _build_blocking_url(db: int) -> str:
    """組阻塞型 client 用的 URL：剝除 URL 上的 socket timeout 類參數。"""
    url = _build_redis_url(db)
    parts = urllib.parse.urlsplit(url)
    if not parts.query:
        return url
    kept = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if k not in _BLOCKING_STRIP_PARAMS
    ]
    return urllib.parse.urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urllib.parse.urlencode(kept),
            parts.fragment,
        )
    )


def get_blocking_redis(db: int | None = None) -> aioredis.Redis:
    """取得阻塞型命令（BRPOP 等）專用 client。

    與 `get_redis` 的差異：socket read timeout 一律為 None（阻塞等待是常態，
    不可被環境端 REDIS_URL 的 socket_timeout 參數提前掐斷），但連線建立仍
    fail-fast、閒置連線自動健檢以利斷線自癒。一般操作請照舊用 `get_redis`。
    """
    if not _clients:
        raise RuntimeError("Redis 尚未初始化（請於 lifespan 呼叫 init_redis）")

    target_db = settings.REDIS_DB if db is None else db
    if target_db not in _blocking_clients:
        _blocking_clients[target_db] = aioredis.from_url(
            _build_blocking_url(target_db),
            decode_responses=True,
            socket_timeout=None,
            socket_connect_timeout=5,
            health_check_interval=30,
        )
    return _blocking_clients[target_db]
