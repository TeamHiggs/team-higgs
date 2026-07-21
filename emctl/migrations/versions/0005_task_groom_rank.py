"""backlog grooming: additive ordering column on tasks

Additive and reversible (PRD docs/prd/command-center.md §5). The command center
lets Tyler reorder / prioritize the backlog, but the ``tasks`` schema has no
priority/rank column, so ordering had no backing store. This adds one:

* ``groom_rank`` -- a nullable ``INTEGER`` sort key. NULL means "unranked"
  (a task Tyler has not explicitly ordered); the grooming views sort NULLs
  last, then by ``id``, so behaviour is unchanged for tasks that were never
  reordered. Smaller rank sorts first.

The column is nullable with no default, so every existing row validates without
a data migration and the CLI's task queries are unaffected. ``downgrade()``
drops the column and is round-trip tested (``tests/test_migrate.py``).

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("groom_rank", sa.Integer, nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "groom_rank")
