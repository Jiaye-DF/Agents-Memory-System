from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_model import LlmModel


async def get_all_active(db: AsyncSession) -> list[LlmModel]:
    stmt = (
        select(LlmModel)
        .where(LlmModel.is_active == True, LlmModel.is_deleted == False)
        .order_by(LlmModel.vendor, LlmModel.display_name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def stmt_all() -> Select[tuple[LlmModel]]:
    return select(LlmModel).where(LlmModel.is_deleted == False)


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


async def get_default(db: AsyncSession) -> LlmModel | None:
    stmt = select(LlmModel).where(
        LlmModel.is_default == True,
        LlmModel.is_active == True,
        LlmModel.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def clear_default(db: AsyncSession, except_pid: int | None = None) -> None:
    """將所有其他模型的 is_default 設為 FALSE（在同一 transaction 切換預設時使用）"""
    stmt = update(LlmModel).where(
        LlmModel.is_default == True,
        LlmModel.is_deleted == False,
    )
    if except_pid is not None:
        stmt = stmt.where(LlmModel.pid != except_pid)
    stmt = stmt.values(is_default=False)
    await db.execute(stmt)
    await db.flush()
