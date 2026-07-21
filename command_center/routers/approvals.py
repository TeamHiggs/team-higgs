"""The approval queue: the ``awaiting_tyler`` line (PRD §2, §7).

The queue is a composed, discriminated list of the things that stopped for
Tyler's call: PRs he has not decided, proposed artifacts, proposed decisions,
and blocking questions. He approves/rejects in place (a state write), previews
the attached artifact inline, and -- for a PR he has approved -- merges it via
the GitHub API (decision #21: external state, not compute).

All writes reuse the shared emctl repos. No route spawns compute or invokes the
model API (decisions #15/#16); the merge is the only outward call.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from command_center.config import Settings, get_settings
from command_center.db import get_conn
from command_center.errors import (
    ForbiddenError,
    NotFoundFailure,
    ValidationFailure,
)
from command_center.github import (
    GitHubMerger,
    HttpGitHubMerger,
    parse_owner_repo,
)
from command_center.schemas import (
    AnswerRequest,
    ApprovalItem,
    ApprovalsOut,
    ArtifactContentOut,
    DecisionRequest,
    MergeOut,
    MessageOut,
    PrDetailOut,
    PrOut,
    ReviewOut,
)
from command_center.security import Identity, current_user
from emctl.db import Conn
from emctl.repo import (
    artifacts,
    decisions,
    projects,
    prs,
    questions,
    reviews,
)

logger = logging.getLogger("command_center")

router = APIRouter(prefix="/api/approvals", tags=["approvals"])

# Inline-preview cap: artifacts are text (decision #20). Bigger files are
# truncated so a huge diff cannot balloon a response.
_MAX_PREVIEW_BYTES = 512 * 1024

_ARTIFACT_BADGE = {
    "mockup": "mockup",
    "diagram": "mockup",
    "spec": "doc",
    "schema": "doc",
    "prompt": "doc",
    "model": "doc",
    "eval-set": "doc",
}


def get_github_merger(settings: Settings = Depends(get_settings)) -> GitHubMerger:
    """Real merger; raises 503 when no token is configured (local/dev).
    Overridden in tests with a fake."""
    return HttpGitHubMerger(settings)


# --- queue -----------------------------------------------------------------


@router.get("", response_model=ApprovalsOut)
def list_queue(
    _user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
) -> ApprovalsOut:
    items: list[ApprovalItem] = []

    for pr in prs.list_awaiting_decision(conn):
        items.append(
            ApprovalItem(
                kind="pr",
                id=int(pr["id"]),
                title=str(pr.get("em_summary") or f"PR #{pr['github_pr']}"),
                project_id=pr.get("project_id"),
                badge="pr",
                risk_level=pr.get("risk_level"),
                github_pr=int(pr["github_pr"]),
            )
        )

    # artifacts.list_ has no status filter; proposed items are selected here.
    for art in artifacts.list_(conn, project_id=None, task_id=None, type_=None):
        if str(art["status"]) != "proposed":
            continue
        items.append(
            ApprovalItem(
                kind="artifact",
                id=int(art["id"]),
                title=str(art["path"]),
                project_id=art.get("project_id"),
                badge=_ARTIFACT_BADGE.get(str(art["type"]), "doc"),
                artifact_type=str(art["type"]),
            )
        )

    for dec in decisions.list_(
        conn, project_id=None, significance=None, status="proposed"
    ):
        items.append(
            ApprovalItem(
                kind="decision",
                id=int(dec["id"]),
                title=str(dec["title"]),
                project_id=dec.get("project_id"),
                badge="decision",
            )
        )

    for q in questions.list_(conn, blocking_only=True):
        items.append(
            ApprovalItem(
                kind="question",
                id=int(q["id"]),
                title=str(q["body"]),
                project_id=q.get("project_id"),
                badge="question",
                blocking=True,
            )
        )

    return ApprovalsOut(items=items)


# --- PR preview + decision + merge -----------------------------------------


@router.get("/pr/{pr_id}", response_model=PrDetailOut)
def pr_detail(
    pr_id: int,
    _user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
) -> PrDetailOut:
    pr = prs.get(conn, pr_id)  # NotFound -> 404
    panel = reviews.list_for_pr(conn, pr_id)
    return PrDetailOut(
        pr=PrOut.model_validate(pr),
        reviews=[ReviewOut.model_validate(r) for r in panel],
    )


@router.post("/pr/{pr_id}/merge", response_model=MergeOut)
def merge_pr(
    pr_id: int,
    _user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
    merger: GitHubMerger = Depends(get_github_merger),
) -> MergeOut:
    pr = prs.get(conn, pr_id)  # NotFound -> 404
    if str(pr.get("tyler_decision") or "") != "approve":
        raise ValidationFailure("approve the PR before merging")
    if str(pr["status"]) == "merged":
        raise ValidationFailure("PR is already merged")

    project = projects.get(conn, int(pr["project_id"]))
    owner, repo = parse_owner_repo(str(project["repo"]))
    # External state change (decision #21); ServiceUnavailable (no token /
    # not mergeable / network) propagates to a clean 5xx without a status write.
    result = merger.merge(owner, repo, int(pr["github_pr"]))
    if not result.merged:
        raise ValidationFailure(result.message)

    prs.update(
        conn,
        pr_id,
        status="merged",
        risk_level=None,
        em_summary=None,
        tyler_decision=None,
        task_id=None,
    )
    logger.info("pr_merged", extra={"pr_id": pr_id})
    return MergeOut(merged=True, sha=result.sha, detail=result.message)


# --- artifact inline preview ----------------------------------------------


@router.get("/artifact/{artifact_id}/content", response_model=ArtifactContentOut)
def artifact_content(
    artifact_id: int,
    _user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> ArtifactContentOut:
    matches = [
        a
        for a in artifacts.list_(conn, project_id=None, task_id=None, type_=None)
        if int(a["id"]) == artifact_id
    ]
    if not matches:
        raise NotFoundFailure(f"artifact {artifact_id} not found")
    path = str(matches[0]["path"])

    if path.startswith("gs://") or "://" in path:
        raise ValidationFailure("artifact is stored externally; no inline preview")

    root = settings.repo_root
    resolved = (root / path).resolve()
    # Path-traversal guard: the file must stay inside the repo root.
    if not resolved.is_relative_to(root):
        raise ForbiddenError("artifact path escapes the repository root")
    if not resolved.is_file():
        raise NotFoundFailure("artifact file is not present in the checkout")

    raw = resolved.read_bytes()
    truncated = len(raw) > _MAX_PREVIEW_BYTES
    text = raw[:_MAX_PREVIEW_BYTES].decode("utf-8", errors="replace")
    return ArtifactContentOut(path=path, content=text, truncated=truncated)


# --- approve / reject ------------------------------------------------------


@router.post("/decision", response_model=MessageOut)
def decide(
    payload: DecisionRequest,
    _user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
) -> MessageOut:
    approve = payload.verdict == "approve"

    if payload.kind == "pr":
        prs.get(conn, payload.id)  # NotFound -> 404
        prs.update(
            conn,
            payload.id,
            status=None if approve else "rejected",
            risk_level=None,
            em_summary=None,
            # PR stays 'open' on approve until the merge endpoint runs (§7).
            tyler_decision="approve" if approve else "reject",
            task_id=None,
            # Persist Tyler's rationale for the audit trail (§7).
            tyler_note=payload.note,
        )
    elif payload.kind == "artifact":
        artifacts.decide(
            conn,
            payload.id,
            status="approved" if approve else "rejected",
            notes=payload.note,
        )
    elif payload.kind == "decision":
        decisions.decide(
            conn,
            payload.id,
            status="accepted" if approve else "reversed",
            note=payload.note,
        )

    verb = "approved" if approve else "rejected"
    return MessageOut(detail=f"{payload.kind} {payload.id} {verb}")


@router.post("/question/{question_id}/answer", response_model=MessageOut)
def answer_question(
    question_id: int,
    payload: AnswerRequest,
    _user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
) -> MessageOut:
    questions.answer(conn, question_id, answer=payload.answer)
    return MessageOut(detail=f"question {question_id} answered")