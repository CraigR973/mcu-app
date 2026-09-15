"""Soft-deleted rows across every table that has them — roadmap §13.5, §6.30.

**The permanent delete is the first irreversible operation in this application.** Every
other destructive-looking action so far has been a `deleted_at` that a restore undoes.
This one is not, so three things are true of it that are not true of anything else here:

1. **It gets past the `soft_delete` trigger through a transaction-scoped setting**, never
   `ALTER TABLE ... DISABLE TRIGGER` — that is persistent and *global*, so a process death
   between disabling and re-enabling would turn every delete in the app permanent while the
   trash kept showing an empty page. Migration `013` explains the mechanism.
2. **It refuses rather than cascades.** A film with discs or watches against it cannot be
   destroyed; Postgres' ``RESTRICT`` says so and this reports *why* rather than surfacing a
   foreign-key error.
3. **It writes its audit row before the row is gone**, in the same transaction, because
   afterwards there is nothing left to describe. `admin_actions.target_id` is TEXT with no
   foreign key precisely so the log outlives its subject (`DECISIONS.md` #5).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import Select, delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.box_set import BOX_SETS_TABLE, BoxSet
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.wanted import RETAILERS_TABLE, WANTED_LIST_TABLE, Retailer, WantedItem
from src.models.watch_log import WatchLog

#: Every table §6.30 sends to the trash, restricted to the ones that exist.
#:
#: §6.30 names "collection items, wanted entries, watch logs, and movies". All four now
#: exist: Batch 15 deliberately left ``wanted_list`` **out** rather than answering an empty
#: page for a table that did not exist, and Batch 18 built it — so it joins here, which is
#: the whole point of having refused it by name instead of silently returning nothing.
#: ``box_sets`` is Batch 12's; ``retailers`` soft-deletes too, and an accidentally removed
#: shop is exactly the kind of thing a bin is for.
TRASH_TABLES: tuple[str, ...] = (
    "collection_items",
    "watch_log",
    "movies",
    BOX_SETS_TABLE,
    WANTED_LIST_TABLE,
    RETAILERS_TABLE,
)

_MODELS: dict[str, Any] = {
    "collection_items": CollectionItem,
    "watch_log": WatchLog,
    "movies": Movie,
    BOX_SETS_TABLE: BoxSet,
    WANTED_LIST_TABLE: WantedItem,
    RETAILERS_TABLE: Retailer,
}

#: §6.30: "Items older than 90 days are auto-purged." The window is defined here; the
#: *schedule* is not — see :func:`purge_candidates`.
PURGE_AFTER = timedelta(days=90)


class PermanentDeleteRefused(Exception):
    """The row is still referenced by something that must not be destroyed with it."""


@dataclass(frozen=True)
class TrashCounts:
    table: str
    count: int


def is_trash_table(table: str) -> bool:
    return table in TRASH_TABLES


def model_for(table: str) -> Any:
    return _MODELS[table]


def deleted_rows(table: str) -> Select[Any]:
    model = model_for(table)
    return select(model).where(model.deleted_at.is_not(None))


async def counts(db: AsyncSession) -> list[TrashCounts]:
    """How many rows are in each table's bin, for the tab labels."""
    out: list[TrashCounts] = []
    for table in TRASH_TABLES:
        model = model_for(table)
        total = int(
            (
                await db.execute(select(func.count(model.id)).where(model.deleted_at.is_not(None)))
            ).scalar_one()
        )
        out.append(TrashCounts(table=table, count=total))
    return out


async def restore(db: AsyncSession, table: str, row_id: uuid.UUID) -> Any:
    """Clear ``deleted_at``. Nothing else is touched, which is what "full state" means.

    §13.5's acceptance is *"restoring brings it back with full state"* — so a restore must
    not be a re-create. Every column the row had is still there; only the tombstone is
    removed, and the derived-field triggers recompute from the values that were always
    present.
    """
    model = model_for(table)
    row = await db.get(model, row_id)
    if row is None or row.deleted_at is None:
        return None
    row.deleted_at = None
    await db.flush()
    return row


async def permanently_delete(db: AsyncSession, table: str, row_id: uuid.UUID) -> bool:
    """Destroy one soft-deleted row. **Irreversible.**

    Only a row already in the trash can be destroyed, which makes a permanent delete a
    deliberate two-step: something has to be deleted before it can be *un*-deleted-able.
    A single click that skipped straight to destruction would be one mis-tap away from
    losing a disc's history for good.
    """
    model = model_for(table)
    row = await db.get(model, row_id)
    if row is None or row.deleted_at is None:
        return False

    # A savepoint, not the whole transaction. A refusal has to undo the *attempt* and
    # nothing else — `db.rollback()` here would discard whatever else the caller had
    # already done in this transaction, including the audit row it staged a moment ago,
    # and would leave the endpoint holding a session whose contents it did not choose.
    try:
        async with db.begin_nested():
            # Transaction-scoped, so Postgres reverts it at commit *and* at rollback:
            # there is no cleanup step to forget, and no window in which anyone else's
            # delete is affected. See migration `013` for why not DISABLE TRIGGER.
            await db.execute(text("SET LOCAL app.permanent_delete = 'on'"))
            await db.execute(delete(model).where(model.id == row_id))
            # Turned off again immediately, so the flag covers exactly one statement.
            # `SET LOCAL` lasts to the end of the *transaction*, and a released savepoint
            # does not undo it — so without this line a request that permanently deleted
            # one row and then soft-deleted another in the same transaction would destroy
            # both. Nothing does that today; the point is that nothing can start to.
            await db.execute(text("SET LOCAL app.permanent_delete = 'off'"))
    except IntegrityError as exc:
        # `movies.id` is RESTRICT from both `collection_items` and `watch_log`. Saying so
        # is more useful than a foreign-key violation, and the right answer is to deal
        # with the discs first — which the trash can do.
        raise PermanentDeleteRefused(
            "This row is still referenced by discs or watch history. "
            "Permanently delete those first."
        ) from exc
    return True


async def purge_candidates(db: AsyncSession, table: str) -> list[Any]:
    """Rows deleted longer ago than :data:`PURGE_AFTER`.

    §6.30 says "items older than 90 days are auto-purged". **Nothing here is automatic.**
    A scheduled purge is a cron, which is a hosting change this project keeps explicit
    (`DECISIONS.md` #60), and a timer that permanently destroys rows is the last thing to
    add without someone deciding to. This function is what a schedule would call, and
    `/trash/purge?dryRun=true` is how to see what it would take.
    """
    model = model_for(table)
    cutoff = utcnow() - PURGE_AFTER
    return list(
        (
            await db.execute(
                select(model).where(model.deleted_at.is_not(None), model.deleted_at < cutoff)
            )
        )
        .scalars()
        .all()
    )
