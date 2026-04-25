import json
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime import to_taipei_iso
from app.core.exceptions import AppError
from app.models.system_setting import SystemSetting
from app.repositories import system_setting_repository
from app.schemas.settings.schemas import SystemSettingUpdateRequest

# TTL 快取：每個 key 獨立快取，避免每次建 Agent 都查 DB
_CACHE_TTL_SECONDS = 30.0
_cache: dict[str, tuple[float, str | int | bool | dict | list | None]] = {}

VALID_VALUE_TYPES = {"string", "integer", "boolean", "json"}


def _invalidate_cache(key: str | None = None) -> None:
    if key is None:
        _cache.clear()
    else:
        _cache.pop(key, None)


def _parse_value(value: str, value_type: str) -> str | int | bool | dict | list:
    if value_type == "integer":
        try:
            return int(value)
        except ValueError as exc:
            raise AppError(
                detail=f"value 無法解析為 integer：{value}",
                response_code=422,
                status_code=422,
            ) from exc
    if value_type == "boolean":
        lower = value.strip().lower()
        if lower in ("true", "1", "yes", "on"):
            return True
        if lower in ("false", "0", "no", "off"):
            return False
        raise AppError(
            detail=f"value 無法解析為 boolean：{value}",
            response_code=422,
            status_code=422,
        )
    if value_type == "json":
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise AppError(
                detail=f"value 無法解析為 json：{exc.msg}",
                response_code=422,
                status_code=422,
            ) from exc
    return value


def _to_dict(obj: SystemSetting) -> dict:
    return {
        "system_setting_uid": str(obj.system_setting_uid),
        "key": obj.key,
        "value": obj.value,
        "value_type": obj.value_type,
        "description": obj.description,
        "is_public": obj.is_public,
        "is_active": obj.is_active,
        "created_at": to_taipei_iso(obj.created_at),
        "updated_at": to_taipei_iso(obj.updated_at),
    }


async def get_public_dict(db: AsyncSession) -> dict:
    rows = await system_setting_repository.list_public(db)
    result: dict[str, str | int | bool | dict | list] = {}
    for row in rows:
        try:
            result[row.key] = _parse_value(row.value, row.value_type)
        except AppError:
            # 若資料庫值與型別對不上（不該發生），退回原字串避免整個端點爆炸
            result[row.key] = row.value
    return result


async def list_admin(db: AsyncSession) -> dict:
    rows = await system_setting_repository.list_all(db)
    return {"items": [_to_dict(r) for r in rows]}


async def get_setting(key: str, db: AsyncSession) -> dict:
    obj = await system_setting_repository.get_by_key(key, db)
    if obj is None:
        raise AppError(
            detail="找不到指定的系統設定", response_code=404, status_code=404
        )
    return _to_dict(obj)


async def update_setting(
    key: str, data: SystemSettingUpdateRequest, db: AsyncSession
) -> dict:
    obj = await system_setting_repository.get_by_key(key, db)
    if obj is None:
        raise AppError(
            detail="找不到指定的系統設定", response_code=404, status_code=404
        )

    update_data: dict = {}
    if data.value is not None:
        # 依現有 value_type 驗證能否解析
        _parse_value(data.value, obj.value_type)
        update_data["value"] = data.value
    if data.description is not None:
        update_data["description"] = data.description
    if data.is_public is not None:
        update_data["is_public"] = data.is_public
    if data.is_active is not None:
        update_data["is_active"] = data.is_active

    if not update_data:
        raise AppError(
            detail="未提供任何更新欄位", response_code=400, status_code=400
        )

    await system_setting_repository.update_obj(obj, update_data, db)
    _invalidate_cache(key)
    return _to_dict(obj)


async def _get_parsed_cached(
    key: str, db: AsyncSession
) -> str | int | bool | dict | list | None:
    now = time.time()
    cached = _cache.get(key)
    if cached is not None and cached[0] > now:
        return cached[1]

    obj = await system_setting_repository.get_active_by_key(key, db)
    if obj is None:
        _cache[key] = (now + _CACHE_TTL_SECONDS, None)
        return None

    try:
        parsed = _parse_value(obj.value, obj.value_type)
    except AppError:
        parsed = obj.value
    _cache[key] = (now + _CACHE_TTL_SECONDS, parsed)
    return parsed


async def get_int(key: str, default: int, db: AsyncSession) -> int:
    value = await _get_parsed_cached(key, db)
    if isinstance(value, bool):
        # bool 是 int 的子類，明確排除
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


async def get_bool(key: str, default: bool, db: AsyncSession) -> bool:
    value = await _get_parsed_cached(key, db)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower = value.strip().lower()
        if lower in ("true", "1", "yes", "on"):
            return True
        if lower in ("false", "0", "no", "off"):
            return False
    return default


async def get_float(key: str, default: float, db: AsyncSession) -> float:
    value = await _get_parsed_cached(key, db)
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


async def get(key: str, default: str | None, db: AsyncSession) -> str | None:
    """取 string 設定（其他型別會 str() 轉回）。"""
    value = await _get_parsed_cached(key, db)
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


async def get_json(
    key: str, default: dict | list | None, db: AsyncSession
) -> dict | list | None:
    value = await _get_parsed_cached(key, db)
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default
