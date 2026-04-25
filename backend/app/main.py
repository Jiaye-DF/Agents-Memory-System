import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import v1_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.redis import close_redis, init_redis
from app.workers import (
    memory_worker,
    project_memory_worker,
    skill_factory_worker,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await init_redis()
    worker_tasks: list[asyncio.Task] = []
    try:
        worker_tasks.append(asyncio.create_task(memory_worker.run()))
    except Exception as exc:
        logger.warning("memory_worker 啟動失敗: %s", exc)
    try:
        worker_tasks.append(asyncio.create_task(skill_factory_worker.run()))
    except Exception as exc:
        logger.warning("skill_factory_worker 啟動失敗: %s", exc)
    # v1.3.5：跨層聚合 worker（user_memory_worker 於 Phase 4 加入）
    try:
        worker_tasks.append(asyncio.create_task(project_memory_worker.run()))
    except Exception as exc:
        logger.warning("project_memory_worker 啟動失敗: %s", exc)
    try:
        yield
    finally:
        for task in worker_tasks:
            if not task.done():
                task.cancel()
        for task in worker_tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        await close_redis()


app = FastAPI(
    title="Agents Memory System",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(v1_router)
