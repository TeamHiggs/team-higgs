"""Authentication routes: Google OIDC login, callback, logout, current user.

A dev-only fake login (``POST /api/auth/dev-login``) responds only when
``DEV_AUTH=1``; it is excluded from the OpenAPI schema and never enabled unless
the flag is set (PRD §6). Single-user surface, so a successful login stores the
verified email in the session -- there is no user table.
"""

from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse

from command_center.auth.oidc import OIDCError, OIDCVerifier
from command_center.config import Settings, get_settings
from command_center.errors import (
    ForbiddenError,
    NotFoundFailure,
    UnauthorizedError,
    ValidationFailure,
)
from command_center.schemas import DevLoginRequest, MessageOut, UserOut
from command_center.security import (
    Identity,
    clear_session,
    current_user,
    establish_session,
    get_oidc_verifier,
)

logger = logging.getLogger("command_center")

router = APIRouter(prefix="/api/auth", tags=["auth"])

_STATE_KEY = "oauth_state"
_POST_LOGIN_REDIRECT = "/"


@router.get("/login")
def login(
    request: Request,
    verifier: OIDCVerifier = Depends(get_oidc_verifier),
) -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    request.session[_STATE_KEY] = state
    return RedirectResponse(url=verifier.authorization_url(state), status_code=302)


@router.get("/callback")
def callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    settings: Settings = Depends(get_settings),
    verifier: OIDCVerifier = Depends(get_oidc_verifier),
) -> RedirectResponse:
    expected_state = request.session.pop(_STATE_KEY, None)
    if not expected_state or not secrets.compare_digest(expected_state, state):
        raise ValidationFailure("Invalid OAuth state")

    try:
        identity = verifier.fetch_identity(code)
    except OIDCError:
        # Do not surface provider internals to the client.
        raise UnauthorizedError("Sign-in failed") from None

    if not settings.email_allowed(identity.email):
        logger.warning("login_denied_not_allowlisted")
        raise ForbiddenError("Account not permitted")

    establish_session(request, email=identity.email, name=identity.name)
    return RedirectResponse(url=_POST_LOGIN_REDIRECT, status_code=302)


@router.post("/logout", response_model=MessageOut)
def logout(request: Request) -> MessageOut:
    clear_session(request)
    return MessageOut(detail="Signed out")


@router.post("/dev-login", include_in_schema=False, response_model=UserOut)
def dev_login(
    request: Request,
    payload: DevLoginRequest,
    settings: Settings = Depends(get_settings),
) -> UserOut:
    """Fake login for local/docker/testing. Guarded by ``DEV_AUTH=1``."""

    if not settings.dev_auth:
        raise NotFoundFailure()
    if not settings.email_allowed(payload.email):
        raise ForbiddenError("Account not permitted")
    name = payload.name or payload.email
    establish_session(request, email=payload.email, name=name)
    return UserOut(email=payload.email, name=name)


# Separate router for /api/me so it lives outside the /api/auth prefix.
me_router = APIRouter(prefix="/api", tags=["auth"])


@me_router.get("/me", response_model=UserOut)
def me(user: Identity = Depends(current_user)) -> UserOut:
    return UserOut(email=user.email, name=user.name)
