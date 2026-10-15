from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class Problem(Exception):
    def __init__(self, status: int, code: str, detail: str):
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail


def problem_response(status: int, code: str, detail: str, errors: list | None = None) -> JSONResponse:
    body = {
        "type": "about:blank",
        "title": HTTPStatus(status).phrase,
        "status": status,
        "code": code,
        "detail": detail,
    }
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def install(app: FastAPI) -> None:
    @app.exception_handler(Problem)
    async def on_problem(_: Request, exc: Problem) -> JSONResponse:
        return problem_response(exc.status, exc.code, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def on_invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return problem_response(422, "invalid_request", "The request body, path or query is invalid.", errors)

    @app.exception_handler(StarletteHTTPException)
    async def on_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = HTTPStatus(exc.status_code).phrase.lower().replace(" ", "_")
        return problem_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def on_unhandled(_: Request, exc: Exception) -> JSONResponse:
        return problem_response(500, "internal_error", f"The server failed on this request ({type(exc).__name__}).")
