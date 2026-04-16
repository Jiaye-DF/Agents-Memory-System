from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
