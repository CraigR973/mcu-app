"""AE10 (#355): movie night that reaches a match — Craig picked all five proposals on 11 Nov.

B, a shortlist of ten for a reason; A, who is watching picked as it starts, pushed at once; D,
the match says where the disc is and logs it for everyone, merged with Letterboxd; C, how far
the other person has got, never which films; E, nights nobody touched close themselves.

Deal tests give their films a genre of their own and filter on it, so the shelf a database
already holds never decides what a test sees.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clock import utcnow
from src.models.collection_item import CollectionItem
from src.models.movie import Movie
from src.models.movie_night import (
    MovieNightParticipant,
    MovieNightSession,
    MovieNightSuggestion,
    new_invite_token,
)
from src.models.notification import Notification
from src.models.profile import Profile
from src.models.watch_log import WatchLog
from src.services.letterboxd.diary import DiaryEntry
from src.services.letterboxd.importer import run_import
from src.services.movie_night import sessions as night_sessions
from src.services.movie_night.deal import DEAL_SIZE, REWATCH_SLOTS, dealt_films
from src.services.movie_night.diary import london_day
from src.services.movie_night.sessions import add_suggestion, record_vote
from tests.test_movie_night_send import RecordingSender, _as, _invites, _person, _phone
from tests.test_movie_night_send import _clear_overrides as _clear_overrides
from tests.test_movie_night_send import db as db
from tests.test_movie_night_send import pushes as pushes


def _genre() -> str:
    return f"AE10 genre {uuid.uuid4().hex[:8]}"


async def _film(
    db: AsyncSession,
    title: str,
    *,
    genre: str | None = None,
    runtime: int | None = 100,
    formats: tuple[str, ...] = ("blu_ray",),
    media_type: str = "film",
    owned: bool = True,
    tmdb_id: int | None = None,
    place: tuple[str, str, str] | None = None,
) -> Movie:
    movie = Movie(
        id=uuid.uuid4(),
        tmdb_id=tmdb_id,
        title=f"{title} {uuid.uuid4().hex[:6]}",
        original_title=title,
        media_type=media_type,
        year=2001,
        runtime_minutes=runtime,
        genres=[{"id": 1, "name": genre}] if genre else None,
    )
    db.add(movie)
    await db.flush()
    if owned:
        location, section, shelf = place or (None, None, None)
        db.add(
            CollectionItem(
                id=uuid.uuid4(),
                movie_id=movie.id,
                formats=list(formats),
                location=location,
                section=section,
                shelf=shelf,
            )
        )
        await db.flush()
    return movie


async def _watch(
    db: AsyncSession,
    person: Profile,
    movie: Movie,
    *,
    rating: str | None = None,
    day: date = date(2026, 10, 1),
    viewing_id: str | None = None,
) -> WatchLog:
    viewing = WatchLog(
        id=uuid.uuid4(),
        movie_id=movie.id,
        user_id=person.id,
        watched_at=day,
        personal_rating=Decimal(rating) if rating else None,
        letterboxd_viewing_id=viewing_id,
    )
    db.add(viewing)
    await db.flush()
    return viewing


async def _night(
    db: AsyncSession,
    *people: Profile,
    filters: dict[str, object] | None = None,
    created: datetime | None = None,
    planned: datetime | None = None,
) -> MovieNightSession:
    night = MovieNightSession(
        id=uuid.uuid4(),
        created_by=people[0].id,
        invite_token=new_invite_token(),
        filters=filters or {},
        planned_start_utc=planned,
    )
    if created is not None:
        night.created_at = created
    db.add(night)
    await db.flush()
    for person in people:
        db.add(MovieNightParticipant(id=uuid.uuid4(), session_id=night.id, user_id=person.id))
    await db.flush()
    return night


async def _match(
    db: AsyncSession, night: MovieNightSession, movie: Movie, *people: Profile
) -> MovieNightSuggestion:
    pick = await add_suggestion(db, session=night, user=people[0], movie_id=movie.id)
    for person in people:
        await record_vote(db, session=night, user=person, suggestion=pick, liked=True)
    return pick


# ---------------------------------------------------------------------------
# B — ten films, each there for a reason
# ---------------------------------------------------------------------------


async def test_a_night_is_dealt_ten_up_to_four_worth_a_rewatch_and_the_rest_in_neither_diary(
    db: AsyncSession,
) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    genre = _genre()
    loved = [await _film(db, f"Loved {index}", genre=genre) for index in range(6)]
    for film in loved:
        await _watch(db, craig, film, rating="5.0")
    unseen = [await _film(db, f"Unseen {index}", genre=genre) for index in range(12)]
    marks = [await _film(db, f"Mark saw {index}", genre=genre) for index in range(3)]
    for film in marks:
        await _watch(db, mark, film)
    night = await _night(db, craig, mark, filters={"genre": genre})

    dealt = await dealt_films(db, session=night, people=[craig.id, mark.id])

    assert len(dealt) == DEAL_SIZE
    reasons = [reason for _, reason in dealt]
    assert reasons == ["worthARewatch"] * REWATCH_SLOTS + ["inNeitherDiary"] * (
        DEAL_SIZE - REWATCH_SLOTS
    )
    assert {movie.id for movie, _ in dealt[:REWATCH_SLOTS]} <= {film.id for film in loved}
    assert {movie.id for movie, _ in dealt[REWATCH_SLOTS:]} <= {film.id for film in unseen}
    assert not {movie.id for movie, _ in dealt} & {film.id for film in marks}


async def test_a_rating_under_four_and_a_half_is_not_worth_a_rewatch(db: AsyncSession) -> None:
    craig = await _person(db, "Craig")
    genre = _genre()
    liked = await _film(db, "Liked", genre=genre)
    await _watch(db, craig, liked, rating="4.0")
    night = await _night(db, craig, filters={"genre": genre})

    assert await dealt_films(db, session=night, people=[craig.id]) == []


async def test_the_filters_narrow_the_deal(db: AsyncSession) -> None:
    craig = await _person(db, "Craig")
    genre = _genre()
    short = await _film(db, "Short", genre=genre, runtime=95)
    exactly = await _film(db, "Two hours", genre=genre, runtime=120)
    await _film(db, "Long", genre=genre, runtime=121)
    await _film(db, "Unknown length", genre=genre, runtime=None)
    await _film(db, "A series", genre=genre, runtime=50, media_type="tv")
    four_k = await _film(db, "Shiny", genre=genre, runtime=200, formats=("4k_uhd", "blu_ray"))
    loved = await _film(db, "Loved short", genre=genre, runtime=90)
    await _watch(db, craig, loved, rating="5.0")

    def ids(dealt: list[tuple[Movie, str]]) -> set[uuid.UUID]:
        return {movie.id for movie, _ in dealt}

    under = await _night(db, craig, filters={"genre": genre, "underTwoHours": True})
    assert ids(await dealt_films(db, session=under, people=[craig.id])) == {
        short.id,
        exactly.id,
        loved.id,
    }
    in_4k = await _night(db, craig, filters={"genre": genre, "fourK": True})
    assert ids(await dealt_films(db, session=in_4k, people=[craig.id])) == {four_k.id}
    neither = await _night(
        db, craig, filters={"genre": genre, "underTwoHours": True, "inNeitherDiary": True}
    )
    dealt = await dealt_films(db, session=neither, people=[craig.id])
    assert ids(dealt) == {short.id, exactly.id}
    assert {reason for _, reason in dealt} == {"inNeitherDiary"}


async def test_the_candidates_say_why_each_dealt_film_is_there(db: AsyncSession) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    genre = _genre()
    loved = await _film(db, "Loved", genre=genre)
    await _watch(db, craig, loved, rating="4.5")
    fresh = await _film(db, "Fresh", genre=genre)
    put_forward = await _film(db, "Put forward", genre=genre)
    night = await _night(db, craig, mark, filters={"genre": genre})
    await add_suggestion(db, session=night, user=mark, movie_id=put_forward.id)

    async with _as(db, craig) as client:
        response = await client.get(f"/api/v1/movie-night/{night.id}/candidates")
    assert response.status_code == 200, response.text
    reasons = {item["movieId"]: item["dealtAs"] for item in response.json()["items"]}
    # Mark's pick came first, so the night was never dealt: only his film is on it.
    assert reasons == {str(put_forward.id): None}

    second = await _night(db, craig, mark, filters={"genre": genre})
    async with _as(db, craig) as client:
        response = await client.get(f"/api/v1/movie-night/{second.id}/candidates")
    reasons = {item["movieId"]: item["dealtAs"] for item in response.json()["items"]}
    assert reasons[str(loved.id)] == "worthARewatch"
    assert reasons[str(fresh.id)] == "inNeitherDiary"


# ---------------------------------------------------------------------------
# A — who is watching, picked as it starts; the push goes at once
# ---------------------------------------------------------------------------


async def test_starting_a_night_for_mark_puts_him_in_it_and_pushes_it_once(
    db: AsyncSession, pushes: RecordingSender
) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    phone = await _phone(db, mark)

    async with _as(db, craig) as client:
        created = await client.post("/api/v1/movie-night", json={"userIds": [str(mark.id)]})
        assert created.status_code == 201, created.text
        body = created.json()
        again = await client.post(f"/api/v1/movie-night/{body['id']}/send", json={})
        assert again.status_code == 200, again.text

    people = {person["id"]: person for person in body["people"]}
    assert people[str(mark.id)]["invited"] is True
    assert str(mark.id) not in {person["id"] for person in body["invitable"]}
    assert pushes.sent == [phone], "pushed at once, and the later send did not push again"
    night = await db.get(MovieNightSession, uuid.UUID(body["id"]))
    assert night is not None
    (invite,) = await _invites(db, night, mark)
    assert invite.title == f"{craig.display_name} started a movie night"


async def test_starting_a_night_for_nobody_sends_nothing(
    db: AsyncSession, pushes: RecordingSender
) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    await _phone(db, mark)

    async with _as(db, craig) as client:
        created = await client.post("/api/v1/movie-night", json={"filters": {"fourK": True}})
    assert created.status_code == 201, created.text
    assert [person["id"] for person in created.json()["people"]] == [str(craig.id)]
    assert created.json()["filters"] == {"fourK": True}
    assert pushes.sent == []


async def test_starting_a_night_for_someone_who_cannot_sign_in_starts_nothing(
    db: AsyncSession,
) -> None:
    craig = await _person(db, "Craig")
    unset = Profile(id=uuid.uuid4(), display_name=f"Unset {uuid.uuid4().hex[:6]}", pin_hash=None)
    db.add(unset)
    await db.flush()

    async with _as(db, craig) as client:
        refused = await client.post("/api/v1/movie-night", json={"userIds": [str(unset.id)]})
    assert refused.status_code == 422, refused.text
    started = await db.scalar(
        select(func.count(MovieNightSession.id)).where(MovieNightSession.created_by == craig.id)
    )
    assert started == 0


async def test_the_list_says_who_a_new_night_can_be_sent_to(db: AsyncSession) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    unset = Profile(id=uuid.uuid4(), display_name=f"Unset {uuid.uuid4().hex[:6]}", pin_hash=None)
    db.add(unset)
    await db.flush()

    async with _as(db, craig) as client:
        listed = await client.get("/api/v1/movie-night")
    assert listed.status_code == 200, listed.text
    names = {person["id"] for person in listed.json()["people"]}
    assert str(mark.id) in names
    assert str(craig.id) not in names and str(unset.id) not in names


async def test_a_night_started_for_two_is_dealt_from_both_diaries(
    db: AsyncSession, pushes: RecordingSender
) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    del pushes
    genre = _genre()
    seen_by_mark = await _film(db, "Mark saw it", genre=genre)
    await _watch(db, mark, seen_by_mark)
    fresh = await _film(db, "Nobody saw it", genre=genre)

    async with _as(db, craig) as client:
        created = await client.post(
            "/api/v1/movie-night",
            json={"userIds": [str(mark.id)], "filters": {"genre": genre}},
        )
        assert created.status_code == 201, created.text
        listed = await client.get(f"/api/v1/movie-night/{created.json()['id']}/candidates")
    assert [item["movieId"] for item in listed.json()["items"]] == [str(fresh.id)]


# ---------------------------------------------------------------------------
# C — how far each person has got, never which films
# ---------------------------------------------------------------------------


async def test_the_night_counts_each_persons_adds_and_never_names_them(db: AsyncSession) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    night = await _night(db, craig, mark)
    picks = [
        await add_suggestion(
            db, session=night, user=mark, movie_id=(await _film(db, f"Pick {index}")).id
        )
        for index in range(4)
    ]
    for pick in picks[:3]:
        await record_vote(db, session=night, user=mark, suggestion=pick, liked=True)
    await record_vote(db, session=night, user=mark, suggestion=picks[3], liked=False)

    async with _as(db, craig) as client:
        session = (await client.get(f"/api/v1/movie-night/{night.id}")).json()
        listed = (await client.get(f"/api/v1/movie-night/{night.id}/candidates")).json()
    people = {person["id"]: person for person in session["people"]}
    assert people[str(mark.id)]["added"] == 3
    assert people[str(craig.id)]["added"] == 0
    assert {item["myVote"] for item in listed["items"]} == {None}, "Mark's picks stay his"


async def test_choosing_now_means_seen_in_the_last_five_minutes(db: AsyncSession) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    night = await _night(db, craig, mark)
    seat = await db.scalar(
        select(MovieNightParticipant).where(
            MovieNightParticipant.session_id == night.id, MovieNightParticipant.user_id == mark.id
        )
    )
    assert seat is not None

    async def mark_as_craig_sees_him() -> dict[str, object]:
        async with _as(db, craig) as client:
            body = (await client.get(f"/api/v1/movie-night/{night.id}")).json()
        return next(person for person in body["people"] if person["id"] == str(mark.id))

    unopened = await mark_as_craig_sees_him()
    assert unopened["lastSeen"] is None and unopened["choosingNow"] is False
    seat.last_seen_utc = utcnow() - timedelta(minutes=4)
    await db.flush()
    assert (await mark_as_craig_sees_him())["choosingNow"] is True
    seat.last_seen_utc = utcnow() - timedelta(minutes=6)
    await db.flush()
    assert (await mark_as_craig_sees_him())["choosingNow"] is False


async def test_opening_the_night_says_you_have_it_open(db: AsyncSession) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    night = await _night(db, craig, mark)

    async with _as(db, mark) as client:
        assert (await client.get(f"/api/v1/movie-night/{night.id}")).status_code == 200
    async with _as(db, craig) as client:
        body = (await client.get(f"/api/v1/movie-night/{night.id}")).json()
    mark_seen = next(person for person in body["people"] if person["id"] == str(mark.id))
    assert mark_seen["choosingNow"] is True and mark_seen["lastSeen"] is not None


async def test_the_live_vote_event_names_no_film(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    craig = await _person(db, "Craig")
    night = await _night(db, craig)
    pick = await add_suggestion(db, session=night, user=craig, movie_id=(await _film(db, "X")).id)
    events: list[tuple[str, dict[str, object]]] = []

    async def record(
        db: AsyncSession, session_id: uuid.UUID, kind: str, data: dict[str, object]
    ) -> None:
        del db, session_id
        events.append((kind, data))

    monkeypatch.setattr(night_sessions, "publish", record)
    await record_vote(db, session=night, user=craig, suggestion=pick, liked=True)

    assert events == [("vote", {})]


# ---------------------------------------------------------------------------
# D — where the disc is, and "Log it for both of us"
# ---------------------------------------------------------------------------


async def test_the_match_says_which_shelf_and_how_long(db: AsyncSession) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    film = await _film(db, "The Exorcist", runtime=122, place=("Lounge", "Lounge", "Left"))
    night = await _night(db, craig, mark)
    pick = await add_suggestion(db, session=night, user=craig, movie_id=film.id)
    await record_vote(db, session=night, user=craig, suggestion=pick, liked=True)

    async with _as(db, mark) as client:
        voted = await client.post(
            f"/api/v1/movie-night/{night.id}/votes",
            json={"suggestionId": str(pick.id), "liked": True},
        )
        stored = (await client.get(f"/api/v1/movie-night/{night.id}")).json()
    assert voted.status_code == 200, voted.text
    for match in (voted.json()["match"], stored["match"]):
        assert match["runtimeMinutes"] == 122
        assert match["places"] == [{"location": "Lounge", "section": "Lounge", "shelf": "Left"}]
        assert match["loggedAt"] is None


async def test_log_it_for_both_writes_one_viewing_each_dated_today_once(
    db: AsyncSession,
) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    film = await _film(db, "The Exorcist", tmdb_id=900000000 + uuid.uuid4().int % 99999999)
    await _watch(db, craig, film, day=date(2020, 10, 31))
    night = await _night(db, craig, mark)
    await _match(db, night, film, craig, mark)

    async with _as(db, mark) as client:
        first = await client.post(f"/api/v1/movie-night/{night.id}/log")
        second = await client.post(f"/api/v1/movie-night/{night.id}/log")
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["match"]["loggedAt"] is not None

    today = london_day(utcnow())
    viewings = list(
        await db.scalars(
            select(WatchLog).where(WatchLog.movie_id == film.id, WatchLog.watched_at == today)
        )
    )
    assert sorted(viewing.user_id for viewing in viewings) == sorted([craig.id, mark.id])
    by_person = {viewing.user_id: viewing for viewing in viewings}
    assert by_person[craig.id].is_rewatch is True, "Craig had seen it in 2020"
    assert by_person[mark.id].is_rewatch is False
    assert {viewing.letterboxd_viewing_id for viewing in viewings} == {None}
    assert {viewing.tmdb_id for viewing in viewings} == {film.tmdb_id}


async def test_nothing_can_be_logged_before_a_match(db: AsyncSession) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    night = await _night(db, craig, mark)

    async with _as(db, craig) as client:
        response = await client.post(f"/api/v1/movie-night/{night.id}/log")
    assert response.status_code == 409, response.text


async def test_a_film_nobody_owns_gets_its_row_without_a_copy_when_logged(
    db: AsyncSession,
) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    tmdb_id = 800000000 + uuid.uuid4().int % 99999999
    night = await _night(db, craig, mark)
    pick = await add_suggestion(
        db, session=night, user=craig, tmdb_id=tmdb_id, title="Rented Film", year=1999
    )
    for person in (craig, mark):
        await record_vote(db, session=night, user=person, suggestion=pick, liked=True)

    async with _as(db, craig) as client:
        response = await client.post(f"/api/v1/movie-night/{night.id}/log")
    assert response.status_code == 200, response.text
    film = await db.scalar(select(Movie).where(Movie.tmdb_id == tmdb_id))
    assert film is not None and film.title == "Rented Film"
    copies = await db.scalar(
        select(func.count(CollectionItem.id)).where(CollectionItem.movie_id == film.id)
    )
    assert copies == 0
    viewers = await db.scalars(select(WatchLog.user_id).where(WatchLog.movie_id == film.id))
    assert sorted(viewers) == sorted([craig.id, mark.id])


async def test_a_film_in_the_trash_is_not_brought_back_by_logging(db: AsyncSession) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    tmdb_id = 700000000 + uuid.uuid4().int % 99999999
    trashed = await _film(db, "Binned", tmdb_id=tmdb_id, owned=False)
    trashed.deleted_at = utcnow()
    night = await _night(db, craig, mark)
    pick = await add_suggestion(
        db, session=night, user=craig, tmdb_id=tmdb_id, title="Binned", year=2001
    )
    for person in (craig, mark):
        await record_vote(db, session=night, user=person, suggestion=pick, liked=True)

    async with _as(db, craig) as client:
        response = await client.post(f"/api/v1/movie-night/{night.id}/log")
    assert response.status_code == 409, response.text
    assert trashed.deleted_at is not None


def test_a_viewing_is_dated_by_the_evening_in_london() -> None:
    assert london_day(datetime(2026, 7, 10, 23, 30)) == date(2026, 7, 11)  # BST
    assert london_day(datetime(2026, 11, 11, 23, 30)) == date(2026, 11, 11)  # GMT


def _entry(viewing_id: str, film: Movie, watched: date, rating: str | None = None) -> DiaryEntry:
    return DiaryEntry(
        viewing_id=viewing_id,
        watched_at=watched,
        title=film.title,
        year=film.year,
        rating=Decimal(rating) if rating else None,
        is_rewatch=False,
    )


async def test_a_letterboxd_viewing_claims_the_one_logged_in_the_app(db: AsyncSession) -> None:
    craig = await _person(db, "Craig")
    film = await _film(db, "Logged twice")
    app_logged = await _watch(db, craig, film, day=date(2026, 11, 11))

    report = await run_import(
        db, craig, [_entry("70001", film, date(2026, 11, 12), "4.0")], dry_run=False
    )

    assert report.merged == 1 and report.written == 1
    rows = list(await db.scalars(select(WatchLog).where(WatchLog.movie_id == film.id)))
    assert [row.id for row in rows] == [app_logged.id], "one viewing, not two"
    assert rows[0].letterboxd_viewing_id == "70001"
    assert rows[0].watched_at == date(2026, 11, 12)
    assert rows[0].personal_rating == Decimal("4.0")


async def test_a_viewing_more_than_a_day_apart_is_another_viewing(db: AsyncSession) -> None:
    craig = await _person(db, "Craig")
    film = await _film(db, "Watched twice")
    app_logged = await _watch(db, craig, film, day=date(2026, 11, 8))

    report = await run_import(db, craig, [_entry("70002", film, date(2026, 11, 11))], dry_run=False)

    assert report.merged == 0 and report.written == 1
    rows = list(await db.scalars(select(WatchLog).where(WatchLog.movie_id == film.id)))
    assert len(rows) == 2
    assert app_logged.letterboxd_viewing_id is None


async def test_the_closest_app_viewing_is_claimed_first(db: AsyncSession) -> None:
    craig = await _person(db, "Craig")
    film = await _film(db, "Two evenings")
    day_before = await _watch(db, craig, film, day=date(2026, 11, 10))
    same_day = await _watch(db, craig, film, day=date(2026, 11, 11))

    await run_import(db, craig, [_entry("70003", film, date(2026, 11, 11))], dry_run=False)

    assert same_day.letterboxd_viewing_id == "70003"
    assert day_before.letterboxd_viewing_id is None


async def test_a_dry_run_claims_nothing(db: AsyncSession) -> None:
    craig = await _person(db, "Craig")
    film = await _film(db, "Rehearsed")
    app_logged = await _watch(db, craig, film, day=date(2026, 11, 11))

    report = await run_import(db, craig, [_entry("70004", film, date(2026, 11, 11))])

    assert report.dry_run and report.merged == 1
    assert app_logged.letterboxd_viewing_id is None


async def test_another_persons_app_viewing_is_never_claimed(db: AsyncSession) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    film = await _film(db, "Watched together")
    marks = await _watch(db, mark, film, day=date(2026, 11, 11))

    report = await run_import(db, craig, [_entry("70005", film, date(2026, 11, 11))], dry_run=False)

    assert report.merged == 0 and report.written == 1
    assert marks.letterboxd_viewing_id is None


# ---------------------------------------------------------------------------
# E — nights nobody touched close themselves
# ---------------------------------------------------------------------------


async def _reload(db: AsyncSession, night: MovieNightSession) -> MovieNightSession:
    fresh = await db.scalar(
        select(MovieNightSession)
        .where(MovieNightSession.id == night.id)
        .execution_options(populate_existing=True)
    )
    assert fresh is not None
    return fresh


async def test_an_untouched_night_closes_two_days_after_it_started(db: AsyncSession) -> None:
    craig = await _person(db, "Craig")
    started = utcnow() - timedelta(days=3)
    night = await _night(db, craig, created=started)
    kept = await add_suggestion(db, session=night, user=craig, movie_id=(await _film(db, "K")).id)

    async with _as(db, craig) as client:
        listed = (await client.get("/api/v1/movie-night")).json()
    shown = next(item for item in listed["items"] if item["id"] == str(night.id))
    assert shown["status"] == "ended"
    closed = await _reload(db, night)
    assert closed.ended_at_utc == started + timedelta(days=2), "closed when it became due"
    assert await db.get(MovieNightSuggestion, kept.id) is not None, "its history stays"


async def test_a_night_anybody_voted_on_stays_open(db: AsyncSession) -> None:
    craig = await _person(db, "Craig")
    night = await _night(db, craig, created=utcnow() - timedelta(days=10))
    pick = await add_suggestion(db, session=night, user=craig, movie_id=(await _film(db, "V")).id)
    await record_vote(db, session=night, user=craig, suggestion=pick, liked=False)

    async with _as(db, craig) as client:
        assert (await client.get("/api/v1/movie-night")).status_code == 200
    assert (await _reload(db, night)).status == "open"


async def test_a_planned_night_closes_two_days_after_its_planned_start(db: AsyncSession) -> None:
    craig = await _person(db, "Craig")
    long_ago = utcnow() - timedelta(days=9)
    recent = await _night(db, craig, created=long_ago, planned=utcnow() - timedelta(days=1))
    to_come = await _night(db, craig, created=long_ago, planned=utcnow() + timedelta(days=5))
    planned_past = utcnow() - timedelta(days=3)
    past = await _night(db, craig, created=long_ago, planned=planned_past)

    async with _as(db, craig) as client:
        assert (await client.get("/api/v1/movie-night")).status_code == 200
    assert (await _reload(db, recent)).status == "open"
    assert (await _reload(db, to_come)).status == "open"
    closed = await _reload(db, past)
    assert closed.status == "ended"
    assert closed.ended_at_utc == planned_past + timedelta(days=2)


async def test_a_closed_nights_invite_and_votes_stop_working(db: AsyncSession) -> None:
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    night = await _night(db, craig, mark, created=utcnow() - timedelta(days=3))
    pick = await add_suggestion(db, session=night, user=craig, movie_id=(await _film(db, "C")).id)
    # No vote yet: the night is untouched and due.

    async with _as(db, mark) as client:
        vote = await client.post(
            f"/api/v1/movie-night/{night.id}/votes",
            json={"suggestionId": str(pick.id), "liked": True},
        )
    assert vote.status_code == 409, vote.text
    other = await _person(db, "Alex")
    async with _as(db, other) as client:
        joined = await client.post(f"/api/v1/movie-night/join/{night.invite_token}")
    assert joined.status_code == 404, joined.text


async def test_a_match_is_announced_with_a_notification_still(db: AsyncSession) -> None:
    """The match push is unchanged by AE10: both people, once."""
    craig, mark = await _person(db, "Craig"), await _person(db, "Mark")
    night = await _night(db, craig, mark)
    await _match(db, night, await _film(db, "Matched"), craig, mark)

    titles = list(
        await db.scalars(
            select(Notification.title).where(Notification.user_id.in_([craig.id, mark.id]))
        )
    )
    assert len([title for title in titles if title.startswith("It's a match")]) == 2


async def test_feeling_lucky_on_a_night_keeps_to_its_filters(db: AsyncSession) -> None:
    """Feeling lucky on a night deals within the night's filters, as its shortlist does."""
    craig = await _person(db, "Craig")
    genre = _genre()
    short = await _film(db, "Short enough", genre=genre, runtime=95)
    await _film(db, "Too long", genre=genre, runtime=150)
    night = await _night(db, craig, filters={"genre": genre, "underTwoHours": True})

    async with _as(db, craig) as client:
        for _ in range(3):
            dealt = await client.post(
                "/api/v1/feeling-lucky", json={"sessionId": str(night.id), "excludedIds": []}
            )
            assert dealt.status_code == 200, dealt.text
            assert dealt.json()["film"]["id"] == str(short.id)
