"""GitHub merge client: owner/repo parsing and status-code mapping.

The outward call is mocked with an httpx transport -- no network, no token
leaves the process. Covers the security-reviewed surface: the merge-only API
call and how non-200 responses degrade.
"""

from __future__ import annotations

import httpx
import pytest

from command_center.config import Settings
from command_center.errors import ServiceUnavailable, ValidationFailure
from command_center.github import HttpGitHubMerger, parse_owner_repo


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        ("TeamHiggs/team-higgs", ("TeamHiggs", "team-higgs")),
        ("https://github.com/TeamHiggs/plant-log", ("TeamHiggs", "plant-log")),
        ("https://github.com/TeamHiggs/plant-log.git", ("TeamHiggs", "plant-log")),
        ("git@github.com:TeamHiggs/team-higgs.git", ("TeamHiggs", "team-higgs")),
    ],
)
def test_parse_owner_repo(ref: str, expected: tuple[str, str]) -> None:
    assert parse_owner_repo(ref) == expected


def test_parse_owner_repo_rejects_garbage() -> None:
    with pytest.raises(ValidationFailure):
        parse_owner_repo("not-a-repo")


def _merger_with(
    monkeypatch: pytest.MonkeyPatch, response: httpx.Response
) -> HttpGitHubMerger:
    def handler(_request: httpx.Request) -> httpx.Response:
        return response

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def factory(*_args: object, **_kwargs: object) -> httpx.Client:
        return real_client(transport=transport)

    monkeypatch.setattr(httpx, "Client", factory)
    return HttpGitHubMerger(
        Settings(SESSION_SECRET="x", ALLOWED_EMAILS="", GITHUB_TOKEN="tok")
    )


def test_no_token_construction_is_unavailable() -> None:
    with pytest.raises(ServiceUnavailable):
        HttpGitHubMerger(
            Settings(SESSION_SECRET="x", ALLOWED_EMAILS="", GITHUB_TOKEN="")
        )


def test_merge_success(monkeypatch: pytest.MonkeyPatch) -> None:
    merger = _merger_with(
        monkeypatch,
        httpx.Response(
            200, json={"merged": True, "sha": "abc123", "message": "Merged"}
        ),
    )
    result = merger.merge("TeamHiggs", "team-higgs", 27)
    assert result.merged is True
    assert result.sha == "abc123"


def test_merge_not_mergeable_maps_to_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    merger = _merger_with(
        monkeypatch, httpx.Response(405, json={"message": "not mergeable"})
    )
    with pytest.raises(ServiceUnavailable):
        merger.merge("TeamHiggs", "team-higgs", 27)


def test_merge_conflict_maps_to_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    merger = _merger_with(
        monkeypatch, httpx.Response(409, json={"message": "head moved"})
    )
    with pytest.raises(ServiceUnavailable):
        merger.merge("TeamHiggs", "team-higgs", 27)
