"""Real Google OIDC verification: token exchange + claim enforcement.

Exercises the actual ``GoogleOIDCVerifier.fetch_identity`` -- issuer, audience,
and email_verified checks -- with only the HTTP transport mocked (not the
verifier seam, not the dev-auth bypass). The service verifies ID tokens via
Google's ``tokeninfo`` endpoint, so the claims are supplied through a mocked
tokeninfo response. Ported from plant-log's proven auth tests.
"""

from __future__ import annotations

import httpx
import pytest

from command_center.auth.oidc import GoogleOIDCVerifier, OIDCError
from command_center.config import Settings

_CLIENT_ID = "client-abc.apps.googleusercontent.com"


def _settings() -> Settings:
    return Settings(
        SESSION_SECRET="x",
        ALLOWED_EMAILS="tyler@tylerdorland.com",
        GOOGLE_CLIENT_ID=_CLIENT_ID,
    )


def _base_claims() -> dict[str, str]:
    return {
        "aud": _CLIENT_ID,
        "iss": "https://accounts.google.com",
        "email_verified": "true",
        "sub": "google-sub-123",
        "email": "tyler@tylerdorland.com",
        "name": "Tyler",
    }


def _install_mock_transport(
    monkeypatch: pytest.MonkeyPatch, claims: dict[str, str]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"id_token": "mock-id-token"})
        return httpx.Response(200, json=claims)

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def factory(*_args: object, **_kwargs: object) -> httpx.Client:
        return real_client(transport=transport)

    monkeypatch.setattr(httpx, "Client", factory)


def test_accepts_verified_google_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_mock_transport(monkeypatch, _base_claims())
    identity = GoogleOIDCVerifier(_settings()).fetch_identity("auth-code")
    assert identity.google_sub == "google-sub-123"
    assert identity.email == "tyler@tylerdorland.com"


def test_rejects_wrong_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    claims = _base_claims() | {"iss": "https://accounts.evil.example"}
    _install_mock_transport(monkeypatch, claims)
    with pytest.raises(OIDCError):
        GoogleOIDCVerifier(_settings()).fetch_identity("auth-code")


def test_rejects_wrong_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    claims = _base_claims() | {"aud": "some-other-client-id"}
    _install_mock_transport(monkeypatch, claims)
    with pytest.raises(OIDCError):
        GoogleOIDCVerifier(_settings()).fetch_identity("auth-code")


def test_rejects_unverified_email(monkeypatch: pytest.MonkeyPatch) -> None:
    claims = _base_claims() | {"email_verified": "false"}
    _install_mock_transport(monkeypatch, claims)
    with pytest.raises(OIDCError):
        GoogleOIDCVerifier(_settings()).fetch_identity("auth-code")
