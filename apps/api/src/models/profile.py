"""The two people who can sign in, and nobody else.

MCU has no public sign-up (`DECISIONS.md` #11). Profiles are seeded by migration and
only ever created by an admin, so this table is expected to hold exactly two rows for
the life of the app.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin

#: Longest display name accepted at login. Also the width of the column, so a name that
#: fits in one fits in the other and login cannot 500 on a `DataError`.
DISPLAY_NAME_MAX_LENGTH = 100

#: A bcrypt hash is 60 characters. Sized exactly so a non-bcrypt value cannot be stored
#: and later handed to `checkpw`.
BCRYPT_HASH_LENGTH = 60


class UserRole(StrEnum):
    """Craig administers, Mark views. Both can read the collection."""

    admin = "admin"
    viewer = "viewer"


class Profile(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    __tablename__ = "profiles"

    #: Typed at login in place of an email address. Unique and compared
    #: case-insensitively — see the functional unique index in migration 002, which is
    #: what actually enforces it; a plain `unique=True` here would let "Craig" and
    #: "craig" both exist and make login ambiguous.
    display_name: Mapped[str] = mapped_column(
        String(DISPLAY_NAME_MAX_LENGTH), nullable=False, index=True
    )

    #: The bcrypt hash of this person's PIN, or ``NULL`` for **no credential**.
    #:
    #: ``NULL`` is the state both profiles are seeded in, and it means the account
    #: cannot be signed into *at all* — not that it can be signed into with anything.
    #: Every read path must say which of the two it means; :func:`src.auth.verify_pin`
    #: returns ``False`` for ``NULL`` rather than reaching bcrypt with a ``None``.
    pin_hash: Mapped[str | None] = mapped_column(String(BCRYPT_HASH_LENGTH), nullable=True)

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        nullable=False,
        server_default=UserRole.viewer.value,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    #: Consecutive failed PIN attempts. Reset to 0 on any successful login.
    #:
    #: This is the **durable** half of the lockout and the reason the acceptance
    #: criterion holds: it lives in Postgres, so a process restart does not hand an
    #: attacker a fresh five attempts. `app-starter` declares the same two fields and
    #: never enforces them (`DECISIONS.md` #11) — here the login route writes both on
    #: a session of its own so the charge survives the handler's rollback.
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    #: When the current lockout expires, or ``NULL`` when not locked.
    locked_until_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    last_login_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Profile {self.display_name} ({self.role})>"


class RefreshToken(Base, UUIDPrimaryKeyMixin):
    """One row per issued refresh token, storing only a SHA-256 digest of it.

    The raw token is returned to the client once and never persisted, so a database
    read cannot mint a session. Rotation revokes the old row and inserts a new one, which
    makes a replayed token detectable rather than merely expired.
    """

    __tablename__ = "refresh_tokens"

    #: ``CASCADE`` because a deleted profile's sessions must not outlive it. Profiles
    #: are soft-deleted in normal operation, and ``get_current_user`` filters those
    #: out, so this fires only on a genuine hard delete.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: SHA-256 hex digest — 64 characters, fixed.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    expires_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    #: Set when the token is rotated or the session is logged out. A row with a
    #: non-``NULL`` value here is spent and must never mint an access token again.
    revoked_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
