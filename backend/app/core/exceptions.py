import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        detail: str,
        response_code: int = 400,
        status_code: int = 400,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.detail = detail
        self.response_code = response_code
        self.status_code = status_code
        # 選用 response headers — 例如 SSO Single Logout 加強模式的 X-Recently-Logged-Out
        self.headers = headers
        super().__init__(detail)


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "detail": exc.detail,
            "response_code": exc.response_code,
        },
        headers=exc.headers,
    )


async def validation_error_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(x) for x in err["loc"])
        errors.append(f"{loc}: {err['msg']}")
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "data": None,
            "detail": "；".join(errors),
            "response_code": 422,
        },
    )


async def generic_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("未預期錯誤: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "detail": "伺服器發生錯誤，請稍後再試",
            "response_code": 500,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_error_handler)  # type: ignore[arg-type]
