from fastapi.responses import JSONResponse


def success(data: dict | None = None, response_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": data,
            "detail": None,
            "response_code": response_code,
        },
    )


def failure(
    detail: str,
    response_code: int = 400,
    status_code: int = 400,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "detail": detail,
            "response_code": response_code,
        },
    )
