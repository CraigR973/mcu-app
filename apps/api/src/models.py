from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, Float, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    original_title: Mapped[str | None] = mapped_column(String)
    overview: Mapped[str | None] = mapped_column(Text)
    tagline: Mapped[str | None] = mapped_column(String)
    release_date: Mapped[date | None] = mapped_column(Date)
    runtime: Mapped[int | None] = mapped_column(Integer)
    popularity: Mapped[float | None] = mapped_column(Float)
    vote_average: Mapped[float | None] = mapped_column(Float)
    vote_count: Mapped[int | None] = mapped_column(Integer)
    adult: Mapped[bool | None] = mapped_column(Boolean)
    status: Mapped[str | None] = mapped_column(String)
    budget: Mapped[int | None] = mapped_column(BigInteger)
    revenue: Mapped[int | None] = mapped_column(BigInteger)
    imdb_id: Mapped[str | None] = mapped_column(String)
    homepage: Mapped[str | None] = mapped_column(String)
    poster_path: Mapped[str | None] = mapped_column(String)
    backdrop_path: Mapped[str | None] = mapped_column(String)
    genre_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    # Derived fields maintained by migration 0015 triggers
    best_format_owned: Mapped[str | None] = mapped_column(String)
    best_hdr_owned: Mapped[str | None] = mapped_column(String)
    best_audio_owned: Mapped[str | None] = mapped_column(String)


class MovieCredit(Base):
    __tablename__ = "movie_credits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    movie_id: Mapped[int] = mapped_column(Integer, nullable=False)
    person_id: Mapped[int | None] = mapped_column(Integer)
    person_name: Mapped[str | None] = mapped_column(String)
    credit_type: Mapped[str] = mapped_column(String, nullable=False)
    character: Mapped[str | None] = mapped_column(String)
    department: Mapped[str | None] = mapped_column(String)
    job: Mapped[str | None] = mapped_column(String)
    credit_order: Mapped[int | None] = mapped_column(Integer)
    profile_path: Mapped[str | None] = mapped_column(String)


class CollectionItem(Base):
    __tablename__ = "collection_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    movie_id: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(Text, nullable=False)
    edition: Mapped[str | None] = mapped_column(Text)
    condition: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str | None] = mapped_column(Text)
    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    purchase_date: Mapped[date | None] = mapped_column(Date)
    purchase_source: Mapped[str | None] = mapped_column(Text)
    barcode: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(Text)
    video_codec: Mapped[str | None] = mapped_column(Text)
    hdr_format: Mapped[str | None] = mapped_column(Text)
    audio_formats: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    aspect_ratio: Mapped[str | None] = mapped_column(Text)
    cover_photo_url: Mapped[str | None] = mapped_column(Text)
    is_for_sale: Mapped[bool] = mapped_column(Boolean, nullable=False)
    asking_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    listing_url: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
