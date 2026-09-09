"""Batch 13's completion sets — roadmap §11.1 and §11.2.

Structured by acceptance criterion:

- §11.1 — *"Refresh job runs live against TMDB and populates `completion_sets` with ≥ 20
  sets (directors, franchises, awards); Hitchcock set lists every Hitchcock film TMDB
  returns; re-running after a TMDB change updates the affected rows."*
- §11.2 — *"Opening Insights shows ≥ 20 sets with owned/missing counts"*

**The TMDB half is a fake here and live in the batch report.** The criterion says "runs
live against TMDB", which a test suite must not do: a test that depends on a third party
fails for reasons that have nothing to do with the code, and TMDB's answer for Hitchcock
changes whenever someone edits it. The live run is a verification step recorded in
`STATUS.md`; what is pinned here is everything that decides *which* of TMDB's answers
become members, because that is where a wrong denominator would come from and it would
look entirely plausible.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.completion_set import CompletionSet
from src.models.movie import Movie, MovieCredit
from src.models.profile import Profile, UserRole
from src.routers.movies import get_tmdb_client
from src.services.completion import (
    candidate_people,
    refresh_sets,
)
from src.tmdb.models import PersonMovieCredit, PersonMovieCredits

pytestmark = pytest.mark.asyncio

ACTOR_HEADER = "x-test-actor"

#: Hitchcock's real TMDB person id, as it appears in this collection's own credits.
HITCHCOCK = 2636


def _credit(
    tmdb_id: int,
    title: str,
    *,
    year: str | None = "1958",
    job: str | None = None,
    order: int | None = None,
    votes: int | None = 100,
) -> PersonMovieCredit:
    return PersonMovieCredit(
        id=tmdb_id,
        title=title,
        release_date=year,
        poster_path=f"/{tmdb_id}.jpg",
        vote_count=votes,
        job=job,
        order=order,
    )


# ---------------------------------------------------------------------------
# Database-backed: candidates, refresh, insights
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def api_session(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()


async def _profile(session: AsyncSession, role: UserRole) -> Profile:
    profile = Profile(
        id=uuid.uuid4(),
        display_name=f"Batch Thirteen {role.value.title()} {uuid.uuid4().hex[:8]}",
        pin_hash=None,
        role=role,
    )
    session.add(profile)
    await session.flush()
    return profile


@pytest_asyncio.fixture
async def admin(api_session: AsyncSession) -> Profile:
    return await _profile(api_session, UserRole.admin)


@pytest_asyncio.fixture
async def viewer(api_session: AsyncSession) -> Profile:
    return await _profile(api_session, UserRole.viewer)


class FakePersonClient:
    """Stands in for TMDB. Records what it was asked, so a test can assert one call per set.

    ``on_unknown`` decides what happens for a person the test did not stub. Both behaviours
    are needed and the distinction is not cosmetic: a run against **live Neon** sees the
    real catalogue's 117 directors, not just the fixture's, so a test that wants to assert
    "no errors" has to say what the others do. ``"empty"`` makes them skipped rows;
    ``"raise"`` is for the test that deliberately exercises the failure path.
    """

    def __init__(
        self,
        filmographies: dict[int, PersonMovieCredits],
        *,
        on_unknown: str = "raise",
    ) -> None:
        self._filmographies = filmographies
        self._on_unknown = on_unknown
        self.calls: list[int] = []

    async def get_person_movie_credits(
        self, person_id: int, language: str = "en-US"
    ) -> PersonMovieCredits:
        del language
        self.calls.append(person_id)
        if person_id not in self._filmographies:
            if self._on_unknown == "empty":
                return PersonMovieCredits(id=person_id)
            raise RuntimeError(f"TMDB has nothing for {person_id}")
        return self._filmographies[person_id]


@pytest_asyncio.fixture
async def overrides(
    api_session: AsyncSession, admin: Profile, viewer: Profile
) -> AsyncIterator[None]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield api_session

    async def override_user(request: Request) -> Profile:
        return admin if request.headers.get(ACTOR_HEADER) == "admin" else viewer

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        yield
    finally:
        app.dependency_overrides.clear()


def _client_as(actor: str) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={ACTOR_HEADER: actor},
    )


@pytest_asyncio.fixture
async def client(overrides: None) -> AsyncIterator[AsyncClient]:
    del overrides
    async with _client_as("admin") as http_client:
        yield http_client


@pytest_asyncio.fixture
async def viewer_client(overrides: None) -> AsyncIterator[AsyncClient]:
    del overrides
    async with _client_as("viewer") as http_client:
        yield http_client


async def _owned_film(
    session: AsyncSession,
    *,
    tmdb_id: int,
    title: str,
    director: tuple[int, str] | None = None,
) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        media_type="film",
        year=1958,
    )
    session.add(movie)
    await session.flush()
    session.add(
        CollectionItem(id=uuid.uuid4(), movie_id=movie.id, formats=["blu_ray"], condition="good")
    )
    if director is not None:
        session.add(
            MovieCredit(
                id=uuid.uuid4(),
                movie_id=movie.id,
                person_name=director[1],
                tmdb_person_id=director[0],
                role="director",
            )
        )
    await session.flush()
    return movie


async def _a_collector_of(
    session: AsyncSession, person: tuple[int, str], tmdb_ids: list[int]
) -> None:
    for index, tmdb_id in enumerate(tmdb_ids):
        await _owned_film(
            session, tmdb_id=tmdb_id, title=f"{person[1]} Film {index}", director=person
        )


async def test_candidates_come_from_the_collections_own_credits(
    api_session: AsyncSession,
) -> None:
    """No names are typed and no TMDB search is run.

    The person id came from the film's own credits when it was identified, so there is no
    matching step to get wrong — which matters, because gotcha 1b is the record of what
    fuzzy TMDB matching did to this app once already.
    """
    person = (9_000_001, "A Prolific Director")
    await _a_collector_of(api_session, person, [9_100_001, 9_100_002, 9_100_003])

    candidates = await candidate_people(api_session, limit_per_type=200)
    mine = [c for c in candidates if c.tmdb_person_id == person[0]]
    assert len(mine) == 1
    assert mine[0].set_type == "director"
    assert mine[0].owned_count == 3


async def test_someone_with_too_few_owned_films_is_not_a_set(
    api_session: AsyncSession,
) -> None:
    """ "You own 1 of 42" is noise, not an insight."""
    person = (9_000_002, "A Director With Two Films Here")
    await _a_collector_of(api_session, person, [9_100_011, 9_100_012])

    candidates = await candidate_people(api_session, limit_per_type=200)
    assert not [c for c in candidates if c.tmdb_person_id == person[0]]


async def test_an_unidentified_film_never_counts_towards_a_set(
    api_session: AsyncSession,
) -> None:
    """It has no TMDB id, so it can never match a filmography.

    Counting it would overstate the owned side of every set it appears in — the number
    would be too high and nothing would say so.
    """
    person = (9_000_003, "A Director With One Unidentified")
    await _a_collector_of(api_session, person, [9_100_021, 9_100_022, 9_100_023])
    unidentified = Movie(
        id=uuid.uuid4(),
        tmdb_id=None,
        title="A Shelf Title Only",
        original_title="A Shelf Title Only",
        media_type="film",
    )
    api_session.add(unidentified)
    await api_session.flush()
    api_session.add(CollectionItem(id=uuid.uuid4(), movie_id=unidentified.id, formats=["dvd"]))
    api_session.add(
        MovieCredit(
            id=uuid.uuid4(),
            movie_id=unidentified.id,
            person_name=person[1],
            tmdb_person_id=person[0],
            role="director",
        )
    )
    await api_session.flush()

    candidates = await candidate_people(api_session, limit_per_type=200)
    mine = next(c for c in candidates if c.tmdb_person_id == person[0])
    assert mine.owned_count == 3


async def test_refresh_creates_sets_then_updates_them_in_place(
    api_session: AsyncSession,
) -> None:
    """§11.1's third clause — "re-running after a TMDB change updates the affected rows".

    Run twice against two different TMDB answers. The second run must edit the row rather
    than add a second Hitchcock, which is what the `(set_type, set_key)` unique constraint
    exists to guarantee.
    """
    person = (9_000_004, "A Director Whose Filmography Grows")
    await _a_collector_of(api_session, person, [9_100_031, 9_100_032, 9_100_033])

    before = PersonMovieCredits(
        id=person[0],
        crew=[_credit(9_100_031, "One", job="Director"), _credit(9_100_099, "Two", job="Director")],
    )
    first = await refresh_sets(
        api_session, FakePersonClient({person[0]: before}), limit_per_type=200
    )
    assert first.created >= 1

    row = (
        await api_session.execute(
            select(CompletionSet).where(CompletionSet.set_key == str(person[0]))
        )
    ).scalar_one()
    assert row.member_tmdb_ids == [9_100_031, 9_100_099]
    first_refreshed = row.last_refreshed

    after = PersonMovieCredits(
        id=person[0],
        crew=[
            _credit(9_100_031, "One", job="Director"),
            _credit(9_100_099, "Two", job="Director"),
            _credit(9_100_100, "A Newly Added Film", year="1962", job="Director"),
        ],
    )
    second = await refresh_sets(
        api_session, FakePersonClient({person[0]: after}), limit_per_type=200
    )
    assert second.updated >= 1

    rows = (
        (
            await api_session.execute(
                select(CompletionSet).where(CompletionSet.set_key == str(person[0]))
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, "a second run must edit the row, not add another"
    assert rows[0].member_tmdb_ids == [9_100_031, 9_100_099, 9_100_100]
    assert rows[0].last_refreshed is not None and first_refreshed is not None


async def test_a_dry_run_reads_tmdb_and_writes_nothing(api_session: AsyncSession) -> None:
    person = (9_000_005, "A Director Nobody Commits")
    await _a_collector_of(api_session, person, [9_100_041, 9_100_042, 9_100_043])
    fake = FakePersonClient(
        {
            person[0]: PersonMovieCredits(
                id=person[0], crew=[_credit(9_100_041, "One", job="Director")]
            )
        }
    )

    result = await refresh_sets(api_session, fake, limit_per_type=200, dry_run=True)

    assert result.created >= 1
    assert fake.calls, "a dry run still asks TMDB — that is what makes it a rehearsal"
    assert (
        await api_session.execute(
            select(CompletionSet).where(CompletionSet.set_key == str(person[0]))
        )
    ).scalar_one_or_none() is None


async def test_one_persons_failure_does_not_abandon_the_rest(
    api_session: AsyncSession,
) -> None:
    """A refresh that gave up on the 25th person would leave 24 good sets unwritten."""
    good = (9_000_006, "A Director TMDB Knows")
    bad = (9_000_007, "A Director TMDB Breaks On")
    await _a_collector_of(api_session, good, [9_100_051, 9_100_052, 9_100_053])
    await _a_collector_of(api_session, bad, [9_100_061, 9_100_062, 9_100_063])

    fake = FakePersonClient(
        {good[0]: PersonMovieCredits(id=good[0], crew=[_credit(9_100_051, "One", job="Director")])}
    )
    result = await refresh_sets(api_session, fake, limit_per_type=200)

    assert result.created >= 1
    assert any(str(bad[0]) in message for message in result.errors)
    assert (
        await api_session.execute(
            select(CompletionSet).where(CompletionSet.set_key == str(good[0]))
        )
    ).scalar_one_or_none() is not None


async def test_a_person_with_no_releasable_films_is_skipped(
    api_session: AsyncSession,
) -> None:
    """ "You own 3 of 0" is worse than not showing the set."""
    person = (9_000_008, "A Director Of Nothing Released")
    await _a_collector_of(api_session, person, [9_100_071, 9_100_072, 9_100_073])
    fake = FakePersonClient(
        {
            person[0]: PersonMovieCredits(
                id=person[0], crew=[_credit(1, "Unreleased", year=None, job="Director")]
            )
        }
    )

    result = await refresh_sets(api_session, fake, limit_per_type=200)

    assert result.skipped >= 1
    assert (
        await api_session.execute(
            select(CompletionSet).where(CompletionSet.set_key == str(person[0]))
        )
    ).scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# §11.2 — the insights surface
# ---------------------------------------------------------------------------


async def _a_set(
    session: AsyncSession, key: str, name: str, member_ids: list[int]
) -> CompletionSet:
    row = CompletionSet(
        id=uuid.uuid4(),
        set_type="director",
        set_key=key,
        set_name=name,
        member_tmdb_ids=member_ids,
        set_metadata={
            "members": [
                {"tmdbId": m, "title": f"Film {m}", "year": 1958, "posterPath": f"/{m}.jpg"}
                for m in member_ids
            ]
        },
    )
    session.add(row)
    await session.flush()
    return row


async def test_insights_reports_owned_and_missing_per_set(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """§11.2's acceptance: sets with owned/missing counts."""
    await _owned_film(api_session, tmdb_id=9_200_001, title="Owned One")
    await _owned_film(api_session, tmdb_id=9_200_002, title="Owned Two")
    row = await _a_set(
        api_session,
        "9000010",
        "A Half-Owned Director",
        [9_200_001, 9_200_002, 9_200_003, 9_200_004],
    )

    response = await client.get("/api/v1/insights/completion")
    assert response.status_code == 200, response.text
    mine = next(s for s in response.json()["items"] if s["id"] == str(row.id))
    assert (mine["ownedCount"], mine["totalCount"], mine["missingCount"]) == (2, 4, 2)
    assert mine["percentComplete"] == 50


