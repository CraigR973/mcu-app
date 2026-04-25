"""create collection_items table

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reusable soft-delete trigger function — intercepts DELETE and converts it to
    # UPDATE SET deleted_at = NOW(), keeping the row for audit purposes.
    op.execute("""
        CREATE OR REPLACE FUNCTION soft_delete()
        RETURNS TRIGGER AS $$
        BEGIN
            EXECUTE format(
                'UPDATE %I SET deleted_at = NOW() WHERE id = $1 AND deleted_at IS NULL',
                TG_TABLE_NAME
            ) USING OLD.id;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.create_table(
        "collection_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "movie_id",
            sa.Integer(),
            sa.ForeignKey("movies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # Physical details
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("edition", sa.Text()),
        sa.Column("condition", sa.Text(), nullable=False),
        sa.Column("region", sa.Text()),
        # Purchase info
        sa.Column("purchase_price", sa.Numeric(10, 2)),
        sa.Column("purchase_date", sa.Date()),
        sa.Column("purchase_source", sa.Text()),
        sa.Column("barcode", sa.Text()),
        sa.Column("notes", sa.Text()),
        # AV specs
        sa.Column("resolution", sa.Text()),
        sa.Column("video_codec", sa.Text()),
        sa.Column("hdr_format", sa.Text()),
        sa.Column("audio_formats", ARRAY(sa.Text())),
        sa.Column("aspect_ratio", sa.Text()),
        # Photos
        sa.Column("cover_photo_url", sa.Text()),
        sa.Column("back_photo_url", sa.Text()),
        sa.Column("disc_photos", ARRAY(sa.Text())),
        sa.Column("extra_photos", ARRAY(sa.Text())),
        # Listing / for-sale
        sa.Column("is_for_sale", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("asking_price", sa.Numeric(10, 2)),
        sa.Column("listing_url", sa.Text()),
        sa.Column("listed_at", sa.TIMESTAMP(timezone=True)),
        # Soft delete & timestamps
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_check_constraint(
        "ck_collection_items_format",
        "collection_items",
        "format IN ('4k_bluray', 'bluray', 'dvd', 'digital', 'laserdisc', 'vhs', 'hddvd')",
    )
    op.create_check_constraint(
        "ck_collection_items_condition",
        "collection_items",
        "condition IN ('sealed', 'mint', 'very_good', 'good', 'fair', 'poor')",
    )
    op.create_check_constraint(
        "ck_collection_items_asking_price",
        "collection_items",
        "asking_price IS NULL OR is_for_sale = TRUE",
    )

    op.create_index("idx_collection_items_movie_id", "collection_items", ["movie_id"])
    op.create_index(
        "idx_collection_items_for_sale",
        "collection_items",
        ["is_for_sale", "deleted_at"],
    )
    op.create_index("idx_collection_items_deleted_at", "collection_items", ["deleted_at"])
    op.create_index("idx_collection_items_format", "collection_items", ["format"])

    op.execute("""
        CREATE TRIGGER collection_items_set_updated_at
        BEFORE UPDATE ON collection_items
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)

    op.execute("""
        CREATE TRIGGER collection_items_soft_delete
        BEFORE DELETE ON collection_items
        FOR EACH ROW EXECUTE FUNCTION soft_delete();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS collection_items_soft_delete ON collection_items;")
    op.execute("DROP TRIGGER IF EXISTS collection_items_set_updated_at ON collection_items;")
    op.drop_index("idx_collection_items_format", table_name="collection_items")
    op.drop_index("idx_collection_items_deleted_at", table_name="collection_items")
    op.drop_index("idx_collection_items_for_sale", table_name="collection_items")
    op.drop_index("idx_collection_items_movie_id", table_name="collection_items")
    op.drop_constraint("ck_collection_items_asking_price", "collection_items", type_="check")
    op.drop_constraint("ck_collection_items_condition", "collection_items", type_="check")
    op.drop_constraint("ck_collection_items_format", "collection_items", type_="check")
    op.drop_table("collection_items")
    op.execute("DROP FUNCTION IF EXISTS soft_delete;")
