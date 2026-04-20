from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_model import LlmModel


async def get_all_active(db: AsyncSession) -> list[LlmModel]:
    stmt = (
        select(LlmModel)
        .where(LlmModel.is_active == True, LlmModel.is_deleted == False)
        .order_by(LlmModel.provider, LlmModel.display_name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_all(
    cursor: int | None, limit: int, db: AsyncSession
) -> list[LlmModel]:
    stmt = select(LlmModel).where(LlmModel.is_deleted == False)
    if cursor is not None:
        stmt = stmt.where(LlmModel.pid > cursor)
    stmt = stmt.order_by(LlmModel.pid.asc()).limit(limit + 1)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_by_uid(llm_model_uid: str, db: AsyncSession) -> LlmModel | None:
    stmt = select(LlmModel).where(
        LlmModel.llm_model_uid == llm_model_uid,
        LlmModel.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_model_id(model_id: str, db: AsyncSession) -> LlmModel | None:
    stmt = select(LlmModel).where(
        LlmModel.model_id == model_id,
        LlmModel.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create(data: dict, db: AsyncSession) -> LlmModel:
    model = LlmModel(**data)
    db.add(model)
    await db.flush()
    await db.refresh(model)
    return model


async def update(
    model: LlmModel, update_data: dict, db: AsyncSession
) -> LlmModel:
    for key, value in update_data.items():
        setattr(model, key, value)
    await db.flush()
    await db.refresh(model)
    return model


async def soft_delete(model: LlmModel, db: AsyncSession) -> None:
    model.is_deleted = True
    await db.flush()
