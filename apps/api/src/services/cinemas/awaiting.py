"""Cinemas awaiting their first enable — AE4 (#355).

The enable step (`refresh.set_enabled`) switches a cinema on only with fresh accepted coverage,
and the morning run used to read only cinemas already on, so a new cinema could never earn it.
A cinema on this list, off, and never enabled before (no enabling entry in `admin_actions`) is
therefore read by the morning run, but only alongside cinemas already on from the same source,
so a source whose cinemas a refusal switched off is not asked again. Until it is enabled it
stays out of every view and the daily digest: reading it gives the enable step its evidence and
nobody sees its films early. Once enabled it is an ordinary cinema; if it is ever switched off
again it is not read again, as for any other.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.admin_action import AdminAction
from src.models.cinema import CinemaVenue
from src.services.cinemas.venues import BY_SLUG, Venue

#: Approved cinemas not yet switched on: the Omniplex on Renfrew Street (AE4, #355).
AWAITING_FIRST_ENABLE = frozenset({"omniplex-glasgow-renfrew-street"})


async def awaiting_first_enable(db: AsyncSession) -> dict[uuid.UUID, Venue]:
    """The listed cinemas that are off and have never been switched on."""
    listed = [BY_SLUG[slug] for slug in sorted(AWAITING_FIRST_ENABLE) if slug in BY_SLUG]
    if not listed:
        return {}
    off = set(
        (
            await db.scalars(
                select(CinemaVenue.id).where(
                    CinemaVenue.id.in_([venue.id for venue in listed]),
                    CinemaVenue.deleted_at.is_(None),
                    CinemaVenue.collection_enabled.is_(False),
                )
            )
        ).all()
    )
    if not off:
        return {}
    enabled_before = set(
        (
            await db.scalars(
                select(AdminAction.target_id).where(
                    AdminAction.target_table == "cinema_venues",
                    AdminAction.target_id.in_([str(venue_id) for venue_id in off]),
                    AdminAction.changes["collectionEnabled"]["to"].astext == "true",
                )
            )
        ).all()
    )
    return {
        venue.id: venue
        for venue in listed
        if venue.id in off and str(venue.id) not in enabled_before
    }
