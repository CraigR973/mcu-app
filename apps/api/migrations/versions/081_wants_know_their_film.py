"""AG5 (MK53-03, CT52-04): a want's shop prices are its film's, and any want can ask which film.

- ``price_checks.another_film``: why a stored listing is another film's and not the want's price
  (``year`` or ``shared_title``, ``services/scraping/extract.another_film``). Null on every
  existing row here: **no price is hidden by this migration.** The nightly shop job judges the
  stored listings by the same rule before it reads the shops (``rejudge_stored``), at the
  owner's word.
- ``assigned_reviews.wording``: a want question's own words and choices, written when it is
  assigned (amends #351). The *Dead Man's Shoes* question is given the words it was asked with,
  so it reads as before. A want question's answer may be any year; the router keeps it to the
  row's choices.

Grants are untouched: ``mcu_readonly`` and ``mcu_backup`` hold SELECT on both tables, which
covers a new column. The downgrade drops both columns and restores the two-answer check
without validating rows already answered.

Revision ID: 081
Revises: 080
Create Date: 2026-11-17
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "081"
down_revision: str | None = "080"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The words the *Dead Man's Shoes* question was asked with (``assigned_reviews.WORDS``).
DEAD_MANS_SHOES = {
    "title": "Check Dead Man's Shoes on Wanted",
    "question": "Is the wanted film Dead Man's Shoes (2004) or Dead Man's Shoes (1940)?",
    "evidence": (
        "Wanted currently names the 1940 film; the retained shop-history discrepancy "
        "was documented as the 2004 release. Your answer does not transfer any records."
    ),
    "choices": [
        {"value": "2004", "label": "Dead Man's Shoes (2004)"},
        {"value": "1940", "label": "Dead Man's Shoes (1940)"},
    ],
}

ANSWER_BEFORE = (
    "answer IS NULL OR answer = 'unsure' OR "
    "(kind = 'titanic_disc' AND answer IN ('1953', '1997')) OR "
    "(kind = 'wanted_identity' AND answer IN ('1940', '2004')) OR "
    "(kind = 'shetland_series' AND answer IN ('use_series', 'keep_separate'))"
)
ANSWER_AFTER = (
    "answer IS NULL OR answer = 'unsure' OR "
    "(kind = 'titanic_disc' AND answer IN ('1953', '1997')) OR "
    "(kind = 'wanted_identity' AND answer ~ '^(19|20)[0-9]{2}$') OR "
    "(kind = 'shetland_series' AND answer IN ('use_series', 'keep_separate'))"
)
WORDING = (
    "(kind = 'wanted_identity') = (wording IS NOT NULL) "
    "AND (wording IS NULL OR jsonb_typeof(wording) = 'object')"
)


def upgrade() -> None:
    op.add_column("price_checks", sa.Column("another_film", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_price_checks_another_film",
        "price_checks",
        "another_film IS NULL OR another_film IN ('year', 'shared_title')",
    )

    op.add_column("assigned_reviews", sa.Column("wording", postgresql.JSONB(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE assigned_reviews SET wording = CAST(:wording AS jsonb) "
            "WHERE kind = 'wanted_identity'"
        ).bindparams(wording=json.dumps(DEAD_MANS_SHOES))
    )
    op.drop_constraint("ck_assigned_review_answer", "assigned_reviews", type_="check")
    op.create_check_constraint("ck_assigned_review_answer", "assigned_reviews", ANSWER_AFTER)
    op.create_check_constraint("ck_assigned_review_wording", "assigned_reviews", WORDING)


def downgrade() -> None:
    op.drop_constraint("ck_assigned_review_wording", "assigned_reviews", type_="check")
    op.drop_constraint("ck_assigned_review_answer", "assigned_reviews", type_="check")
    op.execute(
        "ALTER TABLE assigned_reviews ADD CONSTRAINT ck_assigned_review_answer "
        f"CHECK ({ANSWER_BEFORE}) NOT VALID"
    )
    op.drop_column("assigned_reviews", "wording")
    op.drop_constraint("ck_price_checks_another_film", "price_checks", type_="check")
    op.drop_column("price_checks", "another_film")
