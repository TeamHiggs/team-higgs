"""Google OIDC behind a mockable seam.

Ported from plant-log's proven auth path (decision #17). ``OIDCVerifier`` is the
interface the auth routes depend on; ``GoogleOIDCVerifier`` is the real
implementation (authorization-code exchange + ID-token verification via Google's
endpoints). Tests and the dev-auth path substitute a fake, so every
authenticated endpoint is exercisable without real Google credentials.

The provider endpoints below are fixed OIDC protocol URLs, not deployment
tunables or secrets; client id/secret and redirect URI come from settings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

import httpx

from command_center.config import Settings

_GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_GOOGLE_TOKENINFO_ENDPOINT = "https://oauth2.googleapis.com/tokeninfo"
_SCOPE = "openid email profile"


@dataclass(frozen=True)
class OIDCIdentity:
    """The verified subject returned by the identity provider."""

    google_sub: str
    email: str
    name: str


class OIDCError(Exception):
    """Raised when the provider exchange or verification fails."""


class OIDCVerifier(Protocol):
    def authorization_url(self, state: str) -> str: ...

    def fetch_identity(self, code: str) -> OIDCIdentity: ...


class GoogleOIDCVerifier:
    """Real Google OIDC verifier.

    Note: this network path cannot be exercised in this environment (no Google
    credentials); it is covered by the mockable seam and the dev-auth path, and
    is declared as untested-against-live in the PR.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def authorization_url(self, state: str) -> str:
        params = {
            "client_id": self._settings.google_client_id,
            "redirect_uri": self._settings.google_redirect_uri,
            "response_type": "code",
            "scope": _SCOPE,
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"{_GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"

    def fetch_identity(self, code: str) -> OIDCIdentity:
        with httpx.Client(timeout=10.0) as client:
            token_resp = client.post(
                _GOOGLE_TOKEN_ENDPOINT,
                data={
                    "code": code,
                    "client_id": self._settings.google_client_id,
                    "client_secret": self._settings.google_client_secret,
                    "redirect_uri": self._settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_resp.status_code != 200:
                raise OIDCError("token exchange failed")
            id_token = token_resp.json().get("id_token")
            if not id_token:
                raise OIDCError("no id_token in token response")

            info_resp = client.get(
                _GOOGLE_TOKENINFO_ENDPOINT, params={"id_token": id_token}
            )
            if info_resp.status_code != 200:
                raise OIDCError("id_token verification failed")
            claims = info_resp.json()

        if claims.get("aud") != self._settings.google_client_id:
            raise OIDCError("id_token audience mismatch")
        if claims.get("iss") not in self._settings.google_issuers:
            raise OIDCError("id_token issuer mismatch")
        if not _claim_is_true(claims.get("email_verified")):
            raise OIDCError("id_token email not verified")
        sub = claims.get("sub")
        email = claims.get("email")
        if not sub or not email:
            raise OIDCError("id_token missing sub/email")
        name = claims.get("name") or email
        return OIDCIdentity(google_sub=str(sub), email=str(email), name=str(name))


def _claim_is_true(value: object) -> bool:
    """True iff the claim asserts a boolean true.

    Google's ``tokeninfo`` endpoint returns claim values as strings (``"true"``),
    while a decoded JWT payload carries a real boolean; accept both forms.
    """

    return value is True or (
        isinstance(value, str) and value.strip().lower() == "true"
    )
