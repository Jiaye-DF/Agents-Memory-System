import base64
from dataclasses import dataclass

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base


def encode_cursor(pid: int) -> str:
    return base64.urlsafe_b64encode(str(pid).encode()).decode()


def decode_cursor(cursor: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except (ValueError, Exception) as exc:
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
