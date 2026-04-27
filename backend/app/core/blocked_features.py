"""df 公司版本：blocked feature 路徑 middleware。

對話 / 專案 / Skill 建議 / 訊息送出等需 LLM token 的 API 一律回 `501 Not Implemented`，
避免在 API Token 餘額未開通時被使用。原始 router / service 程式碼保留不動，待日後
解鎖只需移除 middleware 即可恢復。

擋下的路徑 prefix：

- `/api/v1/chat/`：projects / sessions / messages / memories（整個對話領域）
- `/api/v1/skill-suggestions`：list / accept / reject / detail
- `/api/v1/agents/{uid}/skill-suggestions/...`：v1.3.6 Agent 入口的 Skill 推薦

若日後解鎖，於 `app/main.py` 移除 `BlockedFeatureMiddleware` 即可，無須改動其他程式碼。
"""

from __future__ import annotations

import re

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

_NOT_IMPLEMENTED_DETAIL = "此功能尚待審核，暫無 API Token 餘額。"

# 完全比對或以「prefix + '/'」為起頭的 path 一律 block
_BLOCKED_PATH_PREFIXES: tuple[str, ...] = (
    "/api/v1/chat",
    "/api/v1/skill-suggestions",
)

# `/api/v1/agents/{uid}/skill-suggestions...` — Agent 入口的推薦
_AGENT_SKILL_SUGGESTION_RE = re.compile(
    r"^/api/v1/agents/[^/]+/skill-suggestions(?:$|/)"
)


def _is_blocked_path(path: str) -> bool:
    for prefix in _BLOCKED_PATH_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return bool(_AGENT_SKILL_SUGGESTION_RE.match(path))


def _not_implemented_response() -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={
            "success": False,
            "data": None,
            "detail": _NOT_IMPLEMENTED_DETAIL,
            "response_code": 501,
        },
    )


class BlockedFeatureMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if _is_blocked_path(request.url.path):
            return _not_implemented_response()
        return await call_next(request)
