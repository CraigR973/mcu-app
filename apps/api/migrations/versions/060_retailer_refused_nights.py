"""a shop's run of refusing nights, so the scheduled check can ask it weekly

Revision ID: 060
Revises: 059
Create Date: 2026-10-18

Batch X11 (MK47-05, #281). Since 30 Sep the three Shopify shops (Second Sight, 101 Films,
Powerhouse) answer Cloudflare 429s to most requests, and the nightly check waits the asked
60 seconds on each: 26-29 minutes a night against 2 before. No shop refuses *every* request
(re-measured 18 Oct), so the rule is: a night counts when the shop refused at least half of
its requests twice each, and at seven such nights in a row the scheduled check asks it once
a week, until ``OWNER-ACTIONS.md`` 28.

``refused_nights`` is that run. It starts at zero for every shop, **no live row is written**:
the three shops reach seven on the seventh scheduled check after the deploy, unless a seed is
run at Craig's word. It holds no credential; the roles already read the table, and the grant
is repeated for the column, guarded so CI's database (which has neither) still migrates.

The downgrade drops the column: every shop is asked nightly again.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "060"
down_revision: str | None = "059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "retailers",
        sa.Column("refused_nights", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_readonly') THEN "
        "GRANT SELECT (refused_nights) ON retailers TO mcu_readonly; END IF; "
        "IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_backup') THEN "
        "GRANT SELECT (refused_nights) ON retailers TO mcu_backup; END IF; END $$"
    )


def downgrade() -> None:
    op.drop_column("retailers", "refused_nights")
