"""spec search again — how many discs a batch searched again, and how many that settled

Revision ID: 039
Revises: 038
Create Date: 2026-09-26

Batch T10. A disc searched under the spreadsheet's misspelt title is searched once more after
its film is identified, and the batch records how many it searched again and how many of
those the matcher accepted. Both are counts on a batch that has finished, so the downgrade
loses only that tally.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "039"
down_revision: str | None = "038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "spec_runs",
        sa.Column("searched_again", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "spec_runs",
        sa.Column("settled_again", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("spec_runs", "settled_again")
    op.drop_column("spec_runs", "searched_again")
