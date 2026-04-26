"""create smart_collections, box_sets, and box_set_items tables

smart_collections — user-defined dynamic filter sets evaluated at query time
(like iTunes smart playlists). No materialisation — results update as the
collection changes.

box_sets — physical box sets grouping multiple collection_items under one label
(e.g. "Kubrick Box Set", "Columbia Noir Vol 4"). Self-FK series_id links volumes
in a series.

box_set_items — junction table between box_sets and collection_items with an
optional disc_number for ordering within the set.

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

_SORT_ORDER = ("asc", "desc")


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # smart_collections — filter criteria stored as JSONB; no rows cached
    # -------------------------------------------------------------------------
    op.create_table(
        "smart_collections",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        # Lucide icon name for the sidebar
        sa.Column("icon", sa.String(50)),
        # Criteria: format, genre, decade, watched_status, hdr, runtime, etc.
        sa.Column("filters", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("sort_by", sa.String(50)),
        sa.Column(
            "sort_order",
            sa.String(10),
            server_default=sa.text("'asc'"),
        ),
        sa.Column(
            "is_pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_check_constraint(
        "ck_smart_collections_sort_order",
        "smart_collections",
        f"sort_order IS NULL OR sort_order IN {_SORT_ORDER}",
    )

    op.create_index("idx_smart_collections_user_id", "smart_collections", ["user_id"])
    op.create_index(
        "idx_smart_collections_user_pinned",
        "smart_collections",
        ["user_id", "is_pinned", "display_order"],
    )

    # -------------------------------------------------------------------------
    # box_sets — one row per physical box set or volume in a series
    # -------------------------------------------------------------------------
    op.create_table(
        "box_sets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        # Publisher / boutique label
        sa.Column("label", sa.String(100)),
        sa.Column("volume_number", sa.Integer()),
        # Self-FK: links this volume to sibling volumes in the same series
        sa.Column(
            "series_id",
            sa.BigInteger(),
            sa.ForeignKey("box_sets.id", ondelete="SET NULL"),
        ),
        sa.Column("expected_count", sa.Integer()),
        sa.Column("poster_url", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_check_constraint(
        "ck_box_sets_expected_count",
        "box_sets",
        "expected_count IS NULL OR expected_count > 0",
    )

    op.create_index("idx_box_sets_series_id", "box_sets", ["series_id"])

    # -------------------------------------------------------------------------
    # box_set_items — composite PK junction; disc_number for ordering
    # -------------------------------------------------------------------------
    op.create_table(
        "box_set_items",
        sa.Column(
            "box_set_id",
            sa.BigInteger(),
            sa.ForeignKey("box_sets.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "collection_item_id",
            sa.BigInteger(),
            sa.ForeignKey("collection_items.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("disc_number", sa.Integer()),
    )

    op.create_index(
        "idx_box_set_items_collection_item_id",
        "box_set_items",
        ["collection_item_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_box_set_items_collection_item_id", table_name="box_set_items")
    op.drop_table("box_set_items")

    op.drop_index("idx_box_sets_series_id", table_name="box_sets")
    op.drop_constraint("ck_box_sets_expected_count", "box_sets", type_="check")
    op.drop_table("box_sets")

    op.drop_index("idx_smart_collections_user_pinned", table_name="smart_collections")
    op.drop_index("idx_smart_collections_user_id", table_name="smart_collections")
    op.drop_constraint("ck_smart_collections_sort_order", "smart_collections", type_="check")
    op.drop_table("smart_collections")
