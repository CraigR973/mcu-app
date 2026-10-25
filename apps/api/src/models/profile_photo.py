"""One replaceable, private photo per person (AA7), separate from credentials."""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ProfilePhoto(Base):
    __tablename__ = "profile_photos"
    __table_args__ = (
        CheckConstraint("octet_length(data) BETWEEN 1 AND 307200", name="ck_profile_photo_size"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
