"""Private, durable observations, not a second catalogue correction path (AD1).

AG5 (amends #351): **any want can ask "which film?"** when its shop listings name another film's
year (``services/scraping/another_film.py``). Its words are written from those listings when the
admin assigns it and kept on the row; its choices are the want's film and each other year. The
Dead Man's Shoes question keeps the words it was asked with.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Collection
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.admin_action import AdminAction
from src.models.assigned_review import AssignedReview
from src.models.collection_item import CollectionItem, owned_copy
from src.models.identify import IdentifyDoubt
from src.models.movie import Movie
from src.models.price_check import ANOTHER_YEAR, PriceCheck
from src.models.profile import Profile, UserRole
from src.models.wanted import WantedItem
from src.schemas.assigned_reviews import (
    AssignedReviewResponse,
    AssignReview,
    ReviewKind,
    ReviewProposal,
    WantProposal,
)
from src.services.collection_additions import MARK_PROFILE_ID
from src.services.identify.waiting import still_to_identify
from src.services.scraping.another_film import WANT_QUESTION, other_films

# Approved assignment manifest only; never inserted by a migration or Home read.
MARK_REVIEW_MOVIES = {
    "titanic_disc": uuid.UUID("219a59fc-8a0b-4eeb-ba7c-18b0391eb69f"),
    "wanted_identity": uuid.UUID("58df19fb-d961-457c-8374-6df550b563cf"),
    "shetland_series": uuid.UUID("d90ea74d-8ad3-4864-9070-043c4e358e59"),
}
WORDS = {
    "titanic_disc": (
        "Check Titanic's Blu-ray",
        "Is this affected disc Titanic (1953) or Titanic (1997)?",
        "The catalogue says 1953; the selected disc-page evidence names 1997. "
        "Inspect the physical disc and edition. This question concerns this copy only.",
        [("1953", "Titanic (1953)"), ("1997", "Titanic (1997)")],
    ),
    "wanted_identity": (
        "Check Dead Man's Shoes on Wanted",
        "Is the wanted film Dead Man's Shoes (2004) or Dead Man's Shoes (1940)?",
        "Wanted currently names the 1940 film; the retained shop-history discrepancy "
        "was documented as the 2004 release. Your answer does not transfer any records.",
        [("2004", "Dead Man's Shoes (2004)"), ("1940", "Dead Man's Shoes (1940)")],
    ),
    "shetland_series": (
        "Check Shetland Series 5",
        "Should this Series 5 copy use the existing Shetland series identity?",
        "The catalogue already has Shetland as a TV series. Series 5 remains unmatched. "
        "Separate physical copies must remain separate; this answer deletes no copies.",
        [
            ("use_series", "Use the existing series"),
            ("keep_separate", "Keep this identity separate"),
        ],
    ),
}


#: A question's words: title, question, evidence and its choices as (value, label).
Words = tuple[str, str, str, list[tuple[str, str]]]


def as_wording(words: Words) -> dict[str, Any]:
    """Words as a want question's row keeps them (``assigned_reviews.wording``)."""
    title, question, evidence, choices = words
    return {
        "title": title,
        "question": question,
        "evidence": evidence,
        "choices": [{"value": value, "label": label} for value, label in choices],
    }


def wording_of(row: AssignedReview) -> Words:
    """The row's own words when it has them (a want question), else its kind's fixed words."""
    if row.wording is None:
        return WORDS[row.kind]
    wording = row.wording
    return (
        wording["title"],
        wording["question"],
        wording["evidence"],
        [(choice["value"], choice["label"]) for choice in wording["choices"]],
    )


async def want_words(
    db: AsyncSession, want_id: uuid.UUID, snapshot: dict[str, Any]
) -> Words | None:
    """What a want asks, from the other years its shop listings name; ``None`` if none do."""
    year = snapshot.get("year")
    if year is None:
        return None
    others = await other_films(db, want_id)
    if not others:
        return None
    title = snapshot["title"]
    film = f"{title} ({year})"
    choices = [(str(year), film), *((str(other.year), other.label) for other in others)]
    if len(choices) == 2:
        question = f"Is the wanted film {choices[0][1]} or {choices[1][1]}?"
    else:
        question = f"Which film is the wanted {title}?"
    listed = "; ".join(
        f"{', '.join(other.shops)} {'lists' if len(other.shops) == 1 else 'list'} {other.label}"
        for other in others
    )
    evidence = (
        f"Wanted names the {year} film; {listed}. "
        "Your answer does not move the want or change its prices."
    )
    return (f"Check {title} on Wanted", question, evidence, choices)


