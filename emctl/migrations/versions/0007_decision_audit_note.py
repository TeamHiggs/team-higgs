"""command center: decision-audit note on prs and decisions

Additive and reversible (PRD docs/prd/command-center.md §7). Tyler's rationale
for an approve/reject is the audit trail for the irreversible merge-to-main
action, so it must be persisted for every decidable kind -- not silently
discarded. ``artifacts`` already carries this on its ``notes`` column; this
migration gives the two remaining kinds the same inline, nullable field:

* ``prs.tyler_note``       -- rationale recorded when Tyler decides a PR;
* ``decisions.tyler_note`` -- rationale recorded when Tyler accepts/reverses.

A nullable column (not a new table) is the cleaner fit here: these rows are
current-state projections already mutated in place by their ``decide``/``update``
path, and keeping the note beside the decision keeps one consistent write path
across all three approval kinds rather than fragmenting where a rationale lives.

``emctl_report_ro`` (migration 0002) reads these tables through the existing
table-level SELECT grant; a new column on an already-granted table inherits it,
so no grant change is needed. ``downgrade()`` drops both columns and is
round-trip tested (``tests/test_migrate.py``).

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("prs", sa.Column("tyler_note", sa.Text, nullable=True))
    op.add_column("decisions", sa.Column("tyler_note", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("decisions", "tyler_note")
    op.drop_column("prs", "tyler_note")
