import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


#: The database-side default for a naive-UTC column. A bare ``now()`` is cast to a naive
#: timestamp in the *session's* time zone, so on a database not set to UTC it writes local
#: time, while ``set_updated_at`` writes UTC — and the stale-edit guard compares the two
#: (migration ``063``).
UTC_NOW = text("timezone('utc', now())")


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=UTC_NOW,
        default=_utcnow,
        nullable=False,
    )


class UpdatedAtMixin(TimestampMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=UTC_NOW,
        nullable=False,
    )