def fingerprint(snapshot: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


def _conflict() -> HTTPException:
    return HTTPException(409, "The review target changed. Re-open it before making a decision.")


async def context(
    db: AsyncSession,
    kind: str,
    target_id: uuid.UUID,
    *,
    lock: bool = False,
) -> tuple[dict[str, Any], bool]:
    """Relevant current facts only. A read does not write a resolved state.

    Assignment/answers lock the target rows until commit; a concurrent correction cannot
    slip between validation and the observation. Missing/sold/deleted targets are changed,
    never silently completed. No new provider lookup happens here.
    """

    async def get(model: Any, key: uuid.UUID) -> Any:
        query = select(model).where(model.id == key)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = await db.scalar(query)
        if row is None:
            raise _conflict()
        return row

    item = None
    doubt = None
    want = None
    if kind == "titanic_disc":
        doubt = await get(IdentifyDoubt, target_id)
        if doubt.collection_item_id is None:
            raise _conflict()
        item = await get(CollectionItem, doubt.collection_item_id)
        movie_id = item.movie_id
    elif kind == "shetland_series":
        item = await get(CollectionItem, target_id)
        movie_id = item.movie_id
    elif kind == "wanted_identity":
        want = await get(WantedItem, target_id)
        if want.deleted_at is not None or not want.is_active:
            raise _conflict()
        movie_id = want.movie_id
    else:
        raise HTTPException(422, "Unknown review kind")
    if item is not None and (
        item.deleted_at is not None
        or item.listing_status not in ("in_collection", "listed_for_sale")
    ):
        raise _conflict()
    movie = await get(Movie, movie_id)
    if movie.deleted_at is not None:
        raise _conflict()
    snapshot: dict[str, Any] = {
        "movieId": str(movie.id),
        "title": movie.title,
        "year": movie.year,
        "tmdbId": movie.tmdb_id,
        "tmdbTvId": movie.tmdb_tv_id,
    }
    if item is not None:
        snapshot.update(copyId=str(item.id), formats=item.formats)
    if doubt is not None:
        snapshot.update(
            doubtStatus=doubt.status,
            identifiedAs=doubt.identified_as,
            proposedTmdbId=doubt.proposed_tmdb_id,
            note=doubt.note,
            pageUrl=doubt.page_url,
        )
        resolved = doubt.status in ("kept", "corrected", "moved")
    elif kind == "shetland_series":
        resolved = movie.tmdb_tv_id == 46923
        snapshot["stillToIdentify"] = bool(
            await db.scalar(select(Movie.id).where(Movie.id == movie.id, still_to_identify()))
        )
    else:
        assert want is not None
        snapshot.update(
            preferredFormat=want.preferred_format, preferredEdition=want.preferred_edition
        )
        resolved = False  # A changed wanted identity is not proof its price history was repaired.
    return snapshot, resolved


async def describe(
    db: AsyncSession, row: AssignedReview, reader: Profile
) -> AssignedReviewResponse:
    title, question, evidence, options = wording_of(row)
    status: Any = "answered" if row.answer not in (None, "unsure") else "open"
    movie_id: uuid.UUID | None = uuid.UUID(row.snapshot["movieId"])
    try:
        current, resolved = await context(db, row.kind, row.target_id)
        movie_id = uuid.UUID(current["movieId"])
        if resolved:
            status = "resolved"
        elif current != row.snapshot:
            status = "changed"
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        status = "changed"
        original = await db.get(Movie, movie_id)
        if original is None or original.deleted_at is not None:
            movie_id = None
    assignee = await db.get(Profile, row.assigned_to)
    return AssignedReviewResponse(
        id=row.id,
        kind=cast(ReviewKind, row.kind),
        targetId=row.target_id,
        assignedTo=row.assigned_to,
        assigneeName=assignee.display_name if assignee else "Former profile",
        movieId=movie_id,
        title=title,
        question=question,
        evidence=evidence,
        choices=[{"value": value, "label": label} for value, label in options]
        + [{"value": "unsure", "label": "Not sure yet"}],
        revision=row.revision,
        answer=row.answer,
        answeredAt=row.answered_at_utc,
        status=status,
        canAnswer=reader.id == row.assigned_to and status in ("open", "answered"),
    )


async def list_reviews(
    db: AsyncSession,
    reader: Profile,
    *,
    all_assignees: bool = False,
    shared_with: Collection[uuid.UUID] = (),
) -> list[AssignedReviewResponse]:
    """The reader's reviews; with ``shared_with`` (AE8, #355: the shelf keepers, for one of
    them), every one of theirs too, the reader's own first. Only the assignee answers."""
    if all_assignees and reader.role != UserRole.admin:
        raise HTTPException(403, "Only an administrator can inspect other people's reviews")
    query = select(AssignedReview).where(AssignedReview.deleted_at.is_(None))
    if not all_assignees:
        query = query.where(AssignedReview.assigned_to.in_({reader.id, *shared_with}))
    rows = (await db.scalars(query.order_by(AssignedReview.created_at, AssignedReview.id))).all()
    rows = sorted(rows, key=lambda row: row.assigned_to != reader.id)
    return [await describe(db, row, reader) for row in rows]


async def review_for(
    db: AsyncSession,
    review_id: uuid.UUID,
    reader: Profile,
    *,
    lock: bool = False,
    shared_with: Collection[uuid.UUID] = (),
) -> AssignedReview:
    """A review the reader may see. ``shared_with`` widens it, for reading only, to the other
    shelf keepers' reviews (AE8, #355); every write passes none, so its refusals are unchanged."""
    query = select(AssignedReview).where(
        AssignedReview.id == review_id,
        AssignedReview.deleted_at.is_(None),
    )
    if reader.role != UserRole.admin:
        query = query.where(AssignedReview.assigned_to.in_({reader.id, *shared_with}))
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = await db.scalar(query)
    if row is None:
        raise HTTPException(404, "Review not found")
    return row


def audit(
    db: AsyncSession,
    row: AssignedReview,
    by: Profile,
    changes: dict[str, Any],
    *,
    create: bool = False,
) -> None:
    db.add(
        AdminAction(
            user_id=by.id,
            action_type="create" if create else "update",
            target_table="assigned_reviews",
            target_id=str(row.id),
            changes=changes,
        )
    )


async def active_person(db: AsyncSession, person_id: uuid.UUID) -> None:
    person = await db.get(Profile, person_id)
    if person is None or not person.is_active or person.deleted_at is not None:
        raise HTTPException(422, "Choose an active profile")


def validate_subject(kind: str, snapshot: dict[str, Any]) -> None:
    expected = {"titanic_disc": (1953, 16535), "wanted_identity": (1940, 416920)}
    if kind in expected:
        year, tmdb = expected[kind]
        if snapshot["year"] != year or snapshot["tmdbId"] != tmdb:
            raise _conflict()
    elif not snapshot.get("stillToIdentify"):
        raise _conflict()


async def assign(db: AsyncSession, payload: AssignReview, actor: Profile) -> AssignedReview:
    await active_person(db, payload.assignedTo)
    existing = await db.scalar(
        select(AssignedReview).where(
            AssignedReview.kind == payload.kind,
            AssignedReview.target_id == payload.targetId,
            AssignedReview.deleted_at.is_(None),
        )
    )
    if existing is not None:
        if (
            existing.assigned_to != payload.assignedTo
            or fingerprint(existing.snapshot) != payload.expectedFingerprint
        ):
            raise HTTPException(
                409, "This target already has a review. Inspect it before reassigning."
            )
        return existing  # Lost-response retry: no duplicate assignment, answer reset or audit.
    current, resolved = await context(db, payload.kind, payload.targetId, lock=True)
    if resolved or fingerprint(current) != payload.expectedFingerprint:
        raise _conflict()
    approved = uuid.UUID(current["movieId"]) == MARK_REVIEW_MOVIES[payload.kind]
    wording: dict[str, Any] | None = None
    if payload.kind == WANT_QUESTION and not approved:
        # AG5: any want whose shop listings name another film's year, in its own words.
        words = await want_words(db, payload.targetId, current)
        if words is None:
            raise HTTPException(422, "This want's shop listings name no other film")
        wording = as_wording(words)
    else:
        # The three reviewed subjects AD1 approved, not arbitrary misleading cards.
        if not approved:
            raise HTTPException(422, "This target is not one of the approved review subjects")
        validate_subject(payload.kind, current)
        if payload.kind == WANT_QUESTION:
            wording = as_wording(WORDS[payload.kind])
    review_id = uuid.uuid4()
    inserted = await db.scalar(
        insert(AssignedReview)
        .values(
            id=review_id,
            kind=payload.kind,
            target_id=payload.targetId,
            assigned_to=payload.assignedTo,
            snapshot=current,
            wording=wording,
        )
        .on_conflict_do_nothing()
        .returning(AssignedReview.id)
    )
    if inserted is None:
        # Another assignment won; do not silently accept a different assignee or snapshot.
        raise HTTPException(409, "The review was assigned concurrently. Re-open the list.")
    row = await db.get(AssignedReview, review_id)
    assert row is not None
    audit(
        db,
        row,
        actor,
        {
            "assignedTo": str(row.assigned_to),
            "kind": row.kind,
            "targetId": str(row.target_id),
            "snapshot": current,
            **({"wording": wording} if wording is not None else {}),
        },
        create=True,
    )
    return row


async def proposals(db: AsyncSession) -> list[ReviewProposal]:
    """Find exactly the current approved records. Nothing is inserted, guessed or fetched."""
    await active_person(db, MARK_PROFILE_ID)
    found: list[ReviewProposal] = []
    for kind, movie_id in MARK_REVIEW_MOVIES.items():
        if kind == "titanic_disc":
            query = (
                select(IdentifyDoubt.id)
                .join(
                    CollectionItem,
                    CollectionItem.id == IdentifyDoubt.collection_item_id,
                )
                .where(
                    IdentifyDoubt.movie_id == movie_id, IdentifyDoubt.status == "open", owned_copy()
                )
            )
        elif kind == "wanted_identity":
            query = select(WantedItem.id).where(
                WantedItem.movie_id == movie_id,
                WantedItem.is_active.is_(True),
                WantedItem.deleted_at.is_(None),
            )
        else:
            query = select(CollectionItem.id).where(
                CollectionItem.movie_id == movie_id, owned_copy()
            )
        ids = (await db.scalars(query)).all()
        if len(ids) != 1:
            raise HTTPException(
                409,
                f"{WORDS[kind][0]}: expected one current target, found {len(ids)}. "
                "Review before assigning.",
            )
        current, resolved = await context(db, kind, ids[0])
        if resolved:
            raise _conflict()
        validate_subject(kind, current)
        found.append(
            ReviewProposal(
                kind=cast(ReviewKind, kind),
                targetId=ids[0],
                assignedTo=MARK_PROFILE_ID,
                expectedFingerprint=fingerprint(current),
                title=WORDS[kind][0],
            )
        )
    return found


async def want_proposals(db: AsyncSession) -> list[WantProposal]:
    """AG5: each active want whose shop listings name another film's year and that has not
    asked which film it is, with the words it would ask. Nothing is written or fetched."""
    await active_person(db, MARK_PROFILE_ID)
    assignee = await db.get(Profile, MARK_PROFILE_ID)
    assert assignee is not None  # active_person refused a missing profile
    asked = select(AssignedReview.target_id).where(
        AssignedReview.kind == WANT_QUESTION, AssignedReview.deleted_at.is_(None)
    )
    wants = (
        await db.scalars(
            select(WantedItem.id)
            .join(PriceCheck, PriceCheck.wanted_id == WantedItem.id)
            .where(
                WantedItem.is_active.is_(True),
                WantedItem.deleted_at.is_(None),
                PriceCheck.another_film == ANOTHER_YEAR,
                WantedItem.id.not_in(asked),
            )
            .distinct()
        )
    ).all()
    found: list[WantProposal] = []
    for want_id in wants:
        try:
            current, _resolved = await context(db, WANT_QUESTION, want_id)
        except HTTPException:  # pragma: no cover - its film was deleted since the query
            continue
        words = await want_words(db, want_id, current)
        if words is None:
            continue
        title, question, _evidence, choices = words
        found.append(
            WantProposal(
                kind=WANT_QUESTION,
                targetId=want_id,
                assignedTo=MARK_PROFILE_ID,
                expectedFingerprint=fingerprint(current),
                title=title,
                question=question,
                choices=[{"value": value, "label": label} for value, label in choices],
                assigneeName=assignee.display_name,
            )
        )
    return sorted(found, key=lambda proposal: proposal.title)
