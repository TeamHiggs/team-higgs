"""Backlog grooming: greenlight, block/unblock, reorder (PRD §2).

Every action is a state write over the real status vocabulary. Greenlighting
sets a task ``backlog -> planned`` (ready to dispatch); dispatch itself happens
elsewhere -- nothing here spawns an agent (decisions #15/#16). Status changes go
through ``emctl.services.update_task`` so a ``task_events`` row is recorded
exactly as the CLI would.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from command_center.db import get_conn
from command_center.errors import ValidationFailure
from command_center.schemas import BacklogOut, BlockRequest, ReorderRequest, TaskOut
from command_center.security import Identity, current_user
from emctl import services
from emctl.db import Conn
from emctl.repo import tasks

router = APIRouter(prefix="/api", tags=["backlog"])

_IN_FLIGHT = {"in_progress", "in_review", "awaiting_tyler"}


@router.get("/backlog", response_model=BacklogOut)
def backlog(
    _user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
) -> BacklogOut:
    rows = tasks.list_for_groom(conn, status=None)
    out: dict[str, list[TaskOut]] = {"backlog": [], "planned": [], "in_flight": []}
    for r in rows:
        status = str(r["status"])
        if status == "backlog":
            out["backlog"].append(TaskOut.model_validate(r))
        elif status == "planned":
            out["planned"].append(TaskOut.model_validate(r))
        elif status in _IN_FLIGHT:
            out["in_flight"].append(TaskOut.model_validate(r))
        # 'done' is intentionally omitted from the grooming board.
    return BacklogOut(**out)


@router.post("/tasks/{task_id}/greenlight", response_model=TaskOut)
def greenlight(
    task_id: int,
    user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
) -> TaskOut:
    current = tasks.get(conn, task_id)  # NotFound -> 404
    if str(current["status"]) != "backlog":
        raise ValidationFailure(
            f"only a backlog task can be greenlit (task {task_id} is "
            f"{current['status']})"
        )
    row = services.update_task(
        conn,
        task_id,
        {"status": "planned"},
        new_status="planned",
        actor=user.email,
    )
    return TaskOut.model_validate(row)


@router.post("/tasks/{task_id}/block", response_model=TaskOut)
def block(
    task_id: int,
    payload: BlockRequest,
    user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
) -> TaskOut:
    row = services.update_task(
        conn,
        task_id,
        {"blocked": True, "blocked_reason": payload.reason},
        new_status=None,  # blocked is a flag, not a status transition
        actor=user.email,
    )
    return TaskOut.model_validate(row)


@router.post("/tasks/{task_id}/unblock", response_model=TaskOut)
def unblock(
    task_id: int,
    user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
) -> TaskOut:
    row = services.update_task(
        conn,
        task_id,
        {"blocked": False, "blocked_reason": None},
        new_status=None,
        actor=user.email,
    )
    return TaskOut.model_validate(row)


@router.post("/backlog/reorder", response_model=list[TaskOut])
def reorder(
    payload: ReorderRequest,
    _user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
) -> list[TaskOut]:
    rows = tasks.reorder(conn, payload.ordered_ids)
    return [TaskOut.model_validate(r) for r in rows]
