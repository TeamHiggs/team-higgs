"""command center: append-only notes table

Additive and reversible (PRD docs/prd/command-center.md §5). One new ``notes``
entity for Tyler's own thoughts, consistent with the platform's append-only
event-log posture: rows are only ever inserted, never updated or deleted. Text
only -- no blob storage (decision #20).

Columns follow the repo pattern (an id PK, the domain field, an ``author`` /
``context`` for who wrote it and from where, an immutable ``created_at``):

* ``id``         -- surrogate PK;
* ``body``       -- the note text (required);
* ``author``     -- who wrote it (the authenticated email; nullable for CLI use);
* ``context``    -- optional free-text context (e.g. a surface or project ref);
* ``created_at`` -- immutable insert timestamp.

``emctl_report_ro`` (migration 0002) reads this table through that migration's
``ALTER DEFAULT PRIVILEGES ... GRANT SELECT ON TABLES``: ``notes`` is created by
the same migrating role, so the default grant covers it. ``downgrade()`` drops
the table and its index and is round-trip tested (``tests/test_migrate.py``).

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("author", sa.Text),
        sa.Column("context", sa.Text),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Notes list newest-first; index the sort key to keep that read cheap.
    op.create_index("idx_notes_created_at", "notes", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_notes_created_at", table_name="notes")
    op.drop_table("notes")
