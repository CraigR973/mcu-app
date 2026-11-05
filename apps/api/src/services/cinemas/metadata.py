"""TMDB candidates for programme films, looked up within the run's budget — AC3 (#335).

AB6 kept a title-only match from ever becoming an identity, and spent 12 requests a run doing
it. AC3 (#335, superseding the run rule of #326, #327 and #330) identifies films automatically
when a fact agrees (`identity.py`), so this module's job is to fetch the candidates that rule
weighs: one search per distinct film, then each exact-title candidate's details with its
credits and UK release dates in the same answer. Two requests for most films.

The budget: at most 48 TMDB requests a run, and never more than the programme left of the
run's 120 (with a margin of four), so the existing per-run caps hold. On 5 Nov the programme had
77 distinct films to look up; at about two requests each that is four runs, and the 30-day
positive and 7-day negative caches mean a film is looked up again only when its listing
changes or its record expires.
"""

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import date, timedelta
from typing import Annotated, Any, Literal
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, ConfigDict, Field, NaiveDatetime, model_validator

from src.clock import utcnow
from src.services.cinemas import identity
from src.services.cinemas.domain import Showing, Snapshot, SourceError
from src.services.cinemas.fetch import METADATA_CAP, Budget, Refused
from src.services.cinemas.venues import BY_SLUG

Text = Annotated[str, Field(min_length=1, max_length=500)]
MovieId = Annotated[int, Field(strict=True, gt=0, lt=2**31)]
FilmKey = tuple[str, str]

#: Exact-title candidates read in detail per film: enough for a remake and its original.
DETAILED = 3


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReleaseEvent(EvidenceModel):
    date: date
    type: Literal[2, 3]
    note: str = Field(default="", max_length=200)


class Candidate(EvidenceModel):
    tmdb_id: MovieId
    title: Text
    original_title: Text
    directors: list[Text] = Field(default_factory=list, max_length=10)
    runtime: int | None = Field(default=None, gt=0, le=1000)
    imdb_id: str | None = Field(default=None, pattern=r"^tt\d{7,10}$")
    primary_release_date: date | None = None
    gb_theatrical: list[ReleaseEvent] = Field(default_factory=list, max_length=50)
    #: AC3: for AC4's posters. Never fetched separately.
    poster_path: str | None = Field(default=None, max_length=200)
    #: AC3: TMDB's vote count, for Craig's optional "famous sole match" rule at the checkpoint.
    vote_count: int = Field(default=0, ge=0)

    def as_identity(self) -> identity.Candidate:
        return identity.Candidate(
            tmdb_id=self.tmdb_id,
            title=self.title,
            original_title=self.original_title,
            release_date=self.primary_release_date,
            uk_cinema=tuple(sorted(e.date for e in self.gb_theatrical)),
            directors=tuple(self.directors),
            runtime=self.runtime,
            imdb_id=self.imdb_id,
            poster_path=self.poster_path,
        )


class Metadata(EvidenceModel):
    source: Text
    film_key: str = Field(min_length=1, max_length=300)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    fetched_utc: NaiveDatetime
    #: "candidate": exact-title films were found and read; "missing": none was.
    #: "ambiguous" is AB6's, kept so its stored records still read.
    state: Literal["candidate", "ambiguous", "missing"]
    candidate: Candidate | None = None
    search_candidates: list[MovieId] = Field(default_factory=list, max_length=20)
    #: AC3: every exact-title film read in detail; `identity.identify` decides among them.
    candidates: list[Candidate] = Field(default_factory=list, max_length=DETAILED)
    #: Which rule's lookup made it. AB6's read at most one film, by a narrower title match, so
    #: it cannot answer #335's rule: an AB6 record still reads, but is looked up again.
    rule: Literal["ab6", "ac3"] = "ab6"

    @model_validator(mode="after")
    def consistent(self) -> "Metadata":
        if self.state == "missing" and (self.candidate or self.candidates):
            raise ValueError("A missing record holds no candidate")
        return self

    def fresh(self) -> bool:
        age = utcnow() - self.fetched_utc
        return timedelta(0) <= age < timedelta(days=30 if self.state == "candidate" else 7)

    def identities(self) -> list[identity.Candidate]:
        found = self.candidates or ([self.candidate] if self.candidate else [])
        return [c.as_identity() for c in found]


class MappingPick(EvidenceModel):
    source: Text
    film_key: str = Field(min_length=1, max_length=300)
    tmdb_id: MovieId


