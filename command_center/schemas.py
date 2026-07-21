"""Typed request/response models (Pydantic v2).

Every route signature uses these -- never a bare ``dict``/``Any`` on the API
seam -- so the published OpenAPI schema is the accurate contract the SPA (task
#28) builds against. Response models are validated from emctl repo rows
(``dict``), ignoring columns the surface does not expose.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# --- shared config ---------------------------------------------------------

Tier = Literal["plan", "execute", "local"]
Verdict = Literal["approve", "reject"]
ApprovalKind = Literal["pr", "artifact", "decision", "question"]


class _Out(BaseModel):
    """Base for responses built from emctl rows; extra columns are ignored."""

    model_config = ConfigDict(extra="ignore")


# --- auth ------------------------------------------------------------------


class UserOut(_Out):
    email: str
    name: str


class MessageOut(BaseModel):
    detail: str


class DevLoginRequest(BaseModel):
    email: str
    name: str | None = None


# --- tasks / backlog -------------------------------------------------------


class TaskOut(_Out):
    id: int
    project_id: int
    title: str
    spec: str | None = None
    status: str
    blocked: bool
    blocked_reason: str | None = None
    role: str | None = None
    model_tier: str
    prd_ref: str | None = None
    branch: str | None = None
    depends_on: list[int]
    groom_rank: int | None = None
    created_at: datetime
    updated_at: datetime


class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=1)
    project: int
    spec: str | None = None
    role: str | None = None
    tier: Tier | None = None
    prd_ref: str | None = None
    depends_on: list[int] = Field(default_factory=list)


class BlockRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class ReorderRequest(BaseModel):
    ordered_ids: list[int] = Field(..., min_length=1)


class BacklogOut(BaseModel):
    backlog: list[TaskOut]
    planned: list[TaskOut]
    in_flight: list[TaskOut]


# --- prs / reviews ---------------------------------------------------------


class PrOut(_Out):
    id: int
    project_id: int
    github_pr: int
    status: str
    risk_level: str | None = None
    em_summary: str | None = None
    tyler_decision: str | None = None
    decided_at: datetime | None = None
    task_id: int | None = None


class Finding(_Out):
    severity: str | None = None
    where: str | None = None
    claim: str | None = None
    evidence: str | None = None
    why: str | None = None
    fix: str | None = None


class ReviewOut(_Out):
    id: int
    pr_id: int
    role: str
    model: str | None = None
    verdict: str
    findings: list[Finding] = Field(default_factory=list)
    strongest_objection: str
    created_at: datetime


class PrDetailOut(BaseModel):
    pr: PrOut
    reviews: list[ReviewOut]


class MergeOut(BaseModel):
    merged: bool
    sha: str | None = None
    detail: str


# --- artifacts -------------------------------------------------------------


class ArtifactOut(_Out):
    id: int
    project_id: int
    task_id: int | None = None
    type: str
    path: str
    status: str
    decided_at: datetime | None = None
    notes: str | None = None


class ArtifactContentOut(BaseModel):
    path: str
    content: str
    truncated: bool


# --- decisions / questions / risks / runs ----------------------------------


class DecisionOut(_Out):
    id: int
    project_id: int | None = None
    title: str
    context: str | None = None
    decision: str
    status: str
    significance: str
    superseded_by: int | None = None
    created_at: datetime


class QuestionOut(_Out):
    id: int
    project_id: int | None = None
    body: str
    blocking: bool
    answer: str | None = None
    answered_at: datetime | None = None
    created_at: datetime


class AnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1)


class RiskOut(_Out):
    id: int
    project_id: int
    title: str
    body: str | None = None
    category: str
    severity: str
    status: str
    mitigation: str | None = None
    decision_id: int | None = None
    pr_id: int | None = None
    acknowledged_by: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class RunOut(_Out):
    id: int
    task_id: int | None = None
    role: str
    model: str
    mode: str
    started_at: datetime
    ended_at: datetime | None = None
    outcome: str | None = None
    token_cost: int | None = None
    cost_usd: Decimal | None = None
    log_ref: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None


# --- improvement -----------------------------------------------------------


class LearningOut(_Out):
    id: int
    category: str
    observation: str
    evidence: str | None = None
    filed_by: str | None = None
    status: str
    retro_id: int | None = None
    created_at: datetime


class DebtOut(_Out):
    id: int
    project_id: int | None = None
    location: str
    kind: str
    severity: str
    evidence: str
    filed_by: str | None = None
    recurrence: int
    passes_survived: int
    status: str
    resolved_ref: str | None = None
    created_at: datetime


class RetroOut(_Out):
    id: int
    trigger: str
    doc_path: str | None = None
    opened_at: datetime
    closed_at: datetime | None = None


class ImprovementOut(BaseModel):
    retros: list[RetroOut]
    learnings: list[LearningOut]
    debt: list[DebtOut]


# --- notes -----------------------------------------------------------------


class NoteOut(_Out):
    id: int
    body: str
    author: str | None = None
    context: str | None = None
    created_at: datetime


class NoteCreate(BaseModel):
    body: str = Field(..., min_length=1)
    context: str | None = None


# --- approvals -------------------------------------------------------------


class ApprovalItem(BaseModel):
    """One item in the ``awaiting_tyler`` queue. ``kind`` discriminates the
    backing entity; the SPA renders the matching detail view."""

    kind: ApprovalKind
    id: int
    title: str
    project_id: int | None = None
    badge: str
    # Kind-specific hints for the queue card (all optional; only the relevant
    # ones are populated per kind).
    risk_level: str | None = None
    artifact_type: str | None = None
    github_pr: int | None = None
    blocking: bool | None = None


class ApprovalsOut(BaseModel):
    items: list[ApprovalItem]


class DecisionRequest(BaseModel):
    kind: Literal["pr", "artifact", "decision"]
    id: int
    verdict: Verdict
    note: str | None = None
