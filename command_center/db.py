"""Request-scoped database access.

Reuses ``emctl.db.transaction`` verbatim: one psycopg transaction per request,
committed when the handler returns cleanly and rolled back if it raises. This
is the same connection/transaction lifecycle the CLI uses -- the API adds no
data-access machinery of its own. ``emctl.config.database_url`` remains the one
place ``DATABASE_URL`` is read.
"""

from __future__ import annotations

from collections.abc import Iterator

from emctl.db import Conn, transaction


def get_conn() -> Iterator[Conn]:
    """FastAPI dependency yielding a transactional connection.

    On handler success FastAPI resumes this generator, exiting the ``with`` and
    committing; on handler error the exception is thrown back in at the yield,
    so ``transaction`` rolls back and ``map_db_errors`` translates any psycopg
    error into a typed :class:`emctl.errors.EmctlError`.
    """
    with transaction() as conn:
        yield conn
