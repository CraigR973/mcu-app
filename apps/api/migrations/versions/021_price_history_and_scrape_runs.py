"""create price_history_daily and scrape_runs

Revision ID: 021
Revises: 020
Create Date: 2026-09-10

Batch 20 — roadmap §5.5, §5.6 and §5.8.

**`price_history_daily` is §3.18 as designed.** Raw `price_checks` older than 90 days roll
into one row per day per (wanted item, retailer) carrying min/max/avg and a count, and the
raw rows are then deleted. It keeps the table lean without losing the trend Batch 21's
charts draw.

**`scrape_runs` is not in the April spec, and 5.5 cannot be checked without it.** The
corrected acceptance (`DECISIONS.md` #112) reads *"the same-day row count is ≈ (attempted
pairs − not-stocked pairs) within a ≤ 10% failure margin, with every failure logged with
its retailer and reason"* — three numbers and a list that, until now, existed only inside
one HTTP response and were discarded when it was sent. On 2026-09-09 a scraper "test"
displayed results while saving nothing and nobody could tell afterwards; a run that writes
down what it did is the answer to that, and it is also the only way *"first overnight run
completes"* is answerable the morning after.

**`failures` is JSONB rather than a child table.** It is a list read as a whole, only ever
by a person looking at one run, and it never needs to be joined or aggregated. A child
table would buy nothing and cost a migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "021"
down_revision: str | None = "020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_history_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        # `SET NULL` to match `price_checks`: an aggregate is a historical fact and stays
        # true after the want is removed or the retailer edited.
        sa.Column("wanted_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("retailer_id", postgresql.UUID(as_uuid=True), nullable=True),
        # Carried for the same reason `price_checks` carries it — the row stays readable
        # once the foreign key is null, which for 90-day-old data is the likely case.
        sa.Column("retailer_name_snapshot", sa.String(100), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("min_price", sa.Numeric(8, 2), nullable=False),
        sa.Column("max_price", sa.Numeric(8, 2), nullable=False),
        sa.Column("avg_price", sa.Numeric(8, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GBP"),
        sa.Column("check_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["wanted_id"], ["wanted_list.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["retailer_id"], ["retailers.id"], ondelete="SET NULL"),
        sa.CheckConstraint("check_count > 0", name="ck_price_history_daily_check_count"),
        # An aggregate whose minimum exceeds its maximum is arithmetically impossible, so
        # it can only mean the roll-up wrote the columns in the wrong order — the kind of
        # mistake that is invisible in a chart and obvious to a constraint.
        sa.CheckConstraint(
            "min_price <= avg_price AND avg_price <= max_price",
            name="ck_price_history_daily_ordering",
        ),
    )
    # The aggregation is idempotent because of this index: re-running it for a day that is
    # already rolled up conflicts rather than doubling the history.
    op.create_index(
        "uq_price_history_daily_day",
        "price_history_daily",
        ["wanted_id", "retailer_id", "date"],
        unique=True,
    )
    op.create_index(
        "ix_price_history_daily_wanted_date", "price_history_daily", ["wanted_id", "date"]
    )

    op.create_table(
        "scrape_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("started_at_utc", sa.DateTime(timezone=False), nullable=False),
        # NULL while a run is in flight. A run that never finishes is then visible as
        # exactly that, rather than as an absent row indistinguishable from "never ran".
        sa.Column("finished_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        # The five counts the corrected §5.5 criterion is stated in.
        sa.Column("attempted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("not_stocked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("written", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alerts_queued", sa.Integer(), nullable=False, server_default="0"),
        # `[{"retailer": ..., "reason": ...}]` — §5.5's "failures logged with retailer +
        # reason", kept where it can be read the morning after rather than only in a log.
        sa.Column(
            "failures",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "disabled_retailers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint("trigger IN ('cron', 'manual')", name="ck_scrape_runs_trigger"),
        sa.CheckConstraint("jsonb_typeof(failures) = 'array'", name="ck_scrape_runs_failures"),
        sa.CheckConstraint(
            "jsonb_typeof(disabled_retailers) = 'array'", name="ck_scrape_runs_disabled"
        ),
    )
    op.create_index("ix_scrape_runs_started_at", "scrape_runs", ["started_at_utc"])


def downgrade() -> None:
    op.drop_index("ix_scrape_runs_started_at", table_name="scrape_runs")
    op.drop_table("scrape_runs")
    op.drop_index("ix_price_history_daily_wanted_date", table_name="price_history_daily")
    op.drop_index("uq_price_history_daily_day", table_name="price_history_daily")
    op.drop_table("price_history_daily")
