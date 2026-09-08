"""The audit log, per roadmap §3.20.

One row per write an admin performs, holding who did it, what they did, which row it
happened to, and a field-level diff. Two things read it: §13.6's audit log UI, and
§3.11's condition history on the film detail page — the latter being why the
``(target_table, target_id)`` index exists.

**Nothing here points at the row it describes.** ``target_id`` is TEXT with no foreign
key (`DECISIONS.md` #5): the log's entire purpose is to outlive what it records, and a
foreign key would either refuse the delete or take the evidence with it.
"""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

#: §3.20's action vocabulary, mirrored by the CHECK constraint in migration 008.
ACTION_TYPES = ("create", "update", "delete", "restore", "bulk_import")

#: The only table Batch 7 writes audit rows for. ``target_table`` is a string rather
#: than an enum because §13.5's trash spans several tables, but restricting what this
#: batch will *accept* keeps a typo from creating a bucket nothing can ever read back.
COLLECTION_ITEMS_TABLE = "collection_items"


class AdminAction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "admin_actions"

    #: ``SET NULL`` rather than ``CASCADE``: the record of what someone did must not be
    #: erased by deleting them. Nullable for the same reason — a row whose actor is gone
    #: is still evidence, and ``changes`` still says what happened.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_table: Mapped[str] = mapped_column(String(50), nullable=False)

    #: TEXT, and deliberately not a foreign key — see the module docstring.
    target_id: Mapped[str] = mapped_column(Text, nullable=False)

    #: ``{"condition": {"from": "good", "to": "damaged"}}`` for an update; the created
    #: or deleted row's readable fields for a create/delete. NULL only if a caller
    #: genuinely has nothing to say, which no current path does.
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    #: ``created_at`` from :class:`TimestampMixin` *is* §3.20's ``timestamp`` column.
    #: There is no ``updated_at``: an audit row is a statement about a moment and the
    #: application has no path that edits one.

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AdminAction {self.action_type} {self.target_table}/{self.target_id}>"
