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
