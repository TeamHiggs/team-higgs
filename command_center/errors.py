"""Typed web errors and handlers.

Two error families reach a response:

* Web-layer errors (:class:`AppError`) -- auth/authorization/validation raised
  in the HTTP layer.
* emctl data-layer errors (:class:`emctl.errors.EmctlError` and subclasses) --
  raised by the shared repo/services layer and by ``map_db_errors`` inside
  ``emctl.db.transaction``. They are mapped to status codes here so the API and
  CLI keep one error taxonomy.

Handlers emit a small JSON ``{"detail": ...}`` body. Raw exceptions, SQL, and
connection strings never reach a response: emctl already translates DB errors to
generic messages before they surface, and the catch-all logs the type only.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from emctl.errors import (
    ConfigError,
    ConflictError,
    EmctlError,
    NotFoundError,
    ValidationError,
)

logger = logging.getLogger("command_center")


class AppError(Exception):
    """Base for web-layer errors that map to a deliberate HTTP status."""

    status_code = 500
    detail = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.detail)
        if detail is not None:
            self.detail = detail


class UnauthorizedError(AppError):
    status_code = 401
    detail = "Authentication required"


class ForbiddenError(AppError):
    status_code = 403
    detail = "Not permitted"


class NotFoundFailure(AppError):
    status_code = 404
    detail = "Not found"


class ValidationFailure(AppError):
    status_code = 400
    detail = "Invalid request"


class ServiceUnavailable(AppError):
    status_code = 503
    detail = "Service unavailable"


# emctl data-layer error -> HTTP status. ConfigError stays 500 (a
# misconfigured server, not a client fault) and its message is not surfaced.
_EMCTL_STATUS: dict[type[EmctlError], int] = {
    NotFoundError: 404,
    ValidationError: 400,
    ConflictError: 409,
    ConfigError: 500,
}


def _emctl_status(exc: EmctlError) -> int:
    for cls, code in _EMCTL_STATUS.items():
        if isinstance(exc, cls):
            return code
    return 500


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(EmctlError)
    async def _handle_emctl_error(_request: Request, exc: EmctlError) -> JSONResponse:
        status = _emctl_status(exc)
        # emctl messages are already generic (constraint name at most, never the
        # value or SQL). A 500 stays opaque.
        detail = "Internal server error" if status >= 500 else str(exc)
        return JSONResponse(status_code=status, content={"detail": detail})

    @app.exception_handler(Exception)
    async def _handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        # Log the type only; never echo the exception text (may carry SQL/PII).
        logger.exception("unhandled_error", extra={"error_type": type(exc).__name__})
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )
