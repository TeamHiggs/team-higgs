"""reviews table."""

from __future__ import annotations

from typing import Any

from psycopg import sql
from psycopg.types.json import Jsonb

from emctl.db import Conn
from emctl.repo import _sql

Row = _sql.Row


def list_for_pr(conn: Conn, pr_id: int) -> list[Row]:
    """Panel reviews for one PR, oldest first (read for the approval preview)."""
    query = sql.SQL(
        "SELECT * FROM reviews WHERE pr_id = %s ORDER BY id ASC"
    )
    return list(conn.execute(query, (pr_id,)).fetchall())


def add(
    conn: Conn,
    *,
    pr_id: int,
    role: str,
    model: str | None,
    verdict: str,
    findings: Any,
    strongest_objection: str,
) -> Row:
    values: dict[str, Any] = {
        "pr_id": pr_id,
        "role": role,
        "verdict": verdict,
        "strongest_objection": strongest_objection,
        "findings": Jsonb(findings),
    }
    if model is not None:
        values["model"] = model
    return _sql.insert(conn, "reviews", values)
