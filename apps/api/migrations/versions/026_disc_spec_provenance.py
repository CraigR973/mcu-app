"""add spec provenance to collection_items, and the specs-integration halt state

Revision ID: 026
Revises: 025
Create Date: 2026-09-10

Batch 23 — roadmap §3.7, §3.8 and §3.9.

**The spec columns already exist.** `video_specs`, `audio_specs`, `special_features`,
`region_code` and `release_label` landed with Batch 4's schema. What is missing is
everything `DECISIONS.md` #110 requires *around* them.

**Provenance is not optional here, it is a condition of the risk acceptance.** #110: *"Every
derived row records its Blu-ray.com source URL and fetch time so the data can be identified
and removed."* That sentence is why `specs_source_url` and `specs_fetched_at_utc` exist —
without them "delete everything derived from that site" is not a query anyone can write,
and deletion is an explicit owner action the acceptance depends on.

**`specs_integration_state` is the stop condition, made durable.** #110: a `403`, a `429`,
an explicit objection or a hosting complaint *"halts the whole integration; resuming after
any of those requires a new owner decision."* A halt held in memory would be forgotten on
the next deploy, which is precisely the promise that must not be broken. One row, read
before every fetch.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "026"
down_revision: str | None = "025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "collection_items",
        sa.Column("specs_source_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "collection_items",
        sa.Column("specs_fetched_at_utc", sa.DateTime(timezone=False), nullable=True),
    )
    # "Which rows came from Blu-ray.com" has to be one index scan, because the question is
    # asked when somebody wants them all gone.
    op.create_index(
        "ix_collection_items_specs_source",
        "collection_items",
        ["specs_fetched_at_utc"],
        postgresql_where=sa.text("specs_source_url IS NOT NULL"),
    )

    op.create_table(
        "specs_integration_state",
        # A single row, pinned by the CHECK below. A settings table that can grow a second
        # row grows one eventually, and then "is it halted?" has two answers.
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("halted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("halted_reason", sa.Text(), nullable=True),
        sa.Column("halted_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_fetch_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("fetch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("id = 1", name="ck_specs_integration_singleton"),
        sa.CheckConstraint("fetch_count >= 0", name="ck_specs_integration_fetch_count"),
        # Halted means somebody must be able to read *why*, months later, before deciding
        # whether resuming is allowed.
        sa.CheckConstraint(
            "NOT halted OR (halted_reason IS NOT NULL AND halted_at_utc IS NOT NULL)",
            name="ck_specs_integration_halt_has_reason",
        ),
    )
    op.execute("INSERT INTO specs_integration_state (id, halted, fetch_count) VALUES (1, false, 0)")


def downgrade() -> None:
    op.drop_table("specs_integration_state")
    op.drop_index("ix_collection_items_specs_source", table_name="collection_items")
    op.drop_column("collection_items", "specs_fetched_at_utc")
    op.drop_column("collection_items", "specs_source_url")
