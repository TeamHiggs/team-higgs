"""Session helpers and the authenticated-user dependency.

Single-user surface (Tyler only, decision #17), so there is no ``users`` table:
identity is not auditable domain state (stack-backend.md, append-only boundary).
The session is a Starlette signed, httpOnly cookie (``SessionMiddleware``)
carrying the verified email. ``current_user`` resolves it and -- critically --
re-checks the allow-list on every request, so revoking an address in
``ALLOWED_EMAILS`` invalidates any live session immediately.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request

from command_center.auth.oidc import GoogleOIDCVerifier, OIDCVerifier
from command_center.config import Settings, get_settings
from command_center.errors import UnauthorizedError

_SESSION_EMAIL_KEY = "email"
_SESSION_NAME_KEY = "name"


@dataclass(frozen=True)
class Identity:
    """The authenticated principal for the current request."""

    email: str
    name: str


def establish_session(request: Request, *, email: str, name: str) -> None:
    request.session[_SESSION_EMAIL_KEY] = email
    request.session[_SESSION_NAME_KEY] = name


def clear_session(request: Request) -> None:
    request.session.clear()


def current_user(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Identity:
    email = request.session.get(_SESSION_EMAIL_KEY)
    if not isinstance(email, str) or not email:
        raise UnauthorizedError()
    # Re-authorize every request against the current allow-list: a session
    # minted before an address was removed must stop working at once.
    if not settings.email_allowed(email):
        request.session.clear()
        raise UnauthorizedError()
    name = request.session.get(_SESSION_NAME_KEY)
    return Identity(email=email, name=name if isinstance(name, str) else email)


def get_oidc_verifier(settings: Settings = Depends(get_settings)) -> OIDCVerifier:
    """Dependency returning the OIDC verifier; overridden in tests with a fake."""

    return GoogleOIDCVerifier(settings)
