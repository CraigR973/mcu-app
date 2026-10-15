"""Find the TV series that were matched to a film of the same name — Batch Y3.

Mark, 15 Oct: Band of Brothers and 11.22.63 were identified as films, and he expects more.
Before Y3 the app could only match films, so a series' title could find nothing better than
an obscure film that shares it. This reads every identified film on the shelf, asks TMDB's
series index for its title, and names the ones that look like a series:

- **A series of the same title** (:func:`titles.compare`, ``same_title``), and one of:
- that series has at least :data:`VOTES_RATIO` times the film's TMDB votes, and at least
  :data:`MIN_SERIES_VOTES` (Band of Brothers: 4,100 against 3); or
- a disc of it is grouped under "TV", or a spreadsheet title identification replaced reads
  as a series ("Complete Series", "Series 1 - 3"), in T9's own words (:func:`parse_title`).

**It changes nothing.** The report links each film's page, where "Correct match" offers the
series. A film that merely shares a better-known series' name (Fargo, 1996, against Fargo,
2014) is left alone unless the votes say otherwise; one that slips through is a line in a
report for someone to read, not a change.
"""

from __future__ import annotations

import csv
import html
import io
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
from sqlalchemy import exists, select
from sqlalchemy.sql import Select

from src.models.collection_item import CollectionItem, owned_copy
from src.models.identify import MovieTitleAlias
from src.models.movie import Movie
from src.services.identify.titles import compare, parse_title
from src.tmdb.models import TvSearchResult, TvSearchResults

#: The series must be this many times better known than the film it was matched to.
VOTES_RATIO = 5
#: And known at all: a series with a handful of votes says nothing about a film with fewer.
MIN_SERIES_VOTES = 50


class SeriesSearch(Protocol):
    async def search_tv(self, query: str) -> TvSearchResults: ...


@dataclass(frozen=True)
class IdentifiedFilm:
    movie_id: uuid.UUID
    title: str
    year: int | None
    tmdb_id: int
    votes: int
    #: Spreadsheet titles identification replaced (``movie_title_aliases``).
    replaced_titles: tuple[str, ...] = ()
    #: The groupings of its discs on the shelf ("TV", "Clint Eastwood").
    groupings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Suspect:
    film: IdentifiedFilm
    series: TvSearchResult
    reasons: tuple[str, ...]

    @property
    def ratio(self) -> float:
        return self.series.vote_count / max(self.film.votes, 1)


@dataclass
class CheckResult:
    looked_at: int = 0
    suspects: list[Suspect] = field(default_factory=list)
    #: Titles TMDB failed to answer for, so a rerun knows what it did not check.
    failed: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Reading the shelf: one definition, run in a session or over HTTPS
# ---------------------------------------------------------------------------


def _identified_as_film() -> list[Any]:
    return [Movie.deleted_at.is_(None), Movie.tmdb_id.is_not(None), Movie.tmdb_tv_id.is_(None)]


def _identified_on_shelf() -> list[Any]:
    on_shelf = exists().where(CollectionItem.movie_id == Movie.id, owned_copy())
    return [*_identified_as_film(), on_shelf]


def films_query() -> Select[Any]:
    return (
        select(Movie.id, Movie.title, Movie.year, Movie.tmdb_id, Movie.tmdb_vote_count)
        .where(*_identified_on_shelf())
        .order_by(Movie.title, Movie.id)
    )


def replaced_titles_query() -> Select[Any]:
    return (
        select(MovieTitleAlias.movie_id, MovieTitleAlias.title)
        .join(Movie, Movie.id == MovieTitleAlias.movie_id)
        .where(*_identified_on_shelf())
    )


def groupings_query() -> Select[Any]:
    return (
        select(CollectionItem.movie_id, CollectionItem.sub_category)
        .join(Movie, Movie.id == CollectionItem.movie_id)
        # Its own discs on the shelf already say the film is there.
        .where(*_identified_as_film(), owned_copy(), CollectionItem.sub_category.is_not(None))
        .distinct()
    )


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def assemble(
    films: Iterable[Sequence[Any]],
    replaced: Iterable[Sequence[Any]],
    groupings: Iterable[Sequence[Any]],
) -> list[IdentifiedFilm]:
    """The three reads' rows as films. Values may be Postgres' text (the HTTPS path) or
    Python's own (a session), so each is read either way."""
    titles: dict[str, list[str]] = {}
    for movie_id, title in replaced:
        titles.setdefault(str(movie_id), []).append(str(title))
    grouped: dict[str, list[str]] = {}
    for movie_id, grouping in groupings:
        grouped.setdefault(str(movie_id), []).append(str(grouping))
    out: list[IdentifiedFilm] = []
    for movie_id, title, year, tmdb_id, votes in films:
        key = str(movie_id)
        out.append(
            IdentifiedFilm(
                movie_id=uuid.UUID(key),
                title=str(title),
                year=_int(year),
                tmdb_id=_int(tmdb_id) or 0,
                votes=_int(votes) or 0,
                replaced_titles=tuple(sorted(titles.get(key, []))),
                groupings=tuple(sorted(grouped.get(key, []))),
            )
        )
    return out


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------


