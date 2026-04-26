"""create gift_links and shelf_qr_codes tables

gift_links — shareable public URLs exposing a filtered view of the wanted list
so family can see what to buy for Mark. Each link has an optional expiry and
filter config (max price, genres, formats).

shelf_qr_codes — maps a printed QR code to a physical storage location (section +
shelf). Scanning in the app filters collection_items to that location.

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # gift_links — public /gift/{id} slug; id doubles as the URL slug
    # -------------------------------------------------------------------------
    op.create_table(
        "gift_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "created_by",
            PGUUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        # Optional filters: max_price, genres, formats arrays
        sa.Column("filter_config", JSONB(), server_default=sa.text("'{}'")),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "view_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_check_constraint(
        "ck_gift_links_view_count",
        "gift_links",
        "view_count >= 0",
    )

    op.create_index("idx_gift_links_created_by", "gift_links", ["created_by"])
    op.create_index("idx_gift_links_is_active", "gift_links", ["is_active"])

    # -------------------------------------------------------------------------
    # shelf_qr_codes — physical shelf mapping; id is printed on the QR label
    # -------------------------------------------------------------------------
    op.create_table(
        "shelf_qr_codes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        # Human-readable area: "Front Room", "Garage", etc.
        sa.Column("section", sa.String(100), nullable=False),
        # Shelf identifier within the section: "A1", "Top", etc.
        sa.Column("shelf", sa.String(50), nullable=False),
        sa.Column("label", sa.String(255)),
        sa.Column("printed_at", sa.TIMESTAMP(timezone=True)),
    )

    op.create_unique_constraint(
        "uq_shelf_qr_codes_section_shelf",
        "shelf_qr_codes",
        ["section", "shelf"],
    )

    op.create_index("idx_shelf_qr_codes_section", "shelf_qr_codes", ["section"])


def downgrade() -> None:
    op.drop_index("idx_shelf_qr_codes_section", table_name="shelf_qr_codes")
    op.drop_constraint("uq_shelf_qr_codes_section_shelf", "shelf_qr_codes", type_="unique")
    op.drop_table("shelf_qr_codes")

    op.drop_index("idx_gift_links_is_active", table_name="gift_links")
    op.drop_index("idx_gift_links_created_by", table_name="gift_links")
    op.drop_constraint("ck_gift_links_view_count", "gift_links", type_="check")
    op.drop_table("gift_links")
