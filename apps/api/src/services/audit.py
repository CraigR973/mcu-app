"""Writing the audit log, in one place.

Every write path in the collection surface records what it did through
:func:`record_action`, so the shape of a ``changes`` diff is decided once rather than
per endpoint. §13.6's audit UI and §3.11's condition history both read these rows back
and both need the diff to mean the same thing everywhere.

The functions here **add to the session and do not commit.** The audit row must land in
the same transaction as the change it describes, or a rolled-back write leaves a log
entry claiming something happened that did not.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.admin_action import AdminAction
from src.models.collection_item import CollectionItem

#: The fields an audit diff reports on, in the order a reader wants them. Restricted to
#: what a person actually edits: ``updated_at`` and the derived columns change on their
#: own and would bury the one field that was really touched.
AUDITED_ITEM_FIELDS = (
    "formats",
    "location",
    "section",
    "shelf",
    "sub_category",
    "notes",
    "condition",
    "has_playback_issues",
    "playback_notes",
    "purchase_price",
    "purchase_source",
    "purchase_date",
    # Batch 24. A scanned product code is part of what was physically added, and a
    # create audit that omitted it could not explain a later cache/collection hit.
    "barcode",
    # Batch 29, §4.4. *"Marking sold … remains in audit"* is only true if the log can see
    # the field move. Without these three the listing endpoint produced an empty diff and
    # therefore no audit row at all — a sale that left no trace, which is the one thing
    # the criterion asks for.
    "listing_status",
    "listing_price",
    "ebay_listing_url",
)


def _jsonable(value: Any) -> Any:
    """Render a column value in a form JSONB can hold and a reader can recognise.

    ``Decimal`` and ``date`` are the two that matter — a price and a purchase date are
    both fields people edit, and both raise ``TypeError`` on the way into JSONB
    otherwise. Stringifying keeps "12.99" readable in the log rather than turning it
    into a float that prints as 12.989999999999998.
    """
    if isinstance(value, Decimal | date | uuid.UUID):
        return str(value)
    return value


def item_snapshot(item: CollectionItem) -> dict[str, Any]:
    """The audited fields of one item, for a create or delete entry."""
    return {name: _jsonable(getattr(item, name)) for name in AUDITED_ITEM_FIELDS}


def diff_snapshots(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """``{field: {"from": old, "to": new}}`` for the fields that actually moved.

    Only changed fields appear. An update that changes one field should read as one
    line in the history, not as thirteen lines twelve of which say "unchanged" —
    §13.6's acceptance is "5 test changes shows 5 entries with correct diffs", and a
    diff that lists everything is not a correct diff.
    """
    return {
        name: {"from": before[name], "to": after[name]}
        for name in AUDITED_ITEM_FIELDS
        if before.get(name) != after.get(name)
    }


def record_action(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    action_type: str,
    target_table: str,
    target_id: uuid.UUID | str,
    changes: dict[str, Any] | None = None,
) -> AdminAction:
    """Stage one audit row on the caller's session.

    Not committed here on purpose: the caller commits the change and its log entry
    together, so the two cannot disagree about whether something happened.
    """
    entry = AdminAction(
        id=uuid.uuid4(),
        user_id=user_id,
        action_type=action_type,
        target_table=target_table,
        target_id=str(target_id),
        changes=changes,
    )
    db.add(entry)
    return entry
