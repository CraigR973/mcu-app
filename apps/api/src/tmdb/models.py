from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Genre(BaseModel):
    id: int
    name: str


class ProductionCompany(BaseModel):
    id: int
    name: str
    origin_country: str
    logo_path: str | None = None


class ProductionCountry(BaseModel):
    iso_3166_1: str
    name: str


class SpokenLanguage(BaseModel):
    iso_639_1: str
    name: str
    english_name: str = ""


class CastMember(BaseModel):
    id: int
    name: str
    character: str
    order: int
    profile_path: str | None = None
    credit_id: str


class CrewMember(BaseModel):
    id: int
    name: str
    job: str
    department: str
    profile_path: str | None = None
    credit_id: str


class Credits(BaseModel):
    cast: list[CastMember] = Field(default_factory=list)
    crew: list[CrewMember] = Field(default_factory=list)


class Video(BaseModel):
    id: str
    key: str
    site: str
    type: str
    name: str
    official: bool = False


class Videos(BaseModel):
    results: list[Video] = Field(default_factory=list)


class WatchProvider(BaseModel):
    provider_id: int
    provider_name: str
    logo_path: str


class WatchProviderCountry(BaseModel):
    link: str
    flatrate: list[WatchProvider] = Field(default_factory=list)
    rent: list[WatchProvider] = Field(default_factory=list)
    buy: list[WatchProvider] = Field(default_factory=list)


class WatchProviders(BaseModel):
    results: dict[str, WatchProviderCountry] = Field(default_factory=dict)


class SearchResult(BaseModel):
    """A single result row from ``/search/movie``."""

    id: int
    title: str
    original_title: str
    overview: str = ""
    release_date: str | None = None
    popularity: float = 0.0
    vote_average: float = 0.0
    vote_count: int = 0
    poster_path: str | None = None
    backdrop_path: str | None = None
    adult: bool = False
    video: bool = False
    genre_ids: list[int] = Field(default_factory=list)
    original_language: str | None = None

    @property
    def year(self) -> int | None:
        if not self.release_date:
            return None
        try:
            return int(self.release_date.split("-", 1)[0])
        except (ValueError, IndexError):
            return None


class SearchResults(BaseModel):
    page: int = 1
    results: list[SearchResult] = Field(default_factory=list)
    total_pages: int = 0
    total_results: int = 0


class Movie(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    title: str
    original_title: str
    overview: str
    release_date: str | None = None
    runtime: int | None = None
    tagline: str | None = None
    status: str | None = None
    budget: int = 0
    revenue: int = 0
    vote_average: float = 0.0
    vote_count: int = 0
    popularity: float = 0.0
    adult: bool = False
    video: bool = False
    imdb_id: str | None = None
    original_language: str | None = None
    homepage: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    belongs_to_collection: dict[str, Any] | None = None
    genres: list[Genre] = Field(default_factory=list)
    production_companies: list[ProductionCompany] = Field(default_factory=list)
    production_countries: list[ProductionCountry] = Field(default_factory=list)
    spoken_languages: list[SpokenLanguage] = Field(default_factory=list)
    # append_to_response fields
    credits: Credits | None = None
    videos: Videos | None = None
    watch_providers: WatchProviders | None = Field(None, alias="watch/providers")
