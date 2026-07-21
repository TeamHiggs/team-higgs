"""Write orchestration shared by the CLI commands and the command-center API.

The repo layer owns single-table SQL; a few writes span two tables in a fixed
order (create a task *and* record its opening ``task_events`` row; update a
task *and* record a status-change event). That orchestration lived only in
``commands/task.py``. It is factored here so the HTTP API performs the exact
same writes without re-implementing them (PRD command-center §3, decision #18:
colocation without duplication). Functions take a caller-supplied ``Conn`` and
run inside the caller's transaction; they never open connections, read the
environment, or print.
"""

from __future__ import annotations

from typing import Any

from emctl.db import Conn
from emctl.repo import _sql, task_events, tasks

Row = _sql.Row


def create_task(
    conn: Conn,
    *,
    project_id: int,
    title: str,
    spec: str | None,
    role: str | None,
    model_tier: str | None,
    prd_ref: str | None,
    status: str | None,
    branch: str | None,
    depends_on: list[int] | None,
    actor: str | None,
) -> Row:
    """Create a task and record its opening status as the first history event
    (``from_status`` NULL on creation)."""
    row = tasks.create(
        conn,
        project_id=project_id,
        title=title,
        spec=spec,
        role=role,
        model_tier=model_tier,
        prd_ref=prd_ref,
        status=status,
        branch=branch,
        depends_on=depends_on,
    )
    task_events.add(
        conn,
        task_id=int(row["id"]),
        from_status=None,
        to_status=str(row["status"]),
        actor=actor,
    )
    return row


def update_task(
    conn: Conn,
    task_id: int,
    values: dict[str, Any],
    *,
    new_status: str | None,
    actor: str | None,
) -> Row:
    """Update a task and, when ``new_status`` is a genuine change from the
    stored status, record a ``task_events`` row with the correct from/to.

    Reads the current row first so a clean not-found surfaces before any write
    and the event's ``from_status`` is accurate.
    """
    current = tasks.get(conn, task_id)
    row = tasks.update(conn, task_id, values)
    if new_status is not None and new_status != current["status"]:
        task_events.add(
            conn,
            task_id=task_id,
            from_status=str(current["status"]),
            to_status=new_status,
            actor=actor,
        )
    return row
