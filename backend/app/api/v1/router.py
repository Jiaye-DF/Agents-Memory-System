from fastapi import APIRouter

from app.api.v1.admin.router import router as admin_router
from app.api.v1.agent_languages.router import router as agent_languages_router
from app.api.v1.agent_templates.router import router as agent_templates_router
from app.api.v1.agents.router import router as agents_router
from app.api.v1.auth.router import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.models.router import router as models_router
from app.api.v1.settings.router import router as settings_router
from app.api.v1.skills.router import router as skills_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(health_router, tags=["health"])
v1_router.include_router(auth_router)
v1_router.include_router(admin_router)
v1_router.include_router(agent_languages_router)
v1_router.include_router(agent_templates_router)
v1_router.include_router(agents_router)
v1_router.include_router(settings_router)
v1_router.include_router(skills_router)
v1_router.include_router(models_router)