def _same_title(title: str, show: TvSearchResult) -> bool:
    names = [show.name, *([show.original_name] if show.original_name else [])]
    return any(compare(title, name).same_title for name in names)


def judge(film: IdentifiedFilm, found: TvSearchResults) -> Suspect | None:
    """Whether TMDB's series answer for this film's title makes it look like a series."""
    same = [show for show in found.results if _same_title(film.title, show)]
    if not same:
        return None
    series = max(same, key=lambda show: (show.vote_count, show.popularity))
    reasons: list[str] = []
    if series.vote_count >= MIN_SERIES_VOTES and series.vote_count >= VOTES_RATIO * max(
        film.votes, 1
    ):
        reasons.append(
            f"TMDB's series has {series.vote_count:,} votes; the film it was matched to has "
            f"{film.votes:,}."
        )
    for replaced in film.replaced_titles:
        sign = parse_title(replaced).tv
        if sign:
            reasons.append(f"Its spreadsheet title, '{replaced}': {sign}.")
            break
    for grouping in film.groupings:
        sign = parse_title(film.title, grouping).tv
        if sign:
            reasons.append(f"{sign[0].upper()}{sign[1:]}.")
            break
    return Suspect(film, series, tuple(reasons)) if reasons else None


async def check(
    films: Sequence[IdentifiedFilm],
    tmdb: SeriesSearch,
    *,
    progress: Callable[[int, int], None] | None = None,
) -> CheckResult:
    """Ask TMDB's series index for each film's title; strongest suspects first."""
    result = CheckResult()
    for index, film in enumerate(films, start=1):
        try:
            found = await tmdb.search_tv(film.title)
        except (httpx.HTTPError, RuntimeError):
            # TMDB's client raises these once its retries are spent (``TMDBRefused`` is a
            # RuntimeError). One title it fails on is noted, not fatal.
            result.failed.append(film.title)
        else:
            result.looked_at += 1
            suspect = judge(film, found)
            if suspect is not None:
                result.suspects.append(suspect)
        if progress is not None:
            progress(index, len(films))
    result.suspects.sort(key=lambda s: (len(s.reasons), s.ratio), reverse=True)
    return result


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------

_STYLE = """
body{font:15px/1.5 system-ui,sans-serif;margin:24px;color:#1c1917;background:#fafaf9}
h1{font-size:22px;margin:0 0 4px}p.lede{color:#57534e;margin:0 0 20px;max-width:60rem}
table{border-collapse:collapse;width:100%;background:#fff}
th,td{border-bottom:1px solid #e7e5e4;padding:8px 10px;text-align:left;vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#78716c}
td.n{text-align:right;font-variant-numeric:tabular-nums}a{color:#9f1239}
ul{margin:0;padding-left:18px}
"""


def render_html(result: CheckResult, *, app_url: str) -> str:
    base = app_url.rstrip("/")
    rows: list[str] = []
    for s in result.suspects:
        film, series = s.film, s.series
        reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in s.reasons)
        rows.append(
            "<tr>"
            f"<td><a href='{base}/movies/{film.movie_id}'>{html.escape(film.title)}</a>"
            f"<br><small>film {film.year or '?'} · "
            f"<a href='https://www.themoviedb.org/movie/{film.tmdb_id}'>TMDB</a></small></td>"
            f"<td class='n'>{film.votes:,}</td>"
            f"<td>{html.escape(series.name)}<br><small>series {series.year or '?'} · "
            f"<a href='https://www.themoviedb.org/tv/{series.id}'>TMDB</a></small></td>"
            f"<td class='n'>{series.vote_count:,}</td>"
            f"<td><ul>{reasons}</ul></td>"
            "</tr>"
        )
    failed = (
        f"<p>TMDB did not answer for {len(result.failed)}: "
        f"{html.escape(', '.join(result.failed))}. Run it again for those.</p>"
        if result.failed
        else ""
    )
    body = (
        "<table><thead><tr><th>Matched as the film</th><th>Votes</th><th>TMDB's series</th>"
        "<th>Votes</th><th>Why</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        if rows
        else "<p>None found.</p>"
    )
    return (
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Series matched as films</title><style>{_STYLE}</style>"
        "<h1>Series matched as films</h1>"
        f"<p class='lede'>{len(result.suspects)} of the {result.looked_at} identified films on "
        "the shelf look like a TV series. Open each, press <b>Correct match</b>, and choose the "
        "series under <b>TV series</b> if it is one. Nothing here has been changed.</p>"
        f"{failed}{body}"
    )


def render_csv(result: CheckResult, *, app_url: str) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "film page",
            "title",
            "film year",
            "film votes",
            "series",
            "series year",
            "series votes",
            "series TMDB id",
            "why",
        ]
    )
    base = app_url.rstrip("/")
    for s in result.suspects:
        writer.writerow(
            [
                f"{base}/movies/{s.film.movie_id}",
                s.film.title,
                s.film.year or "",
                s.film.votes,
                s.series.name,
                s.series.year or "",
                s.series.vote_count,
                s.series.id,
                " ".join(s.reasons),
            ]
        )
    return out.getvalue()
