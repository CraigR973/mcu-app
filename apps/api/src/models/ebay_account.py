"""Each person's eBay sign-in — Batch T8b, `DECISIONS.md` #142, #216, #227, #245.

**The first personal third-party credential this app holds** (#142). So the tokens are never
stored as text: each is sealed with AES-256-GCM under a key derived from ``EBAY_TOKEN_KEY``
and bound to the profile it belongs to (`services/ebay_account/crypto.py`), and nothing
else about the eBay account is kept. Disconnecting deletes the row; so does eBay refusing
the token. The read-only role is granted neither table.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDPrimaryKeyMixin


class EbayAccount(Base, UUIDPrimaryKeyMixin):
    """One person's connected eBay account: two sealed tokens and when they lapse."""

    __tablename__ = "ebay_accounts"
    __table_args__ = (
        CheckConstraint(
            "length(access_token_sealed) > 28 AND length(refresh_token_sealed) > 28",
            name="ck_ebay_accounts_sealed",
        ),
        UniqueConstraint("profile_id", name="uq_ebay_accounts_profile"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    access_token_sealed: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    access_expires_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    refresh_token_sealed: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    refresh_expires_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    #: The scopes the person consented to, space-separated as eBay takes them.
    scopes: Mapped[str] = mapped_column(Text, nullable=False)
    connected_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    refreshed_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    last_used_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid; never the tokens
        return f"<EbayAccount profile={self.profile_id} since={self.connected_utc:%Y-%m-%d}>"


class EbayConnectState(Base, UUIDPrimaryKeyMixin):
    """The one-time ``state`` a "Connect eBay" sends to eBay, kept only as its hash."""

    __tablename__ = "ebay_connect_states"
    __table_args__ = (
        CheckConstraint("length(state_hash) = 64", name="ck_ebay_connect_states_hash"),
        CheckConstraint("expires_utc > created_utc", name="ck_ebay_connect_states_expiry"),
        Index("ix_ebay_connect_states_profile", "profile_id"),
        UniqueConstraint("state_hash", name="uq_ebay_connect_states_hash"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    state_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    expires_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    used_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
