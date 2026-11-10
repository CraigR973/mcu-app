"""AE4 (#355): a cinema awaiting its first enable is read for its evidence and shown to nobody.

The morning run reads only switched-on cinemas, so a new one could never earn the fresh coverage
the enable step requires. Now one on the awaiting list, off and never enabled, is read beside the
switched-on cinemas of its own source; it stays out of the views until enabled.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.admin_action import AdminAction
from src.models.cinema import CinemaVenue
from src.services.cinemas import programme
from src.services.cinemas.awaiting import awaiting_first_enable
from src.services.cinemas.domain import days_between
from src.services.cinemas.refresh import due_venues
from src.services.cinemas.venues import BY_SLUG
from tests.test_completion_sets import api_session as api_session

OMNIPLEX = BY_SLUG["omniplex-glasgow-renfrew-street"]
BRAEHEAD = BY_SLUG["odeon-braehead"]
GFT = BY_SLUG["gft"]


async def _switch(db: AsyncSession, on: set[str]) -> None:
    await db.execute(update(CinemaVenue).values(collection_enabled=CinemaVenue.slug.in_(on)))
    await db.flush()


async def test_the_omniplex_is_read_beside_a_switched_on_cinematimes_cinema(api_session):
    await _switch(api_session, {BRAEHEAD.slug, GFT.slug})
    assert await due_venues(api_session) == {BRAEHEAD.slug, GFT.slug, OMNIPLEX.slug}


async def test_nothing_on_its_source_means_it_is_not_read(api_session):
    """A refusal switches a source's cinemas off; the awaiting one is not asked either."""
    await _switch(api_session, {GFT.slug})
    assert await due_venues(api_session) == {GFT.slug}
    await _switch(api_session, set())
    assert await due_venues(api_session) == set()


async def test_once_enabled_it_is_an_ordinary_cinema(api_session):
    await _switch(api_session, {BRAEHEAD.slug, OMNIPLEX.slug})
    assert await awaiting_first_enable(api_session) == {}
    assert await due_venues(api_session) == {BRAEHEAD.slug, OMNIPLEX.slug}
    # Switched off again after an enable, it is not read again, as for any other cinema.
    api_session.add(
        AdminAction(
            id=uuid.uuid4(),
            user_id=None,
            action_type="update",
            target_table="cinema_venues",
            target_id=str(OMNIPLEX.id),
            changes={"collectionEnabled": {"from": False, "to": True}},
        )
    )
    await _switch(api_session, {BRAEHEAD.slug})
    assert await awaiting_first_enable(api_session) == {}
    assert await due_venues(api_session) == {BRAEHEAD.slug}


async def test_the_views_leave_it_out_until_it_is_enabled(api_session):
    now = utcnow()
    dates = days_between(now.date(), now.date() + timedelta(days=13))
    await _switch(api_session, {BRAEHEAD.slug})
    window = await programme.load_window(api_session, dates, now)
    assert OMNIPLEX.id not in window.known and BRAEHEAD.id in window.known
    assert len(window.known) == 9
    await _switch(api_session, {BRAEHEAD.slug, OMNIPLEX.slug})
    window = await programme.load_window(api_session, dates, now)
    assert OMNIPLEX.id in window.known and len(window.known) == 10
