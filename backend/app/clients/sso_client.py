"""DF-SSO 中央伺服器 HTTP client。

對應 DF-SSO INTEGRATION.md：
- POST /api/auth/sso/exchange  → 用 code 換 SSO JWT
- GET  /api/auth/me             → 用 SSO JWT 拿 user 資訊（中央 Redis 即時驗證）
- POST /api/auth/logout         → 通知中央刪 Redis session（兩層 Session 模型）

固定 timeout（8s）+ cache: no-store 對齊 spec。
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SSO_TIMEOUT = httpx.Timeout(8.0)


class SsoClientError(Exception):
    """SSO 中央回傳非 2xx 或網路錯誤。"""

    def __init__(self, code: str, status: int = 0, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status
        self.detail = detail


def _ensure_configured() -> None:
    if not settings.SSO_URL:
        raise SsoClientError("sso_not_configured", detail="SSO_URL 未設定")
    if not settings.SSO_APP_ID or not settings.SSO_APP_SECRET:
        raise SsoClientError(
            "sso_not_configured", detail="SSO_APP_ID / SSO_APP_SECRET 未設定"
        )


async def exchange_code(code: str) -> dict:
    """code → SSO JWT。回傳 `{"token": "..."}`（依中央實作可能含其他欄位）。"""
    _ensure_configured()
    url = f"{settings.SSO_URL}/api/auth/sso/exchange"
    payload = {
        "code": code,
        "client_id": settings.SSO_APP_ID,
        "client_secret": settings.SSO_APP_SECRET,
    }
    async with httpx.AsyncClient(timeout=SSO_TIMEOUT) as client:
        try:
            resp = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            logger.warning("SSO exchange 連線失敗：%s", exc)
            raise SsoClientError("sso_unreachable", detail=str(exc)) from exc

    if resp.status_code != 200:
        raise SsoClientError(
            "exchange_failed", status=resp.status_code, detail=resp.text[:200]
        )
    data = resp.json()
    token = data.get("token")
    if not isinstance(token, str) or not token:
        raise SsoClientError("exchange_failed", detail="response missing token")
    return data


async def fetch_user(sso_token: str) -> dict:
    """以 SSO JWT 向中央 /api/auth/me 取得 user 資訊。

    回傳 user dict（含 userId / email / name / erpData / loginAt）。
    """
    _ensure_configured()
    url = f"{settings.SSO_URL}/api/auth/me"
    async with httpx.AsyncClient(timeout=SSO_TIMEOUT) as client:
        try:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {sso_token}"},
            )
        except httpx.HTTPError as exc:
            logger.warning("SSO /me 連線失敗：%s", exc)
            raise SsoClientError("sso_unreachable", detail=str(exc)) from exc

    if resp.status_code == 401:
        raise SsoClientError("session_expired", status=401)
    if resp.status_code != 200:
        raise SsoClientError(
            "me_failed", status=resp.status_code, detail=resp.text[:200]
        )
    data = resp.json()
    user = data.get("user")
    if not isinstance(user, dict):
        raise SsoClientError("me_failed", detail="response missing user")
    return user


async def central_logout(sso_token: str, redirect: str) -> str:
    """通知中央刪 Redis session；回傳中央驗證過的最終 redirect URL。"""
    _ensure_configured()
    url = f"{settings.SSO_URL}/api/auth/logout"
    async with httpx.AsyncClient(timeout=SSO_TIMEOUT) as client:
        try:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {sso_token}"},
                json={"redirect": redirect},
            )
        except httpx.HTTPError as exc:
            logger.warning("SSO logout 連線失敗：%s", exc)
            return redirect

    if resp.status_code != 200:
        # 中央不可達也要繼續清本地，落地 fallback
        return redirect
    try:
        data = resp.json()
    except Exception:
        return redirect
    final_redirect = data.get("redirect")
    return final_redirect if isinstance(final_redirect, str) else redirect
