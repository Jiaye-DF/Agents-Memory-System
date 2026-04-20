from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage


async def get_by_uid(
    chat_message_uid: str, db: AsyncSession
) -> ChatMessage | None:
    stmt = select(ChatMessage).where(
        ChatMessage.chat_message_uid == chat_message_uid,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def stmt_by_session(chat_session_uid: str) -> Select[tuple[ChatMessage]]:
    return select(ChatMessage).where(
        ChatMessage.chat_session_uid == chat_session_uid,
    )


async def get_last_n(
    chat_session_uid: str, n: int, db: AsyncSession
) -> list[ChatMessage]:
    """取得 session 最近 N 則訊息（時序正序返回，用於組 prompt）。"""
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.chat_session_uid == chat_session_uid)
        .order_by(ChatMessage.pid.desc())
        .limit(n)
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    rows.reverse()
    return rows


async def sum_tokens_cost(
    chat_session_uid: str, db: AsyncSession
) -> dict:
    stmt = select(
        func.coalesce(func.sum(ChatMessage.token_in), 0),
        func.coalesce(func.sum(ChatMessage.token_out), 0),
        func.coalesce(func.sum(ChatMessage.cost_usd), 0),
    ).where(ChatMessage.chat_session_uid == chat_session_uid)
    result = await db.execute(stmt)
    token_in, token_out, cost_usd = result.one()
    return {
        "token_in": int(token_in or 0),
        "token_out": int(token_out or 0),
        "cost_usd": float(cost_usd or Decimal("0")),
    }


async def count_by_session(
    chat_session_uid: str, db: AsyncSession
) -> int:
    stmt = select(func.count()).select_from(ChatMessage).where(
        ChatMessage.chat_session_uid == chat_session_uid,
    )
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def create(message_data: dict, db: AsyncSession) -> ChatMessage:
    message = ChatMessage(**message_data)
    db.add(message)
    await db.flush()
    await db.refresh(message)
    return message
