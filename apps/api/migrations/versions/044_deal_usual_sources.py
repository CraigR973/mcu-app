"""where an eBay find's "usually" comes from

Revision ID: 044
Revises: 043
Create Date: 2026-10-01

Batch V8, snag 1. An eBay find's "usually" becomes the average of eBay's figure and the
shops' recent prices for the film on the format (`DECISIONS.md` #228, #237), and the card
says where it comes from ("eBay £A before postage · Zavvi £B"). ``was_price`` already holds
the average; ``deals.usual_sources`` (JSONB, nullable) holds its parts, each
``{"source": …, "price": …}``. A retailer's own deal has none: its "was" price is read off
its sale page. The read-only role reads it through its table-level grant on ``deals``.

**The upgrade writes no rows.** eBay finds stored before it keep a null, and the API reads
that as eBay's figure alone, which is what their ``was_price`` was. The downgrade drops the
column; the averages already stored in ``was_price`` stay as they are.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "044"
down_revision: str | None = "043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("usual_sources", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("deals", "usual_sources")
