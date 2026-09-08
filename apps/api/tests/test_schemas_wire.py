"""The wire-level UTC annotation.

Runs without a database, so unlike the rest of Batch 7 this one is provable on the
development machine (`STATUS.md` gotcha 15).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta, timezone

from pydantic import BaseModel

from src.schemas.collection import AuditEntryResponse, CollectionItemResponse
from src.schemas.wire import UtcDatetime, UtcDatetimeIn


class _Model(BaseModel):
    at: UtcDatetime | None = None


def test_a_naive_column_value_is_stamped_as_utc() -> None:
    """The defect this exists to prevent.

    Every domain timestamp is stored ``DateTime(timezone=False)`` holding UTC. Without
    the annotation the wire carries ``2026-09-08T14:00:00``, which ``new Date()`` reads
    as *local* time — an hour or more wrong, silently, for anyone not on UTC.
    """
    assert _Model(at=datetime(2026, 9, 8, 14, 0, 0)).model_dump(mode="json") == {
        "at": "2026-09-08T14:00:00Z"
    }


def test_an_aware_value_is_converted_rather_than_relabelled() -> None:
    aware = datetime(2026, 9, 8, 15, 0, 0, tzinfo=timezone(timedelta(hours=1)))
    assert _Model(at=aware).model_dump(mode="json") == {"at": "2026-09-08T14:00:00Z"}


def test_none_stays_none() -> None:
    assert _Model().model_dump(mode="json") == {"at": None}


def test_utcnow_round_trips_through_the_annotation() -> None:
    """The exact shape every router writes: ``datetime.now(UTC)`` with the tzinfo dropped."""
    now = datetime.now(UTC).replace(tzinfo=None)
    serialised = _Model(at=now).model_dump(mode="json")["at"]
    assert isinstance(serialised, str)
    assert serialised.endswith("Z")
    assert datetime.fromisoformat(serialised).astimezone(UTC).replace(tzinfo=None) == now


def test_the_response_models_that_carry_timestamps_use_it() -> None:
    """A field added later without the annotation is the regression to catch."""
    item = CollectionItemResponse(
        id=uuid.uuid4(),
        movieId=uuid.uuid4(),
        movieTitle="Heat",
        formats=["4k_uhd"],
        locationLabel="Front 2nd",
        conditionUpdatedAt=datetime(2026, 9, 8, 14, 0, 0),
        hasPlaybackIssues=False,
        listingStatus="in_collection",
        updatedAt=datetime(2026, 9, 8, 15, 0, 0, 123456),
        deletedAt=datetime(2026, 9, 8, 15, 30, 0),
    )
    dumped = item.model_dump(mode="json")
    assert dumped["conditionUpdatedAt"] == "2026-09-08T14:00:00Z"
    assert dumped["deletedAt"] == "2026-09-08T15:30:00Z"
    # Microseconds survive: Batch 8's stale-edit check compares this value back against
    # the column, so a truncated one would make a current edit read as stale.
    assert dumped["updatedAt"] == "2026-09-08T15:00:00.123456Z"

    entry = AuditEntryResponse(
        id=uuid.uuid4(),
        actionType="update",
        targetTable="collection_items",
        targetId=str(uuid.uuid4()),
        createdAt=datetime(2026, 9, 8, 14, 0, 0),
    )
    assert entry.model_dump(mode="json")["createdAt"] == "2026-09-08T14:00:00Z"


def test_an_inbound_timestamp_is_normalised_for_comparison_with_a_column() -> None:
    """``UtcDatetimeIn`` is the half that makes the stale-edit check possible.

    A client sends back exactly what was serialised, so it arrives *aware*. Comparing an
    aware datetime with the naive column value raises ``TypeError`` rather than answering
    wrongly — which is better than a silent mistake, but still a 500.
    """

    class _In(BaseModel):
        at: UtcDatetimeIn | None = None

    parsed = _In(at="2026-09-08T15:00:00.123456Z")  # type: ignore[arg-type]
    assert parsed.at == datetime(2026, 9, 8, 15, 0, 0, 123456)
    assert parsed.at.tzinfo is None

    # An offset other than Z is converted, not merely stripped.
    shifted = _In(at="2026-09-08T16:00:00+01:00")  # type: ignore[arg-type]
    assert shifted.at == datetime(2026, 9, 8, 15, 0, 0)

    # And it serialises back out through the same rule, so a value can round-trip.
    assert parsed.model_dump(mode="json")["at"] == "2026-09-08T15:00:00.123456Z"
