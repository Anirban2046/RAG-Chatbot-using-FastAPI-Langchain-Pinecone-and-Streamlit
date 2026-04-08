from fastapi import Request
from fastapi.responses import JSONResponse
from logger import logger

INTERNAL_ERROR_MESSAGE = "Internal server error"


def internal_server_error_response() -> JSONResponse:
    return JSONResponse(status_code=500, content={"error": INTERNAL_ERROR_MESSAGE})


async def catch_exception_middleware(request:Request,call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.exception("UNHANDLED EXCEPTION on %s", request.url.path)
        return internal_server_error_response()
