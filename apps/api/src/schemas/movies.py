from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class CollectionItemOut(BaseModel):
    id: int
    format: str
    edition: str | None = None
    condition: str
    region: str | None = None
    purchase_price: Decimal | None = None
    purchase_date: date | None = None
    purchase_source: str | None = None
    notes: str | None = None
    resolution: str | None = None
    hdr_format: str | None = None
    audio_formats: list[str] | None = None
    is_for_sale: bool = False

    model_config = {"from_attributes": True}


class CreditOut(BaseModel):
    person_id: int | None = None
    person_name: str | None = None
    credit_type: str
    character: str | None = None
    department: str | None = None
    job: str | None = None
    credit_order: int | None = None
    profile_path: str | None = None

    model_config = {"from_attributes": True}


class MovieListItem(BaseModel):
    id: int
    title: str
    original_title: str | None = None
    release_date: date | None = None
    runtime: int | None = None
    popularity: float | None = None
    vote_average: float | None = None
    vote_count: int | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    genre_ids: list[int] | None = None
    best_format_owned: str | None = None
    best_hdr_owned: str | None = None
    best_audio_owned: str | None = None

    model_config = {"from_attributes": True}


class MovieDetail(MovieListItem):
    overview: str | None = None
    tagline: str | None = None
    status: str | None = None
    budget: int | None = None
    revenue: int | None = None
    imdb_id: str | None = None
    homepage: str | None = None
    cast: list[CreditOut] = []
    crew: list[CreditOut] = []


class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int
    pages: int


class MovieListResponse(BaseModel):
    data: list[MovieListItem]
    meta: PaginationMeta


class MovieDetailResponse(BaseModel):
    data: MovieDetail
