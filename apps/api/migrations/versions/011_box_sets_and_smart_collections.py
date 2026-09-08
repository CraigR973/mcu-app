"""create box_sets, box_set_items and smart_collections

Revision ID: 011
Revises: 010
Create Date: 2026-09-08

Roadmap §3.23, §3.24 and §3.25 — the tables behind Batch 12's phases 11.3, 11.4 and 11.5.

**This migration creates empty tables and backfills nothing.** 627 live items carry a
``sub_category`` and it is tempting to turn the 30-odd values matching /box|vol|set/ into
box sets automatically. It would be wrong: the same column also holds "Clint Eastwood"
(64 items) and "Hitchcock" (30), which are groupings of a person's work rather than boxes,
and no regex separates "Criterion Collection" the publisher from "Evil Dead Trilogy Box
Set" the object. §11.3's acceptance is *"Admin creates …"* precisely because the judgement
is a person's. ``sub_category`` is left untouched and un-read.

Two shapes differ from the §3.24/§3.25 tables as drawn, both deliberate:

**``box_sets.deleted_at``.** §3.24 lists no soft delete. Added for the house convention
and because the row groups real discs — an accidental delete of a 20-item set should be
recoverable. §13.5's Trash does not surface them yet; widening ``TRASH_TABLES`` belongs
to Batch 15.

**``updated_at`` on both new parents.** §3.23/§3.24 list only ``created_at``. Every other
table here carries both, and ``009``'s ``set_updated_at`` trigger is what makes an edit
distinguishable from the row's creation.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Kept in step with :data:`src.models.smart_collection.SMART_COLLECTION_ICONS`. The
#: CHECK constraint is the enforcement; the API validator is the good error message.
ICONS = (
    "sparkles",
    "star",
    "heart",
    "clapperboard",
    "disc",
    "eye",
    "flame",
    "bookmark",
    "layers",
)


def _in_list(column: str, values: Sequence[str]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    op.create_table(
        "box_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column("volume_number", sa.Integer(), nullable=True),
        sa.Column("series_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expected_count", sa.Integer(), nullable=True),
        sa.Column("poster_url", sa.Text(), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=False), nullable=True),
        sa.ForeignKeyConstraint(["series_id"], ["box_sets.id"], ondelete="SET NULL"),
        # A box sold with zero or a negative number of films is not a fact about any
        # box; it is a typo that would then render as "3 of 0".
        sa.CheckConstraint(
            "expected_count IS NULL OR expected_count > 0",
            name="ck_box_sets_expected_count_positive",
        ),
        sa.CheckConstraint(
            "series_id IS NULL OR series_id <> id",
            name="ck_box_sets_series_not_self",
        ),
    )
    op.create_index("ix_box_sets_series_id", "box_sets", ["series_id"])
    op.create_index("ix_box_sets_deleted_at", "box_sets", ["deleted_at"])
    # The grid view's only ordering: live sets, by name.
    op.create_index(
        "ix_box_sets_live_name",
        "box_sets",
        [sa.text("lower(name)")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "box_set_items",
        sa.Column("box_set_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("disc_number", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("box_set_id", "collection_item_id"),
        sa.ForeignKeyConstraint(["box_set_id"], ["box_sets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["collection_item_id"], ["collection_items.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "disc_number IS NULL OR disc_number > 0",
            name="ck_box_set_items_disc_number_positive",
        ),
    )
    # "Which sets is this disc in?" — asked once per copy on the film detail page.
    op.create_index("ix_box_set_items_collection_item_id", "box_set_items", ["collection_item_id"])

    op.create_table(
        "smart_collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("icon", sa.String(50), nullable=False, server_default="sparkles"),
        sa.Column(
            "filters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("sort_by", sa.String(50), nullable=False, server_default="title"),
        sa.Column("sort_order", sa.String(10), nullable=False, server_default="asc"),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.CheckConstraint(_in_list("icon", ICONS), name="ck_smart_collections_icon"),
        sa.CheckConstraint(
            _in_list("sort_by", ("title", "year", "rating")),
            name="ck_smart_collections_sort_by",
        ),
        sa.CheckConstraint(
            _in_list("sort_order", ("asc", "desc")),
            name="ck_smart_collections_sort_order",
        ),
        # The filters column is a query, not a document. An array or a scalar would
        # break the evaluator at read time rather than at write time.
        sa.CheckConstraint(
            "jsonb_typeof(filters) = 'object'",
            name="ck_smart_collections_filters_object",
        ),
        # Two collections with the same name in one sidebar are indistinguishable.
        sa.UniqueConstraint("user_id", "name", name="uq_smart_collections_user_name"),
    )
    op.create_index("ix_smart_collections_user_id", "smart_collections", ["user_id"])
    # The sidebar's ordering, and the dashboard's subset of it.
    op.create_index(
        "ix_smart_collections_user_order",
        "smart_collections",
        ["user_id", "display_order"],
    )

    # `009` moved this to clock_timestamp() so two writes in one transaction differ.
    for table in ("box_sets", "smart_collections"):
        op.execute(
            f"""
            CREATE TRIGGER {table}_set_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
            """
        )


def downgrade() -> None:
    for table in ("box_sets", "smart_collections"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_set_updated_at ON {table};")
    op.drop_index("ix_smart_collections_user_order", table_name="smart_collections")
    op.drop_index("ix_smart_collections_user_id", table_name="smart_collections")
    op.drop_table("smart_collections")
    op.drop_index("ix_box_set_items_collection_item_id", table_name="box_set_items")
    op.drop_table("box_set_items")
    op.drop_index("ix_box_sets_live_name", table_name="box_sets")
    op.drop_index("ix_box_sets_deleted_at", table_name="box_sets")
    op.drop_index("ix_box_sets_series_id", table_name="box_sets")
    op.drop_table("box_sets")
