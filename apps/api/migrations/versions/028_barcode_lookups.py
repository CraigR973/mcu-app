"""Remember what a barcode turned out to be — Batch 24, Phase 3.4.

§3.4's lookup chain is *"try cached mapping, then eBay/Amazon UPC search, then TMDB"*, and
this table is the first leg. It exists because the other two legs are expensive and
unreliable in different ways: eBay costs a unit of a 5,000-a-day quota and returns seller
prose, TMDB needs a title before it can help, and the risk note for this batch expects *"a
low hit rate on unknown discs and wrong-edition matches"*. A barcode a person has already
confirmed is the one answer that is certainly right, and it should never be re-derived.

**Only confirmed resolutions are written.** Nothing here is a guess: a row appears when
somebody looked at the candidates and said "yes, that one", which is the same act §3.4's
mandatory confirmation UI already requires. That keeps the cache from becoming a store of
wrong-edition matches that then look authoritative to the next scan.

**`movie_id` is nullable and `ON DELETE SET NULL`.** A confirmed barcode stays useful after
the film row is tidied away — `tmdb_id` and `title` are kept alongside precisely so the
mapping survives, the same reasoning `price_checks.retailer_name_snapshot` follows.

Revision ID: 028
Revises: 027
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "028"
down_revision: str | None = "027"
branch_labels: str | None = None
depends_on: str | None = None

#: Where a confirmed mapping came from. Recorded rather than inferred so a run of
#: wrong-edition matches can be traced to the leg that produced them.
SOURCES = ("collection", "ebay", "tmdb", "manual")


def upgrade() -> None:
    op.create_table(
        "barcode_lookups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        # EAN-13 and UPC-A are 13 and 12 digits. 32 leaves room for the ISBN-13 a
        # boxed set occasionally carries without inviting free text.
        sa.Column("barcode", sa.String(32), nullable=False),
        sa.Column("movie_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tmdb_id", sa.Integer(), nullable=True),
        #: What the disc was called when it was confirmed. Kept so the mapping reads on
        #: its own, and so it outlives the `movies` row it points at.
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column(
            "confirmed_at_utc",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("confirmed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "source IN (" + ", ".join(f"'{value}'" for value in SOURCES) + ")",
            name="ck_barcode_lookups_source",
        ),
        # A barcode identifies one product. A second row for the same code would mean
        # two answers with nothing to choose between them, which is worse than no cache.
        sa.UniqueConstraint("barcode", name="uq_barcode_lookups_barcode"),
    )


def downgrade() -> None:
    op.drop_table("barcode_lookups")
