from datetime import datetime

from sqlalchemy import DateTime

from src.models.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin, _utcnow


class ExampleModel(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
    __tablename__ = "example_models"


def test_utcnow_returns_naive_utc_datetime() -> None:
    result = _utcnow()
    assert isinstance(result, datetime)
    assert result.tzinfo is None


def test_base_mixins_use_uuid_and_naive_timestamps() -> None:
    assert ExampleModel.__table__.c.id.primary_key is True

    created_at = ExampleModel.__table__.c.created_at
    updated_at = ExampleModel.__table__.c.updated_at
    assert isinstance(created_at.type, DateTime)
    assert created_at.type.timezone is False
    assert isinstance(updated_at.type, DateTime)
    assert updated_at.type.timezone is False
