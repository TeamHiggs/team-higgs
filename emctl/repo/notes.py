"""notes table (append-only).

Rows are only ever inserted -- never updated or deleted -- matching the
platform's event-log posture (migration 0006). Shared by the command-center
API; the CLI may grow a ``note`` surface later on the same functions.
"""

from __future__ import annotations

from typing import Any

from psycopg import sql

from emctl.db import Conn
from emctl.repo import _sql

Row = _sql.Row


def add(
    conn: Conn, *, body: str, author: str | None, context: str | None
) -> Row:
    values: dict[str, Any] = {"body": body}
    if author is not None:
        values["author"] = author
    if context is not None:
        values["context"] = context
    return _sql.insert(conn, "notes", values)


def list_(conn: Conn) -> list[Row]:
    """All notes, newest first (append-only, so no projection is needed)."""
    query = sql.SQL(
        "SELECT * FROM notes ORDER BY created_at DESC, id DESC"
    )
    return list(conn.execute(query).fetchall())
