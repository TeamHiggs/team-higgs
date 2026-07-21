"""Create a task -- author a backlog item (PRD §2).

The task lands as ``backlog`` (the DB default) and waits for a greenlight
before anything can pick it up. Creating a task is a state write; it never
dispatches or runs anything (decisions #15/#16). Shared with the CLI via
``emctl.services.create_task`` so the opening ``task_events`` row is written
identically.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from command_center.db import get_conn
from command_center.schemas import CreateTaskRequest, TaskOut
from command_center.security import Identity, current_user
from emctl import services
from emctl.db import Conn

router = APIRouter(prefix="/api", tags=["tasks"])


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(
    payload: CreateTaskRequest,
    user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
) -> TaskOut:
    row = services.create_task(
        conn,
        project_id=payload.project,
        title=payload.title,
        spec=payload.spec,
        role=payload.role,
        model_tier=payload.tier,
        prd_ref=payload.prd_ref,
        status=None,  # opens as backlog (schema default)
        branch=None,
        depends_on=payload.depends_on or None,
        actor=user.email,
    )
    return TaskOut.model_validate(row)
