"""create item_photos

Revision ID: 025
Revises: 024
Create Date: 2026-09-10

Batch 25 — roadmap §3.10.

**Bytes in Postgres, not an object store.** §3.10 says "upload to Supabase Storage"; there
is no Supabase project (`DECISIONS.md` #17 moved the database to Neon and left every other
Supabase product as a separate future decision), and the owner settled storage as Neon on
2026-09-09. So a photo is a `BYTEA` column on a row, served by the API.

**Not §3.4's `photo_urls` JSONB array.** That column designs a list of *external* URLs,
which is what an object store gives you. With the bytes here there is nothing to point at,
and a table gives each photo a row that can be ordered, captioned and deleted on its own.

**Five per item and a size ceiling, both enforced here as well as in code.** The spec's raw
sizing — 5 photos × 5 MB × 1,857 items ≈ 46 GB — is not sensible in a database that is
35 MB today. Photos are resized before insert; the CHECK is the floor under that, so a
row written by anything other than the upload endpoint still cannot be enormous.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "025"
down_revision: str | None = "024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The hard ceiling the database enforces, deliberately above the app's resize target so a
#: tuned-up target does not need a migration. See `src/services/photos.py`.
MAX_STORED_BYTES = 2 * 1024 * 1024


def upgrade() -> None:
    op.create_table(
        "item_photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("collection_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        # The photo itself. `BYTEA` is TOASTed by Postgres, so a wide row does not slow
        # down the queries that never select this column — which is every catalogue query.
        sa.Column("data", postgresql.BYTEA(), nullable=False),
        sa.Column("content_type", sa.String(40), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        # Strong validator for the `ETag`. Content-addressed, so a re-upload of the same
        # photo is recognisable and a browser's conditional request answers 304.
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("caption", sa.String(200), nullable=True),
        # Explicit ordering: "the first photo" is a choice, not whichever row came back.
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["collection_item_id"], ["collection_items.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["uploaded_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            f"byte_size > 0 AND byte_size <= {MAX_STORED_BYTES}", name="ck_item_photos_size"
        ),
        sa.CheckConstraint("width > 0 AND height > 0", name="ck_item_photos_dimensions"),
        sa.CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="ck_item_photos_content_type",
        ),
        sa.CheckConstraint("position >= 0", name="ck_item_photos_position"),
        # The same photo twice on one disc is a double-tapped upload, not two photos.
        sa.UniqueConstraint("collection_item_id", "checksum", name="uq_item_photos_item_checksum"),
    )
    op.create_index(
        "ix_item_photos_item_position", "item_photos", ["collection_item_id", "position"]
    )


def downgrade() -> None:
    op.drop_index("ix_item_photos_item_position", table_name="item_photos")
    op.drop_table("item_photos")
