"""make collection item source-row lookup apply to live rows only

Revision ID: 034
Revises: 033
Create Date: 2026-09-16

Batch 39 replaces the collection by soft-deleting every live item and importing the
new spreadsheet in the same transaction.  Migration 004's partial unique index excludes
NULL source rows, but still includes soft-deleted rows.  That means the importer's
live-row duplicate check can correctly find no conflict while Postgres rejects the insert
anyway.

Replace the unique index with a live-row lookup index.  The importer is the only writer of
non-NULL source rows and performs the duplicate check in the same item transaction.  The
index cannot stay unique among live rows: §13.5 promises that restoring a complete old row
only clears its tombstone, including when a replacement now owns the same spreadsheet row.
That restore can temporarily leave both discs live; the user can then keep or delete the
replacement after comparing them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "034"
down_revision: str | None = "033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("uq_collection_items_import_source_row", table_name="collection_items")
    op.create_index(
        "ix_collection_items_live_import_source_row",
        "collection_items",
        ["import_source_row"],
        unique=False,
        postgresql_where=sa.text("import_source_row IS NOT NULL AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_collection_items_live_import_source_row", table_name="collection_items")
    op.create_index(
        "uq_collection_items_import_source_row",
        "collection_items",
        ["import_source_row"],
        unique=True,
        postgresql_where=sa.text("import_source_row IS NOT NULL"),
    )
