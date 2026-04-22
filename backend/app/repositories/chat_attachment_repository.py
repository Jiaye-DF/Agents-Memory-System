from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_attachment import ChatAttachment


async def create(data: dict, db: AsyncSession) -> ChatAttachment:
    attachment = ChatAttachment(**data)
    db.add(attachment)
    await db.flush()
    await db.refresh(attachment)
    return attachment


async def get_by_uid(
    chat_attachment_uid: str, db: AsyncSession
) -> ChatAttachment | None:
    stmt = select(ChatAttachment).where(
        ChatAttachment.chat_attachment_uid == chat_attachment_uid,
        ChatAttachment.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def stmt_by_session(chat_session_uid: str) -> Select[tuple[ChatAttachment]]:
    return select(ChatAttachment).where(
        ChatAttachment.chat_session_uid == chat_session_uid,
        ChatAttachment.is_deleted == False,
    )


async def list_by_session(
    chat_session_uid: str, db: AsyncSession
) -> list[ChatAttachment]:
    result = await db.execute(stmt_by_session(chat_session_uid))
    return list(result.scalars().all())


async def list_by_uids(
    chat_attachment_uids: list[str], db: AsyncSession
) -> list[ChatAttachment]:
    """批次依 uid 查附件（給 ChatMessageResponse.attachments 填充，避免 N+1）。"""
    if not chat_attachment_uids:
        return []
    stmt = select(ChatAttachment).where(
        ChatAttachment.chat_attachment_uid.in_(chat_attachment_uids),
        ChatAttachment.is_deleted == False,
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def soft_delete(
    attachment: ChatAttachment, db: AsyncSession
) -> None:
    attachment.is_deleted = True
    await db.flush()
