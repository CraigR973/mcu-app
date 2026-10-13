"""Wire model for the sidebar's conditional destinations — Batch S3, snag 5.

**The menu's problem was emptiness, not organisation** (`DECISIONS.md` #154). Measured
against live Neon on 2026-09-14: `box_sets` 0 rows, `smart_collections` 0,
`deals` 0, `loans` 0. Five of fourteen sidebar destinations led to a page with nothing on
it, and a menu item that leads nowhere is worse than a long menu.

So four of them are hidden **while their table is empty** and reappear the moment it is
not. That is a fact about the database, which only the API can answer — the alternative
was the client fetching four full lists on every page load to discover they were empty.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class NavSectionsResponse(BaseModel):
    """How many rows stand behind each destination that hides itself when empty.

    **Counts rather than booleans**, deliberately. A boolean answers "show this?" and
    nothing else; a count lets the sidebar show a number later without a second endpoint
    and a second round of cache invalidation, and it makes a wrong answer legible in the
    response rather than opaque.
    """

    #: Live box sets — `deleted_at IS NULL`. A soft-deleted set is in the trash, not the
    #: menu.
    boxSets: int = Field(ge=0)
    #: Smart collections belonging to **the caller**. They are per-user (`user_id` is on
    #: the row), so a shared count would show Craig a destination holding only Mark's.
    collections: int = Field(ge=0)
    #: Deals not dismissed — the same filter `GET /deals` itself applies, so the menu
    #: cannot offer a page that then renders empty.
    deals: int = Field(ge=0)
    #: Every loan, open or returned. A returned loan is history the page still shows, so
    #: "the table has rows" is the right test and `returned_date` is not consulted.
    loans: int = Field(ge=0)
