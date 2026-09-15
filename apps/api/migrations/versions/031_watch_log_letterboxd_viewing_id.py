"""add watch_log.letterboxd_viewing_id

Revision ID: 031
Revises: 030
Create Date: 2026-09-15

Batch S8 — snag 10b. The idempotency key for imported watch history,
`DECISIONS.md` #159, #160 and #161.

**One column serves both sources, which is the whole point.** The retrieved diary CSV
carries a `ViewingId` per row; the public RSS feed's `<guid>` is the *same* id wrapped as
`letterboxd-watch-<id>`. Storing the bare id means a viewing present in both the file and
the feed collapses to one row rather than two — which is S5's criterion, met here rather
than there, because the alternative is discovering it after 2,322 rows are already in.

**`UNIQUE (user_id, letterboxd_viewing_id)` rather than a bare unique.** A viewing belongs
to one Letterboxd account, so the id is globally unique in practice — but the constraint
that expresses the *rule* is "a person cannot have logged the same viewing twice", and it
is the one that stays correct if a third diary is ever imported.

**Partial, on `IS NOT NULL`.** Watches logged by hand in the app carry no viewing id and
never will; a plain unique index would allow exactly one such row per person.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "031"
down_revision: str | None = "030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "watch_log",
        sa.Column("letterboxd_viewing_id", sa.String(32), nullable=True),
    )
    # Digits as Letterboxd issues them. A CHECK rather than an integer column: the id is
    # an opaque identifier that happens to look numeric, and arithmetic on it would never
    # be meaningful.
    op.create_check_constraint(
        "ck_watch_log_viewing_id_digits",
        "watch_log",
        "letterboxd_viewing_id IS NULL OR letterboxd_viewing_id ~ '^[0-9]+$'",
    )
    op.create_index(
        "uq_watch_log_user_viewing",
        "watch_log",
        ["user_id", "letterboxd_viewing_id"],
        unique=True,
        postgresql_where=sa.text("letterboxd_viewing_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_watch_log_user_viewing", table_name="watch_log")
    op.drop_constraint("ck_watch_log_viewing_id_digits", "watch_log", type_="check")
    op.drop_column("watch_log", "letterboxd_viewing_id")
