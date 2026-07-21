"""Continuous-improvement surface: read retros, learnings, and debt (PRD §2).

Scheduling an improvement activity is *creating a task* -- the SPA reuses
``POST /api/tasks`` (routers/tasks.py) for that, so nothing here spawns work.
This router is read-only.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from command_center.db import get_conn
from command_center.schemas import DebtOut, ImprovementOut, LearningOut, RetroOut
from command_center.security import Identity, current_user
from emctl.db import Conn
from emctl.repo import debt, learnings, retros

router = APIRouter(prefix="/api", tags=["improvement"])


@router.get("/improvement", response_model=ImprovementOut)
def improvement(
    _user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
) -> ImprovementOut:
    return ImprovementOut(
        retros=[RetroOut.model_validate(r) for r in retros.list_(conn)],
        learnings=[
            LearningOut.model_validate(r)
            for r in learnings.list_(conn, category=None, status=None)
        ],
        debt=[
            DebtOut.model_validate(r)
            for r in debt.list_(conn, status=None, severity=None, kind=None)
        ],
    )
