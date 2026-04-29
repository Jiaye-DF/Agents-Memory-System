from typing import Protocol

from app.core.exceptions import AppError


class _OwnedVisible(Protocol):
    owner_user_uid: object
    visibility: str


def _is_owner(entity: _OwnedVisible, user_uid: str) -> bool:
    return str(entity.owner_user_uid) == user_uid


def ensure_readable(
    entity: _OwnedVisible | None,
    user_uid: str,
    role: str,
    not_found_detail: str,
) -> None:
    """讀取權限：admin 全通；否則需為擁有者或公開資源。失敗統一回 404 以避免資源列舉。"""
    if entity is None:
        raise AppError(detail=not_found_detail, response_code=404, status_code=404)
    if role == "admin":
        return
    if _is_owner(entity, user_uid) or entity.visibility == "public":
        return
    raise AppError(detail=not_found_detail, response_code=404, status_code=404)


def ensure_modifiable(
    entity: _OwnedVisible | None,
    user_uid: str,
    role: str,
    not_found_detail: str,
    forbidden_detail: str = "權限不足",
) -> None:
    """修改權限：admin 可改；否則僅擁有者可改。資源不存在回 404，非擁有者回 403。"""
    if entity is None:
        raise AppError(detail=not_found_detail, response_code=404, status_code=404)
    if role == "admin" or _is_owner(entity, user_uid):
        return
    raise AppError(detail=forbidden_detail, response_code=403, status_code=403)


def ensure_owner(
    entity: _OwnedVisible | None,
    user_uid: str,
    not_found_detail: str,
    forbidden_detail: str,
) -> None:
    """擁有者專用動作（刪除、切換可見性等）：僅擁有者可操作，admin 亦不特權。"""
    if entity is None:
        raise AppError(detail=not_found_detail, response_code=404, status_code=404)
    if not _is_owner(entity, user_uid):
        raise AppError(detail=forbidden_detail, response_code=403, status_code=403)
