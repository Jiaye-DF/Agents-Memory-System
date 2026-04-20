from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_project import ChatProject
from app.models.chat_session import ChatSession


async def get_by_uid(
    chat_project_uid: str, db: AsyncSession
) -> ChatProject | None:
    stmt = select(ChatProject).where(
        ChatProject.chat_project_uid == chat_project_uid,
        ChatProject.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def stmt_by_owner(owner_user_uid: str) -> Select[tuple[ChatProject]]:
    return select(ChatProject).where(
        ChatProject.is_deleted == False,
        ChatProject.owner_user_uid == owner_user_uid,
    )


async def count_by_owner(owner_user_uid: str, db: AsyncSession) -> int:
    stmt = select(func.count()).select_from(ChatProject).where(
        ChatProject.is_deleted == False,
        ChatProject.owner_user_uid == owner_user_uid,
    )
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def session_count_map(
    chat_project_uids: list[str], db: AsyncSession
) -> dict[str, int]:
    if not chat_project_uids:
        return {}
    stmt = (
        select(
            ChatSession.chat_project_uid,
            func.count(ChatSession.pid),
        )
        .where(
            ChatSession.is_deleted == False,
            ChatSession.chat_project_uid.in_(chat_project_uids),
        )
        .group_by(ChatSession.chat_project_uid)
    )
    rows = await db.execute(stmt)
    return {str(project_uid): int(count) for project_uid, count in rows.fetchall()}


async def create(project_data: dict, db: AsyncSession) -> ChatProject:
    project = ChatProject(**project_data)
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return project


async def update(
    project: ChatProject, update_data: dict, db: AsyncSession
) -> ChatProject:
    for key, value in update_data.items():
        setattr(project, key, value)
    await db.flush()
    await db.refresh(project)
    return project


async def soft_delete(project: ChatProject, db: AsyncSession) -> None:
    project.is_deleted = True
    await db.flush()
