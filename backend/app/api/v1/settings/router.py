from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.auth.schemas import TokenPayload
from app.schemas.response import ApiResponse
from app.services import system_setting_service


class PublicSettingsData(BaseModel):
    settings: dict[str, str | int | bool | list | dict]


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/public", response_model=ApiResponse[PublicSettingsData])
async def get_public_settings(
    _current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await system_setting_service.get_public_dict(db)
    return success(data={"settings": result})
