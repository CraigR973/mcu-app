"""AG6's live data step: stored deal pushes lose ended listings' words, and both people get
the agreed quiet hours — at the owner's word.

Since AG6 each eBay find's pushes are rewritten in the film's words when the find ends
(`services/ebay_watch/runs.py`, ``forget_pushed_listings``, MK53-06). Push rows stored before
AG6 belong to finds that ended earlier, so the pass never reaches them: 544 of 580 on 25 Nov.
This rewrites those, and only those. And quiet hours of 22:00–07:00 are the default for a new
person since AG6 (#383); a person whose row holds none is given them here, as both agreed on
24 Nov. Either can change or clear them in Settings afterwards.

**First a dry run, which writes nothing:**

    PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.deal_pushes_owner_step

**Then, at Craig's word and with the counts he saw,**
``--apply --expect-pushes N --expect-people M``. It refuses unless exactly those counts qualify
when it runs. One transaction.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.database import AsyncSessionLocal
from src.models.notification import (
    DEFAULT_QUIET_HOURS_END,
    DEFAULT_QUIET_HOURS_START,
    NotificationPreference,
)
from src.models.profile import Profile
from src.services.ebay_watch.runs import (
    forget_pushed_listings,
    pushes_to_forget,
    stored_ended_finds,
)


async def people_without_quiet_hours(db: AsyncSession) -> list[NotificationPreference]:
    """Live people whose preferences hold no quiet hours."""
    return list(
        (
            await db.scalars(
                select(NotificationPreference)
                .join(Profile, Profile.id == NotificationPreference.user_id)
                .where(
                    Profile.deleted_at.is_(None),
                    NotificationPreference.quiet_hours_start.is_(None),
                    NotificationPreference.quiet_hours_end.is_(None),
                )
            )
        ).all()
    )


async def counts(db: AsyncSession) -> tuple[int, int, int]:
    """Push rows to rewrite, the ended finds they belong to, and people without quiet hours."""
    ended = await stored_ended_finds(db, now=utcnow())
    return (
        await pushes_to_forget(db, ended),
        len(ended),
        len(await people_without_quiet_hours(db)),
    )


async def apply(db: AsyncSession, *, expect_pushes: int, expect_people: int) -> str | None:
    """Both writes in the caller's transaction, or a refusal. Commits nothing itself."""
    ended = await stored_ended_finds(db, now=utcnow())
    people = await people_without_quiet_hours(db)
    pushes = await pushes_to_forget(db, ended)
    if (pushes, len(people)) != (expect_pushes, expect_people):
        return (
            f"Refused: {pushes} push rows and {len(people)} people qualify, "
            f"{expect_pushes} and {expect_people} expected. Nothing written."
        )
    changed = await forget_pushed_listings(db, ended)
    if changed != expect_pushes:
        return f"Refused: {changed} push rows changed, {expect_pushes} expected."
    for preference in people:
        preference.quiet_hours_start = DEFAULT_QUIET_HOURS_START
        preference.quiet_hours_end = DEFAULT_QUIET_HOURS_END
    await db.flush()
    return None


async def main_async(*, write: bool, expect_pushes: int | None, expect_people: int | None) -> int:
    async with AsyncSessionLocal() as db:
        # The first statement of its transaction, as Postgres requires.
        await db.execute(text("SET TRANSACTION READ ONLY"))
        pushes, finds, people = await counts(db)
        await db.rollback()
    print(f"{pushes} stored deal push rows to rewrite, from {finds} ended eBay finds")
    print(f"{people} people with no quiet hours, to be given 22:00–07:00")
    if not write:
        return 0
    assert expect_pushes is not None and expect_people is not None
    async with AsyncSessionLocal() as db:
        refused = await apply(db, expect_pushes=expect_pushes, expect_people=expect_people)
        if refused:
            await db.rollback()
            print(refused, file=sys.stderr)
            return 3
        await db.commit()
    print(f"{expect_pushes} push rows rewritten; {expect_people} people given quiet hours")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0] if __doc__ else "")
    parser.add_argument("--apply", action="store_true", help="Write; without it, a dry run")
    parser.add_argument("--expect-pushes", type=int, help="With --apply: the dry run's push rows")
    parser.add_argument("--expect-people", type=int, help="With --apply: the dry run's people")
    args = parser.parse_args(argv)
    if args.apply and (args.expect_pushes is None or args.expect_people is None):
        parser.error("--apply needs --expect-pushes N and --expect-people M from the dry run")
    return asyncio.run(
        main_async(
            write=args.apply, expect_pushes=args.expect_pushes, expect_people=args.expect_people
        )
    )


if __name__ == "__main__":
    sys.exit(main())
