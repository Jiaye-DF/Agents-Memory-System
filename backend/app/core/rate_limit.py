"""Redis-based rate-limit middleware（fixed-window，每 IP / 每 user）。

僅針對「需要保護的 prefix」啟用：
- `/api/v1/auth/login` / `/auth/register` / `/auth/reset-password`：擋帳號爆破
- `/api/v1/skills`（POST）/ `/api/v1/scripts`（POST）：擋上傳 abuse
- 其他端點直接放行

Key 命名：`rate:{bucket}:{identifier}:{window_start_epoch}`，TTL = window_seconds。
window_start_epoch = floor(now / window_seconds) * window_seconds。

Redis 不可用時 fail-open（記 warning，不阻斷請求）— 安全 / 可用權衡。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.redis import get_redis

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateRule:
    """一條 rate-limit 規則。

    - bucket：Redis key 命名空間（避免不同規則互相干擾）
    - max_calls / window_seconds：固定視窗內的最大次數
    - methods：套用的 HTTP method 集合
    - path_match：完整 path 等於、或以「path + '/'」起頭即命中
    """

    bucket: str
    path_match: str
    methods: frozenset[str]
    max_calls: int
    window_seconds: int


# 規則註冊表；保守上限，後續視觀察調整
_RULES: tuple[RateRule, ...] = (
    RateRule(
        bucket="auth_login",
        path_match="/api/v1/auth/login",
        methods=frozenset({"POST"}),
        max_calls=10,
        window_seconds=60,
    ),
    RateRule(
        bucket="auth_register",
        path_match="/api/v1/auth/register",
        methods=frozenset({"POST"}),
        max_calls=5,
        window_seconds=300,
    ),
    RateRule(
        bucket="auth_reset",
        path_match="/api/v1/auth/reset-password",
        methods=frozenset({"POST"}),
        max_calls=5,
        window_seconds=300,
    ),
    RateRule(
        bucket="upload_skill",
        path_match="/api/v1/skills",
        methods=frozenset({"POST"}),
        max_calls=20,
        window_seconds=300,
    ),
    RateRule(
        bucket="upload_script",
        path_match="/api/v1/scripts",
        methods=frozenset({"POST"}),
        max_calls=20,
        window_seconds=300,
    ),
)


def _client_identifier(request: Request) -> str:
    """以 X-Forwarded-For 首段或 client.host 作為 IP 識別碼。"""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",", 1)[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _match_rule(request: Request) -> RateRule | None:
    path = request.url.path
    method = request.method.upper()
    for rule in _RULES:
        if method not in rule.methods:
            continue
        if path == rule.path_match or path.startswith(rule.path_match + "/"):
            return rule
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        rule = _match_rule(request)
        if rule is None:
            return await call_next(request)

        identifier = _client_identifier(request)
        window_start = (
            int(time.time()) // rule.window_seconds * rule.window_seconds
        )
        key = f"rate:{rule.bucket}:{identifier}:{window_start}"

        try:
            redis = get_redis()
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, rule.window_seconds)
        except Exception as exc:
            # fail-open：Redis 不可用時不阻斷請求（已於下載計數等多處採此原則）
            logger.warning("rate-limit Redis 失敗，fail-open：%s", exc)
            return await call_next(request)

        if count > rule.max_calls:
            retry_after = (
                window_start + rule.window_seconds - int(time.time())
            )
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(max(retry_after, 1))},
                content={
                    "success": False,
                    "data": None,
                    "detail": "請求過於頻繁，請稍後再試",
                    "response_code": 429,
                },
            )

        return await call_next(request)
