from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill


async def get_by_uid(skill_uid: str, db: AsyncSession) -> Skill | None:
    stmt = select(Skill).where(
        Skill.skill_uid == skill_uid,
        Skill.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def stmt_visible_to_user(owner_uid: str) -> Select[tuple[Skill]]:
    return select(Skill).where(
        Skill.is_deleted == False,
        or_(
            Skill.owner_uid == owner_uid,
            Skill.visibility == "public",
        ),
    )


async def create(skill_data: dict, db: AsyncSession) -> Skill:
    skill = Skill(**skill_data)
    db.add(skill)
    await db.flush()
    await db.refresh(skill)
    return skill


async def update(skill: Skill, update_data: dict, db: AsyncSession) -> Skill:
    for key, value in update_data.items():
        setattr(skill, key, value)
    await db.flush()
    await db.refresh(skill)
    return skill


async def soft_delete(skill: Skill, db: AsyncSession) -> None:
    skill.is_deleted = True
    await db.flush()
