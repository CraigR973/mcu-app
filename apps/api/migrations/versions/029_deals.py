"""Discounted discs found on retailers' own sale pages — Batch 22, Phase 5.9.

Net-new: `deals` did not exist, which was verified against live Neon on 2026-09-11 and
again on 2026-09-12.

**Three columns carry the batch's whole risk note.** §5.9's risk is that *"a deals page
that changes layout does not error — it selects the wrong node and stores a plausible
wrong discount, which then feeds the feed"*. `price` and `was_price` are stored
separately and `discount_percent` is **derived from them by the application, never taken
from the page**, so the number in the feed is arithmetic on two figures that each had to
pass a shape check rather than a badge somebody's CSS happened to match.

**`first_seen_at_utc` and `last_seen_at_utc` rather than one timestamp.** A deal is a
thing that persists across runs, and the interesting facts are "how long has this been on
offer" and "is it still there". One `created_at` answers neither, and a run that deleted
and reinserted would lose the first answer every night.

**Uniqueness is `(retailer_id, url)`.** A sale page lists one product once; the URL is
what identifies it across runs. Keying on title instead would merge two editions whose
titles a shop writes identically, and keying on movie_id would merge the 4K with the
Blu-ray.

**`dismissed_at_utc` is a soft state, not a delete.** §5.10's acceptance is *"dismissed
items don't reappear"* — which has to survive the next scrape re-finding the same deal, so
the row must remember the dismissal rather than being removed and re-created.

Revision ID: 029
Revises: 028
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "029"
down_revision: str | None = "028"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "deals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        # `SET NULL` and a snapshot beside it, exactly as `price_checks` does: a deal is a
        # historical fact — "£9.99 at Zavvi on the 12th" — and stays readable after the
        # retailer row is edited or removed.
        sa.Column("retailer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("retailer_name_snapshot", sa.String(100), nullable=False),
        # Null until the title is matched to a film. A deal nobody could match is still
        # worth keeping — it is the evidence that the matcher needs work, and hiding it
        # would make a broken matcher look like a quiet sale page.
        sa.Column("movie_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tmdb_id", sa.Integer(), nullable=True),
        sa.Column("title_snapshot", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("format_code", sa.String(20), nullable=True),
        sa.Column("price", sa.Numeric(8, 2), nullable=False),
        sa.Column("was_price", sa.Numeric(8, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GBP"),
        # Derived by the application from the two prices above — never read off the page.
        sa.Column("discount_percent", sa.Integer(), nullable=True),
        sa.Column(
            "first_seen_at_utc",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at_utc",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("dismissed_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("dismissed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["retailer_id"], ["retailers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["dismissed_by"], ["profiles.id"], ondelete="SET NULL"),
        # A negative or absurd discount is a selector reading the wrong node. The
        # application refuses these before they get here (`check_deal_shape`); the
        # constraint is what makes that true of every writer, including a future one.
        sa.CheckConstraint(
            "discount_percent IS NULL OR (discount_percent > 0 AND discount_percent < 100)",
            name="ck_deals_discount_percent",
        ),
        sa.CheckConstraint("price >= 0", name="ck_deals_price_non_negative"),
        sa.CheckConstraint(
            "was_price IS NULL OR was_price > price", name="ck_deals_was_price_higher"
        ),
        sa.UniqueConstraint("retailer_id", "url", name="uq_deals_retailer_url"),
    )

    # "What is on offer right now?" — the feed's only query shape, newest discount first.
    op.create_index(
        "ix_deals_active",
        "deals",
        ["dismissed_at_utc", sa.text("last_seen_at_utc DESC")],
    )
    # "Do I already own this?" and §5.10's genre filter both join through the film.
    op.create_index("ix_deals_movie", "deals", ["movie_id"])


def downgrade() -> None:
    op.drop_index("ix_deals_movie", table_name="deals")
    op.drop_index("ix_deals_active", table_name="deals")
    op.drop_table("deals")
