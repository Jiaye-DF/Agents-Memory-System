import base64
import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base


def encode_cursor(pid: int) -> str:
    return base64.urlsafe_b64encode(str(pid).encode()).decode()


def decode_cursor(cursor: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except (ValueError, Exception) as exc:
        raise ValueError("無效的分頁 cursor") from exc


def _encode_composite(value: object, pid: int) -> str:
    """以 (value, pid) tuple 編碼 cursor；value 允許 int / float / str / datetime / None。"""
    if isinstance(value, datetime):
        payload_value = value.isoformat()
    elif value is None or isinstance(value, (int, float, str)):
        payload_value = value
    else:
        payload_value = str(value)
    payload = json.dumps({"v": payload_value, "p": pid})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _decode_composite(cursor: str) -> tuple[object, int]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        payload = json.loads(raw)
        return payload["v"], int(payload["p"])
    except (ValueError, KeyError, Exception) as exc:
        raise ValueError("無效的分頁 cursor") from exc


@dataclass
class PaginatedResult[T]:
    items: list[T]
    next_cursor: str | None
    has_next: bool


async def paginate[T: Base](
    db: AsyncSession,
    stmt: Select[tuple[T]],
    cursor: str | None,
    limit: int = 20,
) -> PaginatedResult[T]:
    model_cls = stmt.column_descriptions[0]["entity"]

    if cursor is not None:
        pid = decode_cursor(cursor)
        stmt = stmt.where(model_cls.pid > pid)

    stmt = stmt.order_by(model_cls.pid.asc()).limit(limit + 1)

    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    has_next = len(rows) > limit
    items = rows[:limit]

    next_cursor: str | None = None
    if has_next and items:
        next_cursor = encode_cursor(items[-1].pid)

    return PaginatedResult(items=items, next_cursor=next_cursor, has_next=has_next)


async def paginate_ordered[T: Base](
    db: AsyncSession,
    stmt: Select[tuple[T]],
    order_column,
    order_desc: bool,
    cursor: str | None,
    limit: int = 20,
) -> PaginatedResult[T]:
    """依指定欄位排序的 cursor 分頁；以 (order_value, pid) 做 tie-breaker。

    - `order_desc=True`  → 主欄位 DESC、pid DESC
    - `order_desc=False` → 主欄位 ASC、pid ASC
    - cursor 以 `(order_value, pid)` 編碼，確保翻頁時不會有錯位或重疊

    呼叫端應傳入 SQLAlchemy 欄位物件（如 `Agent.favorite_count`、`Agent.created_at`），
    欄位可為空值時（如 `updated_at` 理論非空），此函式不處理 NULL 排序，
    若未來新增允許 NULL 的排序欄位需擴充此處。
    """
    model_cls = stmt.column_descriptions[0]["entity"]

    if cursor is not None:
        value, pid = _decode_composite(cursor)
        # datetime 欄位從 ISO 還原
        if hasattr(order_column.type, "python_type"):
            try:
                py_type = order_column.type.python_type
                if py_type is datetime and isinstance(value, str):
                    value = datetime.fromisoformat(value)
            except (NotImplementedError, AttributeError):
                pass
        if order_desc:
            # 取較小或相等且 pid 較小者
            stmt = stmt.where(
                or_(
                    order_column < value,
                    and_(order_column == value, model_cls.pid < pid),
                )
            )
        else:
            stmt = stmt.where(
                or_(
                    order_column > value,
                    and_(order_column == value, model_cls.pid > pid),
                )
            )

    if order_desc:
        stmt = stmt.order_by(order_column.desc(), model_cls.pid.desc())
    else:
        stmt = stmt.order_by(order_column.asc(), model_cls.pid.asc())
    stmt = stmt.limit(limit + 1)

    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    has_next = len(rows) > limit
    items = rows[:limit]

    next_cursor: str | None = None
    if has_next and items:
        last = items[-1]
        next_cursor = _encode_composite(
            getattr(last, order_column.key), last.pid
        )

    return PaginatedResult(items=items, next_cursor=next_cursor, has_next=has_next)
