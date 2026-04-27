"""結構化 JSON log 設定 + request id middleware。

- `setup_logging()`：在 lifespan 啟動前呼叫，覆寫 root logger handler 為 JSON formatter
- `RequestContextMiddleware`：每個 request 注入 `request_id`（讀 X-Request-ID 或自產 uuid4），
  寫入 contextvars 供 log filter 取用，並回寫 response header；同時記錄 access log（method / path / status / 毫秒）
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
import uuid
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

_request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
_user_uid_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "user_uid", default=None
)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def set_user_uid(user_uid: str | None) -> None:
    """auth 依賴解析後呼叫，讓後續 log 帶上 user_uid。"""
    _user_uid_ctx.set(user_uid)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = _request_id_ctx.get()
        if rid:
            payload["request_id"] = rid
        uid = _user_uid_ctx.get()
        if uid:
            payload["user_uid"] = uid
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # 額外 key（呼叫端 logger.info("...", extra={"key": val})）
        for key, value in record.__dict__.items():
            if key in (
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "taskName",
            ):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = str(value)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    """重設 root logger handler 為單一 JSON stdout handler。

    Uvicorn 會在 import 時自行建立 access logger / error logger；本函式只覆寫 root，
    讓應用程式碼的 logger 走 JSON 輸出。Uvicorn 預設 log（access）保留原樣。
    """
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    # 移除既有 handler 避免雙寫
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        rid_token = _request_id_ctx.set(rid)
        uid_token = _user_uid_ctx.set(None)
        start = time.perf_counter()
        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logging.getLogger("app.access").info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status_code,
                    "duration_ms": duration_ms,
                },
            )
            _request_id_ctx.reset(rid_token)
            _user_uid_ctx.reset(uid_token)