async def test_the_detail_view_names_the_films_you_are_missing(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """A missing film has no row in this database, so its poster comes from the cache."""
    owned = await _owned_film(api_session, tmdb_id=9_200_011, title="On The Shelf")
    row = await _a_set(api_session, "9000011", "A Director", [9_200_011, 9_200_012])

    response = await client.get(f"/api/v1/insights/completion/{row.id}")
    assert response.status_code == 200, response.text
    films = {f["tmdbId"]: f for f in response.json()["films"]}

    assert films[9_200_011]["owned"] is True
    assert films[9_200_011]["movieId"] == str(owned.id)
    assert films[9_200_012]["owned"] is False
    assert films[9_200_012]["movieId"] is None
    # The poster for a film nobody owns, with no TMDB call at read time.
    assert films[9_200_012]["posterPath"] == "/9200012.jpg"


async def test_a_member_with_no_cached_display_row_still_counts(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """Dropping it would shrink the denominator the counts above are computed from."""
    row = CompletionSet(
        id=uuid.uuid4(),
        set_type="director",
        set_key="9000012",
        set_name="A Set Refreshed By An Older Job",
        member_tmdb_ids=[9_200_021, 9_200_022],
        set_metadata={},
    )
    api_session.add(row)
    await api_session.flush()

    response = await client.get(f"/api/v1/insights/completion/{row.id}")
    assert response.status_code == 200
    assert response.json()["totalCount"] == 2
    assert len(response.json()["films"]) == 2


async def test_soft_deleting_the_last_copy_moves_the_count(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    """Nothing is stored about ownership, so it follows the collection with no job to run."""
    movie = await _owned_film(api_session, tmdb_id=9_200_031, title="A Film About To Go")
    row = await _a_set(api_session, "9000013", "A Director", [9_200_031, 9_200_032])

    before = await client.get(f"/api/v1/insights/completion/{row.id}")
    assert before.json()["ownedCount"] == 1

    movie.deleted_at = datetime(2026, 9, 9)
    await api_session.flush()

    after = await client.get(f"/api/v1/insights/completion/{row.id}")
    assert after.json()["ownedCount"] == 0


async def test_a_viewer_can_read_insights_but_not_refresh_them(
    viewer_client: AsyncClient, api_session: AsyncSession
) -> None:
    """The refresh spends a shared TMDB budget and rewrites a table everyone reads."""
    await _a_set(api_session, "9000014", "A Director", [9_200_041])

    assert (await viewer_client.get("/api/v1/insights/completion")).status_code == 200
    assert (await viewer_client.post("/api/v1/insights/completion/refresh")).status_code == 403


async def test_an_unknown_set_is_a_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/insights/completion/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_the_refresh_endpoint_reports_what_it_did(
    client: AsyncClient, api_session: AsyncSession
) -> None:
    person = (9_000_015, "A Director Refreshed Over HTTP")
    await _a_collector_of(api_session, person, [9_300_001, 9_300_002, 9_300_003])
    fake = FakePersonClient(
        {
            person[0]: PersonMovieCredits(
                id=person[0], crew=[_credit(9_300_001, "One", job="Director")]
            )
        },
        # The endpoint caps `limitPerType` at 100 to bound TMDB spend, and against live
        # Neon that reaches real directors as well as this test's. They return nothing and
        # are skipped, so "no errors" stays a claim about the code rather than about which
        # database the suite happened to run against.
        on_unknown="empty",
    )

    async def override_tmdb() -> AsyncIterator[FakePersonClient]:
        yield fake

    app.dependency_overrides[get_tmdb_client] = override_tmdb
    try:
        response = await client.post(
            "/api/v1/insights/completion/refresh?dryRun=true&limitPerType=100"
        )
    finally:
        app.dependency_overrides.pop(get_tmdb_client, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dryRun"] is True
    assert body["created"] >= 1
    assert body["errors"] == []
