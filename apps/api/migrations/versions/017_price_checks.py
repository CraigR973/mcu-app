"""create price_checks

Revision ID: 017
Revises: 016
Create Date: 2026-09-09

Roadmap §3.6 — where Batch 19's scrapers put what they find.

**§3.6's trigger is deliberately not created.** It says "a Postgres trigger runs after each
insert to evaluate whether the price is below the linked `wanted_list.max_price` — if so, a
push notification is queued". Push does not exist: no VAPID key, no subscription store, no
endpoint. That is **Batch 11**, which stops for an owner credential checkpoint, and the
alerting itself is **Batch 20**. A trigger that queued notifications into nothing would be
the same defect Batch 9 refused to ship. `notification_sent` is created and left `false`
for Batch 20 to own.

**`retailer_name_snapshot` is §3.6's own column and it earns its place.** A price check is
a historical fact — "£12.99 at HMV on the 9th" — and it stays true after the retailer row
is edited or removed. The FK is `SET NULL` for the same reason: the check outlives its
source.

**The unique index is on the listing URL and the day, not on the price.** Re-running the
job twice in an afternoon must not double-count a price, and a genuine change during the
day is more usefully an update than a second row. Batch 21's charts read these.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "017"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONDITIONS = ("new", "used", "refurbished", "unknown")
LISTING_TYPES = ("buy_it_now", "auction", "fixed_price", "unknown")


def _in_list(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(chr(39) + v + chr(39) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "price_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("wanted_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("retailer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("retailer_name_snapshot", sa.String(100), nullable=False),
        sa.Column("price", sa.Numeric(8, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GBP"),
        sa.Column("condition", sa.String(50), nullable=False, server_default="unknown"),
        sa.Column("listing_type", sa.String(50), nullable=False, server_default="unknown"),
        sa.Column("title_snapshot", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "notification_sent", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Both SET NULL: a price check is a historical fact that outlives the wanted entry
        # it was found for and the retailer it came from. `retailer_name_snapshot` is why
        # the row is still readable afterwards.
        sa.ForeignKeyConstraint(["wanted_id"], ["wanted_list.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["retailer_id"], ["retailers.id"], ondelete="SET NULL"),
        sa.CheckConstraint("price >= 0", name="ck_price_checks_price_nonnegative"),
        # A price above five figures is not a Blu-ray; it is a selector that matched the
        # wrong node. The framework rejects it before insert — this is the second line.
        sa.CheckConstraint("price < 100000", name="ck_price_checks_price_plausible"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_price_checks_currency"),
        sa.CheckConstraint(_in_list("condition", CONDITIONS), name="ck_price_checks_condition"),
        sa.CheckConstraint(
            _in_list("listing_type", LISTING_TYPES), name="ck_price_checks_listing_type"
        ),
        sa.CheckConstraint("url ~* '^https?://'", name="ck_price_checks_url_scheme"),
    )
    op.create_index("ix_price_checks_wanted_id", "price_checks", ["wanted_id"])
    op.create_index("ix_price_checks_retailer_id", "price_checks", ["retailer_id"])
    # Batch 21's charts read "this listing over time".
    op.create_index("ix_price_checks_checked_at", "price_checks", ["checked_at"])
    # One row per listing per day. Running the job twice in an afternoon must not
    # double-count, and a price that genuinely moves during the day is more usefully an
    # update than a second row.
    op.create_index(
        "uq_price_checks_listing_day",
        "price_checks",
        [sa.text("md5(url)"), sa.text("(checked_at::date)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_price_checks_listing_day", table_name="price_checks")
    op.drop_index("ix_price_checks_checked_at", table_name="price_checks")
    op.drop_index("ix_price_checks_retailer_id", table_name="price_checks")
    op.drop_index("ix_price_checks_wanted_id", table_name="price_checks")
    op.drop_table("price_checks")
