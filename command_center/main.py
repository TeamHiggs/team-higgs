"""FastAPI application factory for the command-center backend."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from command_center.config import Settings, get_settings
from command_center.errors import register_error_handlers
from command_center.logging_config import configure_logging
from command_center.routers import (
    approvals,
    auth,
    backlog,
    improvement,
    notes,
    state,
    tasks,
)

# Where a Docker build would drop the compiled Vite SPA (task #28). Absent in
# local dev / CI / this backend-only task; the app then serves the JSON API
# only. One image, one deploy (PRD §3) once the SPA lands.
_DEFAULT_STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(
    settings: Settings | None = None, static_dir: Path | None = None
) -> FastAPI:
    configure_logging()
    explicit_settings = settings is not None
    settings = settings or get_settings()

    # The interactive docs and the raw schema are an info-disclosure surface in
    # production, so they are fenced behind the same flag as the dev-login: on
    # when DEV_AUTH=1, HTTP 404 otherwise. This disables only the HTTP routes;
    # FastAPI's in-process ``app.openapi()`` still works, so the published
    # contract for the SPA is generated offline via ``command_center.openapi``.
    docs_enabled = settings.dev_auth

    app = FastAPI(
        title="Command Center API",
        version="0.1.0",
        description=(
            "emctl-over-HTTP: the platform state store given an authenticated "
            "JSON API for the command-center SPA."
        ),
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie=settings.session_cookie_name,
        same_site="lax",
        https_only=settings.session_https_only,
    )

    register_error_handlers(app)

    # get_settings is a module-level dependency; when a bespoke Settings is
    # injected (tests, embedding) make every ``Depends(get_settings)`` return it.
    if explicit_settings:
        app.dependency_overrides[get_settings] = lambda: settings

    app.include_router(auth.router)
    app.include_router(auth.me_router)
    app.include_router(approvals.router)
    app.include_router(backlog.router)
    app.include_router(tasks.router)
    app.include_router(improvement.router)
    app.include_router(notes.router)
    app.include_router(state.router)

    @app.get("/healthz", tags=["ops"], include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    # Serve the built SPA last, so its catch-all can never shadow an API route
    # or /healthz. Skipped entirely when no build is present (this task).
    spa_dir = static_dir if static_dir is not None else _DEFAULT_STATIC_DIR
    index = spa_dir / "index.html"
    if index.is_file():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=spa_dir, html=True), name="spa")

    return app


def __getattr__(name: str) -> object:
    """Lazily build the ASGI app on first access.

    ``uvicorn command_center.main:app`` resolves ``app`` here (constructing it
    once, reading settings from the environment as it should in a deployment),
    while importing this module for its factory -- tests, the OpenAPI dump --
    does not require the environment to be configured.
    """
    if name == "app":
        return create_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
