"""an eBay find's condition and sample, and the scan's one look at the Wanted list

Revision ID: 049
Revises: 048
Create Date: 2026-10-12

Batch X1, "eBay: unblind the scan, name the right disc, say how fresh". Three nullable
columns:

- ``deals.listing_condition``: the listing's own condition ("Very good"), so the Deals card
  and the push name what is for sale, not only the film it was filed under. Cleared, with the
  listing's title and image, once an eBay find expires (eBay API licence §8.1.2, §3.1(b)).
- ``deals.usual_listings``: how many asking prices stand behind an eBay find's usual price,
  for "asking prices, 12 listings".
- ``ebay_watch_runs.wanted_searched``: how many Wanted films a pass searched one by one. Set
  by the first pass after X1 only, which searched each once to recover what the blind scan of
  9–12 Oct missed; a pass with it set means no later pass does it again.

**Nothing to backfill:** a shop's deal has no condition or sample, and an eBay find stored
before X1 reads as it did. The read-only role's grants on both tables are table-level, so they
cover the new columns; nothing in them is a credential.

The downgrade drops the three columns; the deals and runs themselves stay.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "049"
down_revision: str | None = "048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("listing_condition", sa.Text(), nullable=True))
    op.add_column("deals", sa.Column("usual_listings", sa.Integer(), nullable=True))
    op.add_column("ebay_watch_runs", sa.Column("wanted_searched", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("ebay_watch_runs", "wanted_searched")
    op.drop_column("deals", "usual_listings")
    op.drop_column("deals", "listing_condition")
