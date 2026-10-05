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

    #: The borrower's name as text, always — a friend's, or one of the two people's. It was
    #: the only borrower column until Batch W3, on the reasoning that neither person borrows
    #: from the other; Craig does (`DECISIONS.md` #249), so ``borrower_profile_id`` says when
    #: the borrower is one of them.
    borrower_name: Mapped[str] = mapped_column(String(255), nullable=False)

    #: Set when the borrower is one of the people who use the app — "I'm borrowing it" —
    #: and null for anyone else. Migration 048. The reminder words itself to the borrower
    #: from this ("You've had …"), which a name compared as text could not do safely.
    borrower_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL", name="fk_loans_borrower_profile"),
        nullable=True,
        index=True,
    )

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
