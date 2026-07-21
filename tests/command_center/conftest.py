"""Command-center API test harness.

Reuses the top-level ``tests/conftest.py`` DB fixtures (migrate once, truncate
between tests) -- the API's ``get_conn`` reads ``DATABASE_URL``, which that
harness points at the throwaway test DB. Here we add a FastAPI ``TestClient``
with a fake OIDC verifier and a fake GitHub merger, plus seed helpers that
write through the shared emctl repos.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from command_center.auth.oidc import OIDCIdentity, OIDCVerifier
from command_center.config import Settings
from command_center.github import GitHubMerger, MergeResult
from command_center.main import create_app
from command_center.routers.approvals import get_github_merger
from command_center.security import get_oidc_verifier

ALLOWED_EMAIL = "tyler@tylerdorland.com"
DENIED_EMAIL = "intruder@example.com"


def _test_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "SESSION_SECRET": "test-secret",
        "ALLOWED_EMAILS": ALLOWED_EMAIL,
        "DEV_AUTH": True,
        "SESSION_HTTPS_ONLY": False,
        "GITHUB_TOKEN": "",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


class _FakeVerifier:
    """OIDC verifier stand-in; tests set the identity it returns."""

    identity: OIDCIdentity = OIDCIdentity(
        google_sub="g-tyler", email=ALLOWED_EMAIL, name="Tyler"
    )

    def authorization_url(self, state: str) -> str:
        return f"https://accounts.google.example/auth?state={state}"

    def fetch_identity(self, code: str) -> OIDCIdentity:
        return self.identity


class FakeMerger:
    """GitHub merger stand-in; records calls and returns a canned result."""

    def __init__(self, result: MergeResult | None = None) -> None:
        self.result = result or MergeResult(
            merged=True, sha="deadbeef", message="Merged"
        )
        self.calls: list[tuple[str, str, int]] = []

    def merge(self, owner: str, repo: str, number: int) -> MergeResult:
        self.calls.append((owner, repo, number))
        return self.result


@pytest.fixture
def fake_verifier() -> _FakeVerifier:
    return _FakeVerifier()


@pytest.fixture
def fake_merger() -> FakeMerger:
    return FakeMerger()


def _build_client(
    settings: Settings,
    verifier: OIDCVerifier,
    merger: GitHubMerger | None,
) -> TestClient:
    app = create_app(settings=settings)
    app.dependency_overrides[get_oidc_verifier] = lambda: verifier
    if merger is not None:
        app.dependency_overrides[get_github_merger] = lambda: merger
    return TestClient(app)


@pytest.fixture
def client(
    fake_verifier: _FakeVerifier, fake_merger: FakeMerger
) -> Iterator[TestClient]:
    with _build_client(_test_settings(), fake_verifier, fake_merger) as c:
        yield c


@pytest.fixture
def no_token_client(fake_verifier: _FakeVerifier) -> Iterator[TestClient]:
    """Client with the real merger dependency and no GitHub token, to exercise
    clean degradation of the merge endpoint."""
    with _build_client(_test_settings(GITHUB_TOKEN=""), fake_verifier, None) as c:
        yield c


@pytest.fixture
def dev_off_client(fake_verifier: _FakeVerifier) -> Iterator[TestClient]:
    """Client with ``DEV_AUTH`` off, to assert the dev-login and docs surfaces
    are fenced off (404) when the flag is not set."""
    with _build_client(_test_settings(DEV_AUTH=False), fake_verifier, None) as c:
        yield c


def login(client: TestClient, email: str = ALLOWED_EMAIL, name: str = "Tyler") -> None:
    resp = client.post("/api/auth/dev-login", json={"email": email, "name": name})
    assert resp.status_code == 200, resp.text
