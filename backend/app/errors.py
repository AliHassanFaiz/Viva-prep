from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def _body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api(_: Request, exc: APIError):
        return JSONResponse(status_code=exc.status, content=_body(exc.code, exc.message))

    @app.exception_handler(HTTPException)
    async def _http(_: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content=_body("http_error", str(exc.detail)))

    @app.exception_handler(RequestValidationError)
    async def _val(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
        return JSONResponse(status_code=422, content=_body("validation_error", f"{loc}: {first.get('msg', 'invalid request')}"))

    @app.exception_handler(Exception)
    async def _any(_: Request, exc: Exception):
        from .logging_utils import logger
        logger.error('{"stage":"unhandled","error":"%s"}', type(exc).__name__)
        return JSONResponse(status_code=500, content=_body("internal_error", "Something went wrong on our side."))
