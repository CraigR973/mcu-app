"""make soft_delete skippable, and create loans

Revision ID: 013
Revises: 012
Create Date: 2026-09-09

Two things for Batch 15: §3.8's `loans` table, and the one change that makes §13.5's
permanent delete possible **safely**.

**Why `soft_delete()` needs changing at all.** `003` created a BEFORE DELETE trigger on
`collection_items` that rewrites every `DELETE` into `UPDATE ... SET deleted_at`. That is
what makes the trash work, and it means a permanent delete cannot simply issue a `DELETE` —
the row would come back soft-deleted, and the endpoint would report success having
destroyed nothing.

**Why not `ALTER TABLE ... DISABLE TRIGGER`.** That is what Batch 7's audit test does, and
it is correct *in a test*. In a request handler it is dangerous: `DISABLE TRIGGER` is
**persistent and global**, not session-scoped. If the process died between disabling and
re-enabling — a deploy, an OOM, an unhandled exception on the row in between — the trigger
would stay off for **every session**, and every subsequent delete anywhere in the app would
silently become permanent. The trash would keep showing an empty page while discs vanished.

**What this does instead.** The function now returns early when a transaction-scoped
setting says so:

    SET LOCAL app.permanent_delete = 'on';
    DELETE FROM collection_items WHERE id = ...;

`SET LOCAL` reverts at commit **and at rollback**, by Postgres, with no cleanup step to
forget. There is no window in which the trigger is off for anyone else, and a crash
mid-transaction rolls back the setting and the delete together. `current_setting(..., true)`
returns NULL rather than raising when the setting was never set, so every ordinary delete
takes the soft path unchanged.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The transaction-scoped flag the permanent-delete path sets. Named with the ``app.``
#: prefix Postgres requires for a custom GUC.
PERMANENT_DELETE_SETTING = "app.permanent_delete"

_SOFT_DELETE_SKIPPABLE = """
CREATE OR REPLACE FUNCTION soft_delete()
RETURNS TRIGGER AS $$
BEGIN
    -- `true` = "missing is not an error". Every ordinary delete reaches here with the
    -- setting unset, gets NULL, and takes the soft path exactly as before.
    IF current_setting('app.permanent_delete', true) = 'on' THEN
        RETURN OLD;
    END IF;
    EXECUTE format(
        'UPDATE %I SET deleted_at = (NOW() AT TIME ZONE ''utc'') '
        'WHERE id = $1 AND deleted_at IS NULL',
        TG_TABLE_NAME
    ) USING OLD.id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""

_SOFT_DELETE_ORIGINAL = """
CREATE OR REPLACE FUNCTION soft_delete()
RETURNS TRIGGER AS $$
BEGIN
    EXECUTE format(
        'UPDATE %I SET deleted_at = (NOW() AT TIME ZONE ''utc'') '
        'WHERE id = $1 AND deleted_at IS NULL',
        TG_TABLE_NAME
    ) USING OLD.id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(_SOFT_DELETE_SKIPPABLE)

    op.create_table(
        "loans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("collection_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_name", sa.String(255), nullable=False),
        sa.Column("lent_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("returned_date", sa.Date(), nullable=True),
        sa.Column("reminder_sent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # CASCADE: a loan of a disc that no longer exists is not a fact about anything.
        # The disc is soft-deleted in the ordinary case, so this only fires on the
        # permanent-delete path this same migration makes possible.
        sa.ForeignKeyConstraint(
            ["collection_item_id"], ["collection_items.id"], ondelete="CASCADE"
        ),
        # A disc cannot come back before it went out.
        sa.CheckConstraint(
            "returned_date IS NULL OR returned_date >= lent_date",
            name="ck_loans_returned_after_lent",
        ),
        sa.CheckConstraint(
            "due_date IS NULL OR due_date >= lent_date",
            name="ck_loans_due_after_lent",
        ),
    )
    op.create_index("ix_loans_collection_item_id", "loans", ["collection_item_id"])
    # "What is out right now?" — the loans page's only real query, and the one the
    # overdue check runs. Partial on open loans because that is the only set it asks for.
    op.create_index(
        "ix_loans_open",
        "loans",
        ["due_date"],
        postgresql_where=sa.text("returned_date IS NULL"),
    )
    # One open loan per disc. Without this, lending the same disc twice by mistake gives
    # two people a claim on one object and no way to tell which is real.
    op.create_index(
        "uq_loans_one_open_per_item",
        "loans",
        ["collection_item_id"],
        unique=True,
        postgresql_where=sa.text("returned_date IS NULL"),
    )
    op.execute(
        """
        CREATE TRIGGER loans_set_updated_at
        BEFORE UPDATE ON loans
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS loans_set_updated_at ON loans;")
    op.drop_index("uq_loans_one_open_per_item", table_name="loans")
    op.drop_index("ix_loans_open", table_name="loans")
    op.drop_index("ix_loans_collection_item_id", table_name="loans")
    op.drop_table("loans")
    op.execute(_SOFT_DELETE_ORIGINAL)
