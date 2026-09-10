"""The Blu-ray.com integration's halt switch — `DECISIONS.md` #110.

**One row, and it is a promise rather than a setting.** #110 makes the owner's risk
acceptance conditional: a `403`, a `429`, an explicit objection or a hosting complaint
*"halts the whole integration; resuming after any of those requires a new owner decision."*
Held in memory that promise lasts until the next deploy, which is no promise at all.
"""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base

#: The only id this table ever has.
SINGLETON_ID = 1


class SpecsIntegrationState(Base):
    __tablename__ = "specs_integration_state"
    __table_args__ = (CheckConstraint("id = 1", name="ck_specs_integration_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=SINGLETON_ID)

    halted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Why. Read months later by whoever decides whether resuming is allowed.
    halted_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    halted_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    last_fetch_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    #: How many pages this deployment has ever fetched. #110 bounds the access; a number
    #: nobody counted cannot be shown to be within its bounds.
    fetch_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<SpecsIntegrationState halted={self.halted} fetches={self.fetch_count}>"
