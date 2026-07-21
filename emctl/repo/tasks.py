"""tasks table."""

from __future__ import annotations

from typing import Any

from psycopg import sql

from emctl.db import Conn
from emctl.errors import NotFoundError
from emctl.repo import _sql

Row = _sql.Row


def create(
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
) -> Row:
    values: dict[str, Any] = {"project_id": project_id, "title": title}
    optional = {
        "spec": spec,
        "role": role,
        "model_tier": model_tier,
        "prd_ref": prd_ref,
        "status": status,
        "branch": branch,
        "depends_on": depends_on,
    }
    for key, value in optional.items():
        if value is not None:
            values[key] = value
    return _sql.insert(conn, "tasks", values)


def get(conn: Conn, task_id: int) -> Row:
    return _sql.get(conn, "tasks", "task", task_id)


def update(conn: Conn, task_id: int, values: dict[str, Any]) -> Row:
    # Always advance updated_at; it takes no bound value.
    extra = [sql.SQL("updated_at = now()")]
    return _sql.update(conn, "tasks", "task", task_id, values, extra=extra)


def list_(
    conn: Conn,
    *,
    status: str | None,
    project_id: int | None,
    role: str | None,
    blocked: bool | None,
) -> list[Row]:
    where: dict[str, Any] = {}
    if status is not None:
        where["status"] = status
    if project_id is not None:
        where["project_id"] = project_id
    if role is not None:
        where["role"] = role
    if blocked is not None:
        where["blocked"] = blocked
    return _sql.select(conn, "tasks", where=where or None)


def list_for_groom(conn: Conn, *, status: str | None) -> list[Row]:
    """Tasks in grooming order: explicit ``groom_rank`` first (ascending),
    then unranked tasks by id. Optionally filtered to one status.

    A distinct read from :func:`list_` (which orders by id) so the CLI's
    ``task list`` output stays byte-for-byte identical.
    """
    query: sql.Composable = sql.SQL("SELECT * FROM tasks")
    params: list[Any] = []
    if status is not None:
        query = query + sql.SQL(" WHERE status = %s")
        params.append(status)
    # NULLS LAST keeps never-reordered tasks after explicitly ranked ones.
    query = query + sql.SQL(" ORDER BY groom_rank ASC NULLS LAST, id ASC")
    return list(conn.execute(query, params).fetchall())


def reorder(conn: Conn, ordered_ids: list[int]) -> list[Row]:
    """Assign ``groom_rank`` from the given order (0-based) and return the
    updated rows. Each id is set to its index in ``ordered_ids``; an unknown
    id raises :class:`NotFoundError` (no row updated) before any partial write
    is committed, because all updates run in the caller's one transaction.
    """
    updated: list[Row] = []
    for rank, task_id in enumerate(ordered_ids):
        query = sql.SQL(
            "UPDATE tasks SET groom_rank = %s, updated_at = now() "
            "WHERE id = %s RETURNING *"
        )
        row = conn.execute(query, (rank, task_id)).fetchone()
        if row is None:
            raise NotFoundError(f"task {task_id} not found")
        updated.append(row)
    return updated
