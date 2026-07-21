"""GitHub PR merge -- the one outward call the service makes (decision #21).

Merging a PR Tyler has approved is *external state*, not compute: it starts no
agent and calls no model API, so it stays inside the "writes state, never spawns
compute" boundary (decisions #15/#16). The client uses only the merge endpoint
of the GitHub REST API with a least-privilege, merge-only token injected from
Secret Manager (infra task #29).

Behind a mockable seam (``GitHubMerger``) so the merge path is testable without
a live token or network. When no token is configured (local/dev), the merge
endpoint degrades cleanly -- a 503 with a clear message, never a crash.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

import httpx

from command_center.config import Settings
from command_center.errors import ServiceUnavailable, ValidationFailure

# owner/repo out of "owner/repo", a full https URL, or an scp-style git remote.
_OWNER_REPO = re.compile(
    r"(?:github\.com[:/])?(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)


@dataclass(frozen=True)
class MergeResult:
    merged: bool
    sha: str | None
    message: str


def parse_owner_repo(repo_ref: str) -> tuple[str, str]:
    """Extract ``(owner, repo)`` from a project's ``repo`` field.

    Raises :class:`ValidationFailure` when the reference is not a recognizable
    GitHub ``owner/repo``, so a malformed project row surfaces as a clean 400
    rather than a bad outward request.
    """
    match = _OWNER_REPO.search(repo_ref.strip())
    if not match:
        raise ValidationFailure(f"cannot derive a GitHub repo from '{repo_ref}'")
    return match.group("owner"), match.group("repo")


class GitHubMerger(Protocol):
    def merge(self, owner: str, repo: str, number: int) -> MergeResult: ...


class HttpGitHubMerger:
    """Real merge client. Requires a token; construction fails without one so
    the endpoint can translate the absence into a clean 503."""

    def __init__(self, settings: Settings) -> None:
        if not settings.github_token:
            raise ServiceUnavailable(
                "PR merge is unavailable: no GitHub token is configured"
            )
        self._token = settings.github_token
        self._api = settings.github_api_url.rstrip("/")

    def merge(self, owner: str, repo: str, number: int) -> MergeResult:
        url = f"{self._api}/repos/{owner}/{repo}/pulls/{number}/merge"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.put(url, headers=headers, json={"merge_method": "merge"})
        except httpx.HTTPError as exc:  # network failure, not a merge verdict
            raise ServiceUnavailable("could not reach GitHub to merge") from exc

        if resp.status_code == 200:
            body = resp.json()
            return MergeResult(
                merged=bool(body.get("merged")),
                sha=body.get("sha"),
                message=str(body.get("message", "Merged")),
            )
        # 405 not mergeable, 409 head moved, 404 not found / no access, 401/403
        # bad token. Surface a clean, non-leaky reason; the token is never echoed.
        reason = {
            404: "PR not found or the token cannot access the repository",
            405: "PR is not mergeable",
            409: "PR head changed since review; refresh and retry",
            401: "GitHub rejected the merge token",
            403: "GitHub token lacks merge permission",
        }.get(resp.status_code, f"GitHub merge failed ({resp.status_code})")
        raise ServiceUnavailable(reason)