def fingerprint(row: Showing) -> str:
    value = {
        "title": row.title,
        "tmdbId": row.tmdb_id,
        "imdbId": row.imdb_id,
        "facts": row.identity_facts,
        "sourceRelease": row.source_release.isoformat() if row.source_release else None,
    }
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def facts_of(row: Showing) -> identity.Facts:
    """What the source says beyond the title, in `identity`'s terms."""
    director = row.identity_facts.get("director")
    runtime = row.identity_facts.get("runtimeMinutes")
    return identity.Facts(
        release=row.source_release,
        director=director if isinstance(director, str) else None,
        runtime=runtime if isinstance(runtime, int) else None,
        tmdb_id=row.tmdb_id,
        imdb_id=row.imdb_id,
    )


def lookup_key(row: Showing) -> tuple[Any, ...]:
    """Rows that ask TMDB the same question share one lookup: one film listed per showing
    (cinematimes, GFT) is still one search. The title's own words count."""
    read = identity.read_title(row.title, row.start.date())
    facts = facts_of(row)
    return (
        identity.normal(read.query),
        read.anniversary_year,
        bool(read.rerun_label),
        facts.release,
        facts.director,
        facts.runtime,
        facts.tmdb_id,
        facts.imdb_id,
    )


def _date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    return date.fromisoformat(value[:10])


def selected_rows(snapshots: dict[str, Snapshot]) -> dict[FilmKey, Showing]:
    rows: dict[FilmKey, Showing] = {}
    for slug, snapshot in snapshots.items():
        if snapshot.failed:
            continue
        for row in snapshot.rows:
            key = (BY_SLUG[slug].source, row.film_key)
            if key in rows and fingerprint(rows[key]) != fingerprint(row):
                raise SourceError("Conflicting identity facts across source snapshots")
            rows[key] = row
    return rows


def metadata_room(fetch: Budget) -> int:
    """TMDB requests this run may still make: the cap, or what the programme left less four."""
    return max(
        0,
        min(METADATA_CAP, 120 - (fetch.requests - fetch.metadata_requests) - 4)
        - fetch.metadata_requests,
    )


async def _details(fetch: Budget, token: str, movie_id: int, votes: int) -> Candidate:
    base = "https://api.themoviedb.org/3/"
    # Validate an untrusted id before it goes into an authenticated URL.
    movie_id = MappingPick(source="tmdb", film_key="id", tmdb_id=movie_id).tmdb_id
    detail = json.loads(
        await fetch.metadata(
            base + f"movie/{movie_id}?language=en-GB&append_to_response=credits,release_dates",
            token,
        )
    )
    if detail["id"] != movie_id:
        raise SourceError("Metadata response identity differs from requested ID")
    events = [
        ReleaseEvent(date=day, type=e["type"], note=e.get("note", "")[:200])
        for country in detail["release_dates"]["results"]
        if country["iso_3166_1"] == "GB"
        for e in country["release_dates"]
        if e["type"] in (2, 3) and (day := _date(e["release_date"])) is not None
    ]
    poster = detail.get("poster_path")
    return Candidate(
        tmdb_id=movie_id,
        title=detail["title"],
        original_title=detail["original_title"],
        directors=[p["name"] for p in detail["credits"]["crew"] if p["job"] == "Director"][:10],
        runtime=detail.get("runtime") or None,
        imdb_id=detail.get("imdb_id") or None,
        primary_release_date=_date(detail.get("release_date")),
        gb_theatrical=events[:50],
        poster_path=poster
        if isinstance(poster, str) and re.fullmatch(r"/[\w.-]{1,190}", poster)
        else None,
        vote_count=max(0, int(detail.get("vote_count") or votes or 0)),
    )


async def _look_up(fetch: Budget, token: str, row: Showing) -> tuple[list[Candidate], list[int]]:
    """One search, then each exact-title candidate's details: two requests for most films."""
    if row.tmdb_id is not None:
        return [await _details(fetch, token, row.tmdb_id, 0)], []
    query = identity.read_title(row.title, row.start.date()).query
    url = "https://api.themoviedb.org/3/search/movie?" + urlencode(
        {"query": query, "language": "en-GB", "include_adult": "false", "page": 1}
    )
    results = json.loads(await fetch.metadata(url, token))["results"]
    if not isinstance(results, list) or len(results) > 20:
        raise SourceError("Unexpected metadata search shape")
    exact = [
        m
        for m in results
        if identity.same_title(query, m["title"]) or identity.same_title(query, m["original_title"])
    ][:DETAILED]
    candidates = []
    for found in exact:
        if metadata_room(fetch) <= 0:
            raise SourceError("Metadata budget spent within one film; it is looked up next run")
        candidates.append(
            await _details(fetch, token, int(found["id"]), int(found.get("vote_count") or 0))
        )
    return candidates, [m["id"] for m in results]


