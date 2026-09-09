"""Discs lent to people — roadmap §3.8 and §6.6's lending tracker.

A loan is about a **specific disc**, not a film: §3.8's foreign key is
``collection_item_id``, and that is right — lending "your copy of Heat" means one physical
object left the house, and if you own it on 4K and DVD only one of them did.
"""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin

#: ``admin_actions.target_table`` for a loan.
LOANS_TABLE = "loans"


class Loan(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    __tablename__ = "loans"

    collection_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collection_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: Free text, not a profile id. The people who borrow discs are friends and family,
    #: not users of this app — there are exactly two of those and neither borrows from
    #: the other.
    borrower_name: Mapped[str] = mapped_column(String(255), nullable=False)

    #: ``DATE``, like ``watch_log.watched_at`` and for the same reason: people remember
    #: lending something "last Saturday", not at an instant.
    lent_date: Mapped[date] = mapped_column(Date, nullable=False)

    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    #: NULL until it comes back. This column *is* the open/closed state — there is no
    #: separate status to disagree with it.
    returned_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    #: §3.8's column, written by `services/reminders.py::notify_overdue_loans` since
    #: Batch 11. It carried no writer at all from Batch 15 until then. The flag lives on
    #: the loan because that is where the fact belongs, and because a reminder that fires
    #: twice is worse than one that fires late.
    reminder_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Loan {self.collection_item_id} to {self.borrower_name!r}>"
