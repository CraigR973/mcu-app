"""an edition the spec job inferred says so, until a person confirms it

Revision ID: 058
Revises: 057
Create Date: 2026-10-16

Batch X9, CT46-05. On 12 Oct all 146 copies with an edition had it from the spec job ("the
one UK edition the search found", #220), none from a person, and 16 named a SteelBook the
sheet mentions nowhere. ``collection_items.edition_source`` says how an edition was inferred
from the copy's Blu-ray.com page: ``only_uk_edition`` (the search found no other UK edition
of the film on that format), ``chosen`` (Craig chose the page from the list) or ``pasted``.
Null is an edition a person typed or confirmed. The copy page reads "probably …" while it is
set.

**The backfill marks only what the spec job wrote.** An edition is marked when its copy's
disc page is settled and no audit row shows a person setting that edition, on adding the
copy or editing it: the job writes editions without an audit row, a person never does.
Which kind is read from how the page was settled.

Granted to both read-only roles, guarded so CI's database (which has neither) still
migrates. It holds no credential.

The downgrade drops the column: every edition reads as the copy's again.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "058"
down_revision: str | None = "057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKFILL = """
UPDATE collection_items ci
SET edition_source = CASE sl.how
    WHEN 'confirmed' THEN 'chosen'
    WHEN 'pasted' THEN 'pasted'
    ELSE 'only_uk_edition'
END
FROM spec_lookups sl
WHERE sl.collection_item_id = ci.id
  AND sl.status = 'done'
  AND ci.edition IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM admin_actions a
      WHERE a.target_table = 'collection_items'
        AND a.target_id = ci.id::text
        AND (
            a.changes -> 'edition' ->> 'to' = ci.edition
            OR (a.action_type = 'create' AND a.changes ->> 'edition' = ci.edition)
        )
  )
"""


def upgrade() -> None:
    op.add_column("collection_items", sa.Column("edition_source", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_collection_items_edition_source",
        "collection_items",
        "edition_source IS NULL OR edition_source IN ('only_uk_edition', 'chosen', 'pasted')",
    )
    op.create_check_constraint(
        "ck_collection_items_edition_source_has_edition",
        "collection_items",
        "edition_source IS NULL OR edition IS NOT NULL",
    )
    op.execute(BACKFILL)
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_readonly') THEN "
        "GRANT SELECT (edition_source) ON collection_items TO mcu_readonly; END IF; "
        "IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_backup') THEN "
        "GRANT SELECT (edition_source) ON collection_items TO mcu_backup; END IF; END $$"
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_collection_items_edition_source_has_edition", "collection_items", type_="check"
    )
    op.drop_constraint("ck_collection_items_edition_source", "collection_items", type_="check")
    op.drop_column("collection_items", "edition_source")
