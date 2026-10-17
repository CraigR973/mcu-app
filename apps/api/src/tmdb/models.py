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


class AlternativeTitle(BaseModel):
    """A title the film is also known by in one country — Batch T9.

    "Avengers Assemble" is The Avengers' GB title and "Sicario 2: Soldado" is one of Sicario:
    Day of the Soldado's. TMDB's search already matches these; identification needs them to
    see *why* a result came back.
    """

    title: str
    iso_3166_1: str = ""
    type: str = ""


class AlternativeTitles(BaseModel):
    titles: list[AlternativeTitle] = Field(default_factory=list)


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


#: TMDB's release-date vocabulary. **5 is the one this app wanted for two batches and
#: never asked for**: `RELEASE_TYPES` has carried `4k_uhd_release` and `blu_ray_release`
#: since Batch 17 and nothing ever wrote either, because ingestion only ever read
#: `/movie/upcoming`, which is cinema dates.
TMDB_RELEASE_PREMIERE = 1
TMDB_RELEASE_THEATRICAL_LIMITED = 2
TMDB_RELEASE_THEATRICAL = 3
TMDB_RELEASE_DIGITAL = 4
TMDB_RELEASE_PHYSICAL = 5
TMDB_RELEASE_TV = 6


class ReleaseDate(BaseModel):
    """One dated release of a film in one country.

    ``note`` is free text a contributor typed — *"4K UHD"*, *"Criterion"*, or nothing at
    all — and it is the **only** thing in this payload that can tell a 4K disc from a
    Blu-ray. TMDB's type 5 means "Physical" and no more.
    """

    release_date: str | None = None
    type: int = 0
    certification: str = ""
    note: str = ""


class CountryReleaseDates(BaseModel):
    iso_3166_1: str = ""
    release_dates: list[ReleaseDate] = Field(default_factory=list)


class ReleaseDates(BaseModel):
    """``/movie/{id}/release_dates`` — every country, every type.

    **Community-maintained and patchy**, which is the thing to carry forward rather than
    hide: plenty of films have a GB cinema date and no GB physical one, and a screen that
    implied otherwise would be the failure mode here.
    """

    id: int = 0
    results: list[CountryReleaseDates] = Field(default_factory=list)

    def for_country(self, iso_3166_1: str) -> list[ReleaseDate]:
        for country in self.results:
            if country.iso_3166_1.upper() == iso_3166_1.upper():
                return country.release_dates
        return []


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


class TvSearchResult(BaseModel):
    """One show from ``/search/tv`` — Batch T9 sets TV series aside rather than matching them
    to a film of the same name."""

    id: int
    name: str
    original_name: str = ""
    first_air_date: str | None = None
    popularity: float = 0.0
    vote_count: int = 0
    #: Batch Y3: what the identify panel shows of a series it offers.
    overview: str | None = None
    poster_path: str | None = None

    @property
    def year(self) -> int | None:
        if not self.first_air_date:
            return None
        try:
            return int(self.first_air_date.split("-", 1)[0])
        except (ValueError, IndexError):
            return None


class PersonSearchResult(BaseModel):
    """One person from ``/search/person`` — Batch T9 checks a name the title or a disc's
    grouping gives against that person's films."""

    id: int
    name: str
    known_for_department: str | None = None
    popularity: float = 0.0


class PersonSearchResults(BaseModel):
    page: int = 1
    results: list[PersonSearchResult] = Field(default_factory=list)
    total_pages: int = 0
    total_results: int = 0


class TvSearchResults(BaseModel):
    page: int = 1
    results: list[TvSearchResult] = Field(default_factory=list)
    total_pages: int = 0
    total_results: int = 0


# ---------------------------------------------------------------------------
# A TV series — Batch Y3
#
# ``/tv/{id}`` with ``aggregate_credits``, ``videos`` and ``external_ids`` appended. Written
# from TMDB's published shape, not a captured answer (the cloud session that built it had no
# TMDB key), so everything past the id and name is optional: a field TMDB leaves out or
# nulls must not turn an identification into a 502.
# ---------------------------------------------------------------------------


class TvRole(BaseModel):
    character: str | None = None
    episode_count: int = 0


class TvCastMember(BaseModel):
    """One person across the whole series, from ``aggregate_credits``: their parts are in
    ``roles``, not a single ``character``."""

    id: int
    name: str
    order: int = 0
    profile_path: str | None = None
    roles: list[TvRole] = Field(default_factory=list)
    total_episode_count: int = 0

    @property
    def character(self) -> str | None:
        return next((role.character for role in self.roles if role.character), None)


class TvCrewJob(BaseModel):
    job: str | None = None
    episode_count: int = 0


class TvCrewMember(BaseModel):
    id: int
    name: str
    department: str | None = None
    jobs: list[TvCrewJob] = Field(default_factory=list)


class TvCredits(BaseModel):
    cast: list[TvCastMember] = Field(default_factory=list)
    crew: list[TvCrewMember] = Field(default_factory=list)


class TvCreator(BaseModel):
    id: int
    name: str
    profile_path: str | None = None


class ExternalIds(BaseModel):
    imdb_id: str | None = None


class Keyword(BaseModel):
    id: int
    name: str = ""


class MovieKeywords(BaseModel):
    """``/movie/{id}/keywords``, or the ``keywords`` a full record appends — Batch Y5. A film's
    list is ``keywords``."""

    keywords: list[Keyword] = Field(default_factory=list)


class TvKeywords(BaseModel):
    """``/tv/{id}/keywords``, or the ``keywords`` a full series appends. A series' list is
    ``results``, not ``keywords``: TMDB names them differently."""

    results: list[Keyword] = Field(default_factory=list)


class TvShow(BaseModel):
    id: int
    name: str
    original_name: str | None = None
    overview: str | None = None
    tagline: str | None = None
    first_air_date: str | None = None
    last_air_date: str | None = None
    number_of_seasons: int | None = None
    number_of_episodes: int | None = None
    vote_average: float | None = None
    vote_count: int | None = None
    popularity: float | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    genres: list[Genre] = Field(default_factory=list)
    created_by: list[TvCreator] = Field(default_factory=list)
    aggregate_credits: TvCredits | None = None
    videos: Videos | None = None
    external_ids: ExternalIds | None = None
    #: Batch Y5. Absent unless the request appended it, which ``get_tv_full`` does.
    keywords: TvKeywords | None = None


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
    alternative_titles: AlternativeTitles | None = None
    #: Batch Y5. Absent unless the request appended it, which ``get_movie_full`` does.
    keywords: MovieKeywords | None = None


class PersonMovieCredit(BaseModel):
    """One film in a person's TMDB filmography.

    A deliberately small subset of what ``/person/{id}/movie_credits`` returns. Everything
    here is displayed in the "films you are missing" list, which is the only reason these
    are stored at all — the alternative is a TMDB call per set per page view.
    """

    id: int
    title: str
    release_date: str | None = None
    poster_path: str | None = None
    popularity: float | None = None
    vote_count: int | None = None
    #: Present on the crew half of the response only. "Directing" is the one this app
    #: filters on: TMDB lists a director's producing and writing credits in the same
    #: array, and a "Hitchcock films" set that included everything he ever produced would
    #: not be the set anyone means.
    department: str | None = None
    job: str | None = None
    #: Cast-half only. Used the same way, to keep a bit part out of an actor's set.
    order: int | None = None


class PersonMovieCredits(BaseModel):
    id: int
    cast: list[PersonMovieCredit] = []
    crew: list[PersonMovieCredit] = []
