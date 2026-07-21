"""Read-only state surfaces: PRs, risks, questions, recent run costs.

The rest of ``emctl status`` made visual (PRD §2). Every route is authenticated
and reads through the shared emctl repos -- no query is re-implemented here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from command_center.db import get_conn
from command_center.schemas import PrOut, QuestionOut, RiskOut, RunOut
from command_center.security import Identity, current_user
from emctl.db import Conn
from emctl.repo import prs, questions, risks, runs

router = APIRouter(prefix="/api", tags=["state"])


@router.get("/prs", response_model=list[PrOut])
def list_prs(
    _user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
) -> list[PrOut]:
    return [PrOut.model_validate(r) for r in prs.list_(conn)]


@router.get("/risks", response_model=list[RiskOut])
def list_risks(
    _user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
) -> list[RiskOut]:
    return [
        RiskOut.model_validate(r)
        for r in risks.list_(
            conn, project_id=None, status=None, category=None, severity=None
        )
    ]


@router.get("/questions", response_model=list[QuestionOut])
def list_questions(
    _user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
) -> list[QuestionOut]:
    return [
        QuestionOut.model_validate(r)
        for r in questions.list_(conn, blocking_only=False)
    ]


@router.get("/runs", response_model=list[RunOut])
def list_runs(
    limit: int = Query(50, ge=1, le=200),
    _user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
) -> list[RunOut]:
    return [RunOut.model_validate(r) for r in runs.list_recent(conn, limit=limit)]
