"""add profiles.streaming_region

Revision ID: 014
Revises: 013
Create Date: 2026-09-09

Roadmap §7.1 asks for watch providers that are "region-aware (user's streaming_region)" —
and no such column exists. `collection_items.region_code` is a **different thing**: it is
the disc's Blu-ray region (A/B/C), a property of a physical object, not of a person's
streaming subscriptions.

Defaulted to ``GB``, which is where both people are and what §7.1's own acceptance
criterion assumes ("UK streaming options shown correctly"). A column rather than a
constant because the value belongs to a person — the app already personalises watched
status per profile, and streaming availability is the same kind of fact.

Two characters, ISO 3166-1 alpha-2, which is what TMDB's ``watch/providers`` keys its
``results`` map by. A CHECK keeps a lower-cased or three-letter value out, because TMDB
answers a wrong key with an empty map rather than an error — the film would simply appear
to be streaming nowhere.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "streaming_region",
            sa.String(2),
            nullable=False,
            server_default="GB",
        ),
    )
    op.create_check_constraint(
        "ck_profiles_streaming_region",
        "profiles",
        "streaming_region ~ '^[A-Z]{2}$'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_profiles_streaming_region", "profiles", type_="check")
    op.drop_column("profiles", "streaming_region")
