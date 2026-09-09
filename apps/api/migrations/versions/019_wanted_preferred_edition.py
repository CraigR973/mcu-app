"""add wanted_list.preferred_edition

Revision ID: 019
Revises: 018
Create Date: 2026-09-09

**Which edition, not just which format.** `preferred_format` answers 4K vs Blu-ray vs DVD,
but a shop lists several editions *within* a format — Arrow sells Deep Red on 4K three
times over: plain, Limited Edition, and an "Arte Originale Slipcover" limited edition at
more than twice the price. Until now the want could not say which, so page order decided
and a `max_price` alert could fire on an edition nobody was waiting for.

**Free text rather than a vocabulary.** Boutique edition names are unbounded and invented
per release — "Arte Originale Slipcover", "The Film Vault Range", "Indicator Standard" —
so a fixed list would fail on exactly the cases that need it (`DECISIONS.md` #104).

**Nullable, and read by nothing that requires it.** A want with no edition behaves exactly
as it did: the first genuine disc for the film in the wanted format.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: str | None = "018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "wanted_list",
        sa.Column("preferred_edition", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wanted_list", "preferred_edition")