async def enrich(
    snapshots: dict[str, Snapshot],
    fetch: Budget,
    token: str,
    cache: Mapping[FilmKey, Metadata],
) -> tuple[list[Metadata], dict[str, Any]]:
    rows = selected_rows(snapshots)
    records: list[Metadata] = []
    report: dict[str, Any] = {"requests": 0, "cached": 0, "pending": 0, "errors": [], "lookups": 0}
    groups: dict[tuple[Any, ...], list[tuple[FilmKey, Showing]]] = {}
    for key, row in rows.items():
        groups.setdefault(lookup_key(row), []).append((key, row))
    # A short budget goes first where the source says most (AB6's order): a reissue label with
    # source facts, then facts, then the films with the most showings. Events never ask TMDB,
    # and a film a fresh cached record answers costs nothing.
    ordered = sorted(
        groups.values(),
        key=lambda members: (
            not (members[0][1].evidence.get("returningLabel") and members[0][1].identity_facts),
            not members[0][1].identity_facts,
            -len(members),
        ),
    )
    for members in ordered:
        (source, film_key), row = members[0]
        if identity.read_title(row.title, row.start.date()).event:
            continue
        fresh = [cache.get(k) for k, r in members]
        reusable = next(
            (
                m
                for m, (k, r) in zip(fresh, members, strict=True)
                if m and m.rule == "ac3" and m.fingerprint == fingerprint(r) and m.fresh()
            ),
            None,
        )
        if reusable is None:
            if not token or metadata_room(fetch) < 2 or "api.themoviedb.org" in fetch.refused:
                report["pending"] += len(members)
                continue
            try:
                candidates, searched = await _look_up(fetch, token, row)
                report["lookups"] += 1
            except (
                SourceError,
                ValueError,
                KeyError,
                TypeError,
                httpx.HTTPError,
                TimeoutError,
            ) as exc:
                report["pending"] += len(members)
                # No URLs, auth or provider bodies in diagnostics. A failure is not negative
                # identity evidence, so it never earns the seven-day negative cache.
                if len(report["errors"]) < 10:
                    report["errors"].append(type(exc).__name__)
                if isinstance(exc, Refused):
                    report["refused"] = True
                continue
            reusable = Metadata(
                source=source,
                film_key=film_key,
                fingerprint=fingerprint(row),
                fetched_utc=utcnow(),
                state="candidate" if candidates else "missing",
                candidates=candidates,
                search_candidates=searched[:20],
                rule="ac3",
            )
        else:
            report["cached"] += len(members)
        for (member_source, member_key), member in members:
            records.append(
                reusable.model_copy(
                    update={
                        "source": member_source,
                        "film_key": member_key,
                        "fingerprint": fingerprint(member),
                    }
                )
            )
    report["requests"] = fetch.metadata_requests
    report["successfulRequests"] = fetch.metadata_successes
    report["status"] = "noToken" if not token else "partial" if report["pending"] else "complete"
    report["records"] = len(records)
    return records, report


def validate_picks(
    snapshots: dict[str, Snapshot], records: list[Metadata], picks: list[MappingPick]
) -> dict[FilmKey, int]:
    """Owner-reviewed mappings from the refresh CLI: each must name one of the film's own
    current candidates and agree with any id the source gives. Craig's pick is the
    corroboration (#335); it never invents a candidate the lookup did not find."""
    rows = selected_rows(snapshots)
    lookup = {(m.source, m.film_key): m for m in records}
    accepted: dict[FilmKey, int] = {}
    for pick in picks:
        key = (pick.source, pick.film_key)
        row, record = rows.get(key), lookup.get(key)
        if key in accepted or row is None or record is None:
            raise SourceError("Mapping pick missing, duplicate or not an observed candidate")
        chosen = next((c for c in record.identities() if c.tmdb_id == pick.tmdb_id), None)
        if (
            chosen is None
            or not record.fresh()
            or record.fingerprint != fingerprint(row)
            or row.evidence.get("conflict")
            or row.evidence.get("combinedProgramme")
            or (row.tmdb_id and row.tmdb_id != pick.tmdb_id)
            or (row.imdb_id and row.imdb_id != chosen.imdb_id)
        ):
            raise SourceError("Mapping is not one of the film's current candidates, or conflicts")
        accepted[key] = pick.tmdb_id
    return accepted
