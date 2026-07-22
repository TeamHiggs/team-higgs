"""The Content-Security-Policy is emitted on every response (task #34).

Defence-in-depth for the one-image SPA: default-src locks every subresource to
this origin; style-src additionally allows 'unsafe-inline' because the React SPA
applies inline style attributes. Scripts stay locked to 'self'.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

EXPECTED_CSP = "default-src 'self'; style-src 'self' 'unsafe-inline'"


def test_healthz_carries_csp(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.headers["content-security-policy"] == EXPECTED_CSP


def test_api_response_carries_csp(client: TestClient) -> None:
    # An unauthenticated API call still flows through the middleware.
    resp = client.get("/api/me")
    assert resp.headers["content-security-policy"] == EXPECTED_CSP


def test_csp_locks_scripts_to_self_and_allows_only_inline_styles() -> None:
    # Guard the exact directives: scripts must NOT be granted 'unsafe-inline'.
    assert "script-src" not in EXPECTED_CSP  # scripts fall back to default-src 'self'
    default_src, style_src = (d.strip() for d in EXPECTED_CSP.split(";"))
    assert default_src == "default-src 'self'"
    assert style_src == "style-src 'self' 'unsafe-inline'"
