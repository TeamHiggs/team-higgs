"""Auth: OIDC redirect, allow-list, session, 401s, dev-login guard, docs fence."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from command_center.auth.oidc import OIDCIdentity
from command_center.config import Settings
from tests.command_center.conftest import (
    ALLOWED_EMAIL,
    DENIED_EMAIL,
    _FakeVerifier,
    login,
)


def _state(client: TestClient) -> str:
    resp = client.get("/api/auth/login", follow_redirects=False)
    assert resp.status_code == 302
    qs = parse_qs(urlparse(resp.headers["location"]).query)
    return qs["state"][0]


def test_login_redirects_to_provider(client: TestClient) -> None:
    resp = client.get("/api/auth/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"].startswith("https://")


def test_callback_allowlisted_establishes_session(client: TestClient) -> None:
    state = _state(client)
    resp = client.get(
        f"/api/auth/callback?code=abc&state={state}", follow_redirects=False
    )
    assert resp.status_code == 302
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["email"] == ALLOWED_EMAIL


def test_callback_denies_non_allowlisted(
    client: TestClient, fake_verifier: _FakeVerifier
) -> None:
    fake_verifier.identity = OIDCIdentity(
        google_sub="g-x", email=DENIED_EMAIL, name="No"
    )
    state = _state(client)
    resp = client.get(
        f"/api/auth/callback?code=abc&state={state}", follow_redirects=False
    )
    assert resp.status_code == 403
    assert client.get("/api/me").status_code == 401


def test_callback_rejects_bad_state(client: TestClient) -> None:
    _state(client)
    resp = client.get(
        "/api/auth/callback?code=abc&state=tampered", follow_redirects=False
    )
    assert resp.status_code == 400


def test_all_surfaces_require_session(client: TestClient) -> None:
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/approvals").status_code == 401
    assert client.get("/api/backlog").status_code == 401
    assert client.get("/api/prs").status_code == 401
    assert client.get("/api/risks").status_code == 401
    assert client.get("/api/questions").status_code == 401
    assert client.get("/api/runs").status_code == 401
    assert client.get("/api/notes").status_code == 401
    assert client.get("/api/improvement").status_code == 401


def test_write_surfaces_require_session(client: TestClient) -> None:
    # Auth is enforced before the resource is resolved, so placeholder ids and
    # bodies are fine: the response must be 401, never 404/422/200.
    assert client.post("/api/notes", json={"body": "x"}).status_code == 401
    assert (
        client.post("/api/tasks", json={"title": "x", "project": 1}).status_code == 401
    )
    assert client.post("/api/tasks/1/greenlight").status_code == 401
    assert client.post("/api/tasks/1/block", json={"reason": "x"}).status_code == 401
    assert (
        client.post(
            "/api/backlog/reorder", json={"ordered_ids": [1]}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/approvals/decision",
            json={"kind": "pr", "id": 1, "verdict": "approve"},
        ).status_code
        == 401
    )
    assert client.post("/api/approvals/pr/1/merge").status_code == 401


def test_logout_clears_session(client: TestClient) -> None:
    login(client)
    assert client.get("/api/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/me").status_code == 401


def test_dev_login_rejects_non_allowlisted(client: TestClient) -> None:
    resp = client.post("/api/auth/dev-login", json={"email": DENIED_EMAIL})
    assert resp.status_code == 403


def test_dev_login_not_in_openapi_and_docs_open_in_dev(client: TestClient) -> None:
    # DEV_AUTH is on for tests, so the schema is reachable but the dev-login
    # route is still excluded from it.
    schema = client.get("/openapi.json").json()
    assert "/api/auth/dev-login" not in schema["paths"]
    assert "/api/approvals" in schema["paths"]


def test_dev_auth_off_fences_devlogin_and_docs(dev_off_client: TestClient) -> None:
    # With DEV_AUTH off, the dev-login route and the docs/schema surfaces are
    # all 404 -- neither the OIDC bypass nor the info-disclosure surface exists.
    assert (
        dev_off_client.post(
            "/api/auth/dev-login", json={"email": ALLOWED_EMAIL}
        ).status_code
        == 404
    )
    assert dev_off_client.get("/docs").status_code == 404
    assert dev_off_client.get("/openapi.json").status_code == 404


def test_dev_auth_refused_with_production_oidc_signal() -> None:
    # Fail-closed: DEV_AUTH may not coexist with a configured GOOGLE_CLIENT_ID
    # (a production OIDC signal); Settings raises at construction/startup.
    with pytest.raises(ValidationError):
        Settings(
            SESSION_SECRET="x",  # type: ignore[call-arg]
            DEV_AUTH=True,
            GOOGLE_CLIENT_ID="real-client-id.apps.googleusercontent.com",
        )
