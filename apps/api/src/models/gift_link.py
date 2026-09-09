"""Shareable wanted-list links — roadmap §3.21 and §6.26.

**The app's second unauthenticated surface**, after Batch 17's `.ics` feed. The URL is the
whole credential, so the slug is 128 bits and its own column rather than §3.21's primary
key — §6.26's worked example is eight hex characters, which is enumerable, and the thing
being enumerated is a named person's wish list.
"""

import secrets
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDPrimaryKeyMixin

GIFT_LINKS_TABLE = "gift_links"

#: 16 bytes → 128 bits → ~22 URL-safe characters. Sized as a credential, because that is
#: what it is: anyone holding the URL can read the list.
SLUG_BYTES = 16


def new_slug() -> str:
    return secrets.token_urlsafe(SLUG_BYTES)


class GiftLink(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "gift_links"

    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)

    #: §3.21's "optional filters (max price, genres, formats)". Validated against a closed
    #: model before it is written, the same way smart collections are — this one is read by
    #: an **unauthenticated** endpoint, so an unrecognised key must never survive to become
    #: part of a query.
    filter_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    #: §6.26 step 5: "track view count". Incremented by an unauthenticated request, which
    #: is why the public endpoint is rate-limited — it is the one place a stranger can
    #: cause a write.
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    #: "Deactivated without deleting" — §3.21's own words. Distinct from `deleted_at`, the
    #: same distinction Batch 18 drew for `wanted_list.is_active`.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, index=True
    )

    def is_usable(self, now: datetime) -> bool:
        """Whether this link should answer at all.

        Every reason it might not — deleted, deactivated, expired — collapses to the same
        answer at the endpoint: a 404 identical to a slug that never existed. A visitor
        cannot tell "this expired" from "this was never real", which is what stops the
        public surface confirming guesses.
        """
        if self.deleted_at is not None or not self.is_active:
            return False
        return self.expires_at is None or self.expires_at > now
