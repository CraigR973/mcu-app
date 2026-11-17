"""AG4 (CR49-02, CT52-02): every fact found for a film is stamped with the film it was found for.

Six stores gain ``found_for``, not null: ``film_reviews``, ``disc_valuations``,
``ebay_used_listings``, ``ebay_used_scans``, ``ebay_price_refs`` and ``spec_lookups``. It holds
what the film was when the row was found: ``film:<TMDB id>``, ``tv:<TMDB series id>`` or ``none``
(``services/found_for.identity``). A row whose stamp is not its film now is forgotten and looked
up again (``services/found_for.py``), which retires #378's and #380's audit rule and the disc
values' time rule.

**The backfill stamps each existing row with its film as it is now** (a disc page lookup, with
its copy's film), except a row the retired rules already judge to answer another film, which is
stamped ``stale`` so the first sweep looks it up again:

- found before the film's latest correction (an ``identify`` or ``undo_identify`` audit that is
  not a merge), as #378 and #380 judged it: by when a review was found, a value or usual price
  or used-listing search was checked, a used listing last seen, or a page lookup decided or
  searched; a lookup a person decided is theirs and is stamped as it stands;
- a page lookup on a copy moved since the lookup was decided or searched (``move_copy`` or its
  undo, audited on the copy), which no rule reached before AG4 (CT52-02).

No row is deleted here; the sweep forgets at its next run. Grants are untouched: ``mcu_readonly``
and ``mcu_backup`` hold SELECT on each table, which covers a new column. The downgrade drops the
six columns.

Revision ID: 080
Revises: 079
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "080"
down_revision: str | None = "079"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: What a film is, in SQL, for the movies row aliased ``m`` (``services/found_for.identity``).
IDENTITY = (
    "CASE WHEN m.tmdb_id IS NOT NULL THEN 'film:' || m.tmdb_id "
    "WHEN m.tmdb_tv_id IS NOT NULL THEN 'tv:' || m.tmdb_tv_id ELSE 'none' END"
)

#: Never a film's identity, so the first sweep forgets it.
STALE = "stale"

#: Each film's latest correction, as #378 and #380 read it: not a merge.
CORRECTIONS = """
    SELECT target_id AS movie_id, max(created_at) AS corrected
    FROM admin_actions
    WHERE target_table = 'movies'
      AND changes->>'kind' IN ('identify', 'undo_identify')
      AND changes->'merge' IS NULL
    GROUP BY target_id
"""

#: Each copy's latest move, or the undo of one.
MOVES = """
    SELECT target_id AS item_id, max(created_at) AS moved
    FROM admin_actions
    WHERE target_table = 'collection_items'
      AND changes->>'kind' IN ('move_copy', 'undo_move_copy')
    GROUP BY target_id
"""

#: The film-keyed stores, and the time each row was found.
FILM_STORES = {
    "film_reviews": "found_utc",
    "disc_valuations": "checked_utc",
    "ebay_used_listings": "last_seen_utc",
    "ebay_used_scans": "checked_utc",
    "ebay_price_refs": "checked_utc",
}


def upgrade() -> None:
    for table, found in FILM_STORES.items():
        op.add_column(table, sa.Column("found_for", sa.Text(), nullable=True))
        op.execute(
            f"UPDATE {table} t SET found_for = {IDENTITY} FROM movies m WHERE m.id = t.movie_id"
        )
        op.execute(
            f"UPDATE {table} t SET found_for = '{STALE}' FROM ({CORRECTIONS}) c "
            f"WHERE c.movie_id = t.movie_id::text AND t.{found} < c.corrected"
        )
        op.alter_column(table, "found_for", nullable=False)

    op.add_column("spec_lookups", sa.Column("found_for", sa.Text(), nullable=True))
    op.execute(
        f"UPDATE spec_lookups l SET found_for = {IDENTITY} "
        "FROM collection_items ci JOIN movies m ON m.id = ci.movie_id "
        "WHERE ci.id = l.collection_item_id"
    )
    when = "coalesce(l.decided_utc, l.searched_utc, l.created_utc)"
    op.execute(
        f"UPDATE spec_lookups l SET found_for = '{STALE}' "
        f"FROM collection_items ci, ({CORRECTIONS}) c "
        "WHERE ci.id = l.collection_item_id AND c.movie_id = ci.movie_id::text "
        f"AND l.decided_by IS NULL AND {when} < c.corrected"
    )
    op.execute(
        f"UPDATE spec_lookups l SET found_for = '{STALE}' FROM ({MOVES}) mv "
        "WHERE mv.item_id = l.collection_item_id::text AND l.decided_by IS NULL "
        f"AND {when} < mv.moved"
    )
    op.alter_column("spec_lookups", "found_for", nullable=False)


def downgrade() -> None:
    for table in (*FILM_STORES, "spec_lookups"):
        op.drop_column(table, "found_for")
