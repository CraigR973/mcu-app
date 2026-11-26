"""AH1 (#397): no admin-only route opens to a viewer by accident.

AH1 opened three of the wanted list's writes to the viewer on purpose: its add, its edit and
its remove. Every other route that takes `AdminUser` is pinned here, and a viewer is sent to
each one. **A route that leaves this list, or answers a viewer with anything but 403, fails
CI.** Adding an admin route adds a line; removing one, or opening it to a viewer, is a
decision recorded in `DECISIONS.md` first, never a quiet edit to this file.

The refusal is proved without a database: `require_admin` refuses before a handler runs, so
the session handed to each route is a stand-in that nothing should touch. A route that let the
viewer through would reach it and fail with a 500, not a 403.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi.routing import APIRoute, iter_route_contexts
from httpx import ASGITransport, AsyncClient

from src.auth import get_current_user, require_admin
from src.database import get_db
from src.main import app
from src.models.profile import Profile, UserRole

#: Opened to the viewer by AH1 (#396, #397): both people add to the shared wanted list, and
#: a viewer edits and removes the wants he added.
OPENED_BY_AH1 = frozenset(
    {
        ("POST", "/api/v1/wanted"),
        ("PUT", "/api/v1/wanted/{item_id}"),
        ("DELETE", "/api/v1/wanted/{item_id}"),
    }
)

#: Every route that takes `AdminUser`, as at AH2 (26 Nov): 65 method and path pairs.
ADMIN_ROUTES = frozenset(
    {
        ("GET", "/api/v1/admin/audit"),
        ("GET", "/api/v1/attention"),
        ("DELETE", "/api/v1/attention/notes/{note_id}"),
        ("POST", "/api/v1/box-sets"),
        ("DELETE", "/api/v1/box-sets/{box_set_id}"),
        ("PUT", "/api/v1/box-sets/{box_set_id}"),
        ("POST", "/api/v1/box-sets/{box_set_id}/items"),
        ("DELETE", "/api/v1/box-sets/{box_set_id}/items/{collection_item_id}"),
        ("POST", "/api/v1/calendar/ingest"),
        ("GET", "/api/v1/cinemas/review"),
        ("POST", "/api/v1/cinemas/review/{key}"),
        ("GET", "/api/v1/collection/value/bid-trial"),
        ("POST", "/api/v1/collection/value/bid-trial"),
        ("POST", "/api/v1/collection/value/refresh"),
        ("POST", "/api/v1/collection/value/sales/refresh"),
        ("POST", "/api/v1/collection/{item_id}/photos"),
        ("POST", "/api/v1/deals/scrape"),
        ("POST", "/api/v1/deals/{deal_id}/dismiss"),
        ("GET", "/api/v1/identify/doubts"),
        ("POST", "/api/v1/identify/doubts/{doubt_id}/identify"),
        ("POST", "/api/v1/identify/films/{movie_id}/identify"),
        ("POST", "/api/v1/identify/films/{movie_id}/put-back"),
        ("POST", "/api/v1/identify/films/{movie_id}/set-aside"),
        ("POST", "/api/v1/identify/films/{movie_id}/skip"),
        ("GET", "/api/v1/identify/overview"),
        ("GET", "/api/v1/identify/queue"),
        ("GET", "/api/v1/identify/recent"),
        ("POST", "/api/v1/identify/recent/{action_id}/undo"),
        ("POST", "/api/v1/insights/completion/refresh"),
        ("POST", "/api/v1/needs-you/reviews"),
        ("GET", "/api/v1/needs-you/reviews/proposals"),
        ("GET", "/api/v1/needs-you/reviews/want-proposals"),
        ("PATCH", "/api/v1/needs-you/reviews/{review_id}/assignee"),
        ("POST", "/api/v1/needs-you/reviews/{review_id}/close"),
        ("POST", "/api/v1/needs-you/reviews/{review_id}/reopen"),
        ("POST", "/api/v1/notifications/deliver"),
        ("POST", "/api/v1/notifications/run-reminders"),
        ("POST", "/api/v1/notifications/seed-sale-seasons"),
        ("DELETE", "/api/v1/photos/{photo_id}"),
        ("POST", "/api/v1/retailers"),
        ("POST", "/api/v1/retailers/seed"),
        ("DELETE", "/api/v1/retailers/{retailer_id}"),
        ("PUT", "/api/v1/retailers/{retailer_id}"),
        ("POST", "/api/v1/scrapers/aggregate"),
        ("POST", "/api/v1/scrapers/apply-built-ins"),
        ("GET", "/api/v1/scrapers/built-in"),
        ("POST", "/api/v1/scrapers/daily"),
        ("POST", "/api/v1/scrapers/run"),
        ("GET", "/api/v1/scrapers/runs"),
        ("POST", "/api/v1/scrapers/test"),
        ("DELETE", "/api/v1/specs"),
        ("GET", "/api/v1/specs/backfill"),
        ("POST", "/api/v1/specs/backfill/run"),
        ("POST", "/api/v1/specs/fetch"),
        ("POST", "/api/v1/specs/halt"),
        ("GET", "/api/v1/specs/queue"),
        ("POST", "/api/v1/specs/queue/{lookup_id}/accept"),
        ("POST", "/api/v1/specs/queue/{lookup_id}/skip"),
        ("GET", "/api/v1/specs/state"),
        ("GET", "/api/v1/trash"),
        ("GET", "/api/v1/trash/all"),
        ("POST", "/api/v1/trash/purge"),
        ("POST", "/api/v1/trash/{table}/{item_id}/restore"),
        ("DELETE", "/api/v1/trash/{table}/{row_id}/permanent"),
        ("POST", "/api/v1/trash/{table}/{row_id}/restore-row"),
    }
)

_BODY_METHODS = {"POST", "PUT", "PATCH"}


def _needs_admin(dependant: Any) -> bool:
    return any(dep.call is require_admin or _needs_admin(dep) for dep in dependant.dependencies)


def admin_routes() -> set[tuple[str, str]]:
    """Each (method, path) whose dependencies include `require_admin`, at any depth."""
    found: set[tuple[str, str]] = set()
    for context in iter_route_contexts(app.routes):
        route = context.original_route
        if not isinstance(route, APIRoute):
            continue
        if _needs_admin(getattr(context, "dependant", None) or route.dependant):
            found.update((method, context.path) for method in (context.methods or route.methods))
    return found


def test_the_admin_only_routes_are_exactly_the_pinned_ones() -> None:
    current = admin_routes()

    assert not (ADMIN_ROUTES - current), (
        "these routes no longer take AdminUser; record the decision first: "
        f"{sorted(ADMIN_ROUTES - current)}"
    )
    assert not (current - ADMIN_ROUTES), (
        f"pin these new admin routes: {sorted(current - ADMIN_ROUTES)}"
    )
    assert OPENED_BY_AH1.isdisjoint(current)


async def test_a_viewer_is_refused_at_every_admin_only_route() -> None:
    viewer = Profile(id=uuid.uuid4(), display_name="A Viewer", pin_hash=None, role=UserRole.viewer)

    async def as_viewer() -> Profile:
        return viewer

    async def stand_in_session() -> AsyncIterator[object]:
        yield object()

    app.dependency_overrides[get_current_user] = as_viewer
    app.dependency_overrides[get_db] = stand_in_session
    let_through: list[str] = []
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for method, path in sorted(ADMIN_ROUTES):
                url = re.sub(r"\{[^}]+\}", str(uuid.UUID(int=1)), path)
                response = await client.request(
                    method, url, json={} if method in _BODY_METHODS else None
                )
                if response.status_code != 403:
                    let_through.append(f"{method} {path}: {response.status_code}")
    finally:
        app.dependency_overrides.clear()

    assert let_through == []
