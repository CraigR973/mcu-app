"""Movie night — §8.3's sessions and §8.4's realtime swiping.

**Both people, not admin and viewer.** A movie night is two people on a sofa deciding what
to watch; there is no version of it where one of them may not vote. Every route here is
`CurrentUser`.

**Realtime is Postgres `LISTEN`/`NOTIFY` with SSE** (`DECISIONS.md` #113), not Supabase
Realtime — §8.4 names a product this app has never had. The listener's connection
discipline is `services/movie_night/realtime.py`'s whole subject.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from src.auth import CurrentUser
from src.clock import utcnow
from src.models.movie_night import (
    MovieNightParticipant,
    MovieNightSession,
    new_invite_token,
)
from src.models.profile import Profile
from src.routers.movies import Database
from src.schemas.movie_night import (
    CandidateListResponse,
    CandidateResponse,
    MatchResponse,
    MovieNightSessionListResponse,
    MovieNightSessionResponse,
    SessionCreateRequest,
    VoteRequest,
    VoteResponse,
)
from src.services.movie_night.realtime import broadcaster
from src.services.movie_night.sessions import candidate_movies, publish, record_vote

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["movie-night"])

#: How long the stream waits before sending a keep-alive comment. Proxies and phone
#: radios close an idle connection, and a movie night has long quiet stretches while
#: somebody reads a synopsis — without this the stream dies mid-session and looks like
#: the other person having stopped swiping.
HEARTBEAT_SECONDS = 20.0


async def _session_for(
    db: Database, session_id: uuid.UUID, user: Profile, *, must_be_open: bool = False
) -> MovieNightSession:
    """A session the caller is actually in."""
    session = (
        await db.execute(
            select(MovieNightSession)
            .join(
                MovieNightParticipant,
                MovieNightParticipant.session_id == MovieNightSession.id,
            )
            .where(MovieNightSession.id == session_id, MovieNightParticipant.user_id == user.id)
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if must_be_open and session.status != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That movie night has ended"
        )
    return session


async def _response(db: Database, session: MovieNightSession) -> MovieNightSessionResponse:
    count = (
        await db.execute(
            select(func.count())
            .select_from(MovieNightParticipant)
            .where(MovieNightParticipant.session_id == session.id)
        )
    ).scalar_one()
    return MovieNightSessionResponse(
        id=session.id,
        status="open" if session.status == "open" else "ended",
        filters=session.filters or {},
        inviteToken=session.invite_token,
        # The path a person shares. Composed here rather than as an absolute URL for the
        # reason Batch 17 and 27 both settled on: the API cannot know its own public
        # origin without trusting the `Host` header.
        invitePath=f"/movie-night/join/{session.invite_token}",
        participantCount=count,
        createdAt=session.created_at,
        endedAt=session.ended_at_utc,
    )


@router.get("/movie-night", response_model=MovieNightSessionListResponse)
async def list_sessions(user: CurrentUser, db: Database) -> MovieNightSessionListResponse:
    """The caller's sessions, newest first."""
    sessions = list(
        (
            await db.execute(
                select(MovieNightSession)
                .join(
                    MovieNightParticipant,
                    MovieNightParticipant.session_id == MovieNightSession.id,
                )
                .where(MovieNightParticipant.user_id == user.id)
                .order_by(MovieNightSession.created_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    return MovieNightSessionListResponse(
        items=[await _response(db, session) for session in sessions], total=len(sessions)
    )


@router.post(
    "/movie-night", response_model=MovieNightSessionResponse, status_code=status.HTTP_201_CREATED
)
async def create_session(
    payload: SessionCreateRequest, user: CurrentUser, db: Database
) -> MovieNightSessionResponse:
    """§8.3 — start a movie night. The creator is its first participant."""
    session = MovieNightSession(
        id=uuid.uuid4(),
        created_by=user.id,
        invite_token=new_invite_token(),
        filters=payload.filters,
    )
    db.add(session)
    await db.flush()
    db.add(
        MovieNightParticipant(
            id=uuid.uuid4(), session_id=session.id, user_id=user.id, joined_at_utc=utcnow()
        )
    )
    await db.commit()
    await db.refresh(session)
    return await _response(db, session)


@router.post("/movie-night/join/{invite_token}", response_model=MovieNightSessionResponse)
async def join_session(
    invite_token: str, user: CurrentUser, db: Database
) -> MovieNightSessionResponse:
    """§8.3's acceptance — *"second user joins via URL"*.

    **Authenticated, unlike Batch 17's feed and Batch 27's gift page.** Those are read-only
    surfaces for people with no account; this one votes, and a vote has to belong to
    somebody. The token says *which session*, not *who*.
    """
    session = (
        await db.execute(
            select(MovieNightSession).where(
                MovieNightSession.invite_token == invite_token,
                MovieNightSession.status == "open",
            )
        )
    ).scalar_one_or_none()
    if session is None:
        # One answer for "no such token" and "that night is over", so a wrong link cannot
        # be used to find out which tokens exist.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That invite is not valid"
        )

    already = (
        await db.execute(
            select(MovieNightParticipant).where(
                MovieNightParticipant.session_id == session.id,
                MovieNightParticipant.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if already is None:
        db.add(
            MovieNightParticipant(
                id=uuid.uuid4(), session_id=session.id, user_id=user.id, joined_at_utc=utcnow()
            )
        )
        await db.flush()
        await publish(db, session.id, "joined", {"userId": str(user.id)})
    await db.commit()
    return await _response(db, session)


@router.get("/movie-night/{session_id}", response_model=MovieNightSessionResponse)
async def read_session(
    session_id: uuid.UUID, user: CurrentUser, db: Database
) -> MovieNightSessionResponse:
    return await _response(db, await _session_for(db, session_id, user))


@router.post("/movie-night/{session_id}/end", response_model=MovieNightSessionResponse)
async def end_session(
    session_id: uuid.UUID, user: CurrentUser, db: Database
) -> MovieNightSessionResponse:
    """Close it. The invite stops working and the votes stay."""
    session = await _session_for(db, session_id, user)
    if session.status == "open":
        session.status = "ended"
        session.ended_at_utc = utcnow()
        await db.flush()
        await publish(db, session.id, "ended", {})
    await db.commit()
    return await _response(db, session)


@router.get("/movie-night/{session_id}/candidates", response_model=CandidateListResponse)
async def list_candidates(
    session_id: uuid.UUID,
    user: CurrentUser,
    db: Database,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> CandidateListResponse:
    """The deck — films **this** person has not swiped on yet."""
    session = await _session_for(db, session_id, user)
    movies = await candidate_movies(db, session=session, user=user, limit=limit)
    return CandidateListResponse(
        items=[
            CandidateResponse(
                movieId=movie.id,
                title=movie.title,
                year=movie.year,
                posterPath=movie.poster_path,
                overview=movie.overview,
            )
            for movie in movies
        ],
        total=len(movies),
    )


@router.post("/movie-night/{session_id}/votes", response_model=VoteResponse)
async def cast_vote(
    session_id: uuid.UUID, payload: VoteRequest, user: CurrentUser, db: Database
) -> VoteResponse:
    """§8.4 — one swipe, and the match if it completed one."""
    session = await _session_for(db, session_id, user, must_be_open=True)
    match = await record_vote(
        db, session=session, user=user, movie_id=payload.movieId, liked=payload.liked
    )
    await db.commit()
    return VoteResponse(
        recorded=True,
        match=(
            MatchResponse(movieId=match.movie_id, title=match.title, posterPath=match.poster_path)
            if match is not None
            else None
        ),
    )


async def _events(session_id: uuid.UUID) -> AsyncIterator[str]:
    """Server-Sent Events for one session, fed by the `LISTEN` connection.

    The heartbeat is a comment line, which SSE defines as ignorable — it keeps proxies and
    phone radios from closing a connection that is merely quiet, without the browser having
    to know about it.
    """
    queue = await broadcaster.subscribe(str(session_id))
    try:
        yield ": connected\n\n"
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield f"data: {json.dumps(event)}\n\n"
    finally:
        # Runs when the browser goes away, which is how the listening connection is
        # eventually released — see #113 on why that matters.
        await broadcaster.unsubscribe(str(session_id), queue)


@router.get("/movie-night/{session_id}/events")
async def session_events(
    session_id: uuid.UUID, user: CurrentUser, db: Database
) -> StreamingResponse:
    """§8.4's realtime sync. `LISTEN`/`NOTIFY` over SSE, per `DECISIONS.md` #113."""
    await _session_for(db, session_id, user)
    return StreamingResponse(
        _events(session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
