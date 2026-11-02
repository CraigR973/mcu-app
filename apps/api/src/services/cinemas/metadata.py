"""Bounded TMDB candidates, never a title-only identity or current-run classifier."""

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from datetime import date, timedelta
from typing import Annotated, Any, Literal
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, ConfigDict, Field, NaiveDatetime, model_validator

from src.clock import utcnow
from src.services.cinemas.domain import Showing, Snapshot, SourceError
from src.services.cinemas.fetch import Budget, Refused
from src.services.cinemas.venues import BY_SLUG

Text = Annotated[str, Field(min_length=1, max_length=500)]
MovieId = Annotated[int, Field(strict=True, gt=0, lt=2**31)]
FilmKey = tuple[str, str]


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


class Metadata(EvidenceModel):
    source: Text
    film_key: str = Field(min_length=1, max_length=300)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    fetched_utc: NaiveDatetime
    state: Literal["candidate", "ambiguous", "missing"]
    candidate: Candidate | None = None
    search_candidates: list[MovieId] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def consistent(self) -> "Metadata":
        if (self.state == "candidate") != (self.candidate is not None):
            raise ValueError("Candidate state and metadata must agree")
        return self

    def fresh(self) -> bool:
        age = utcnow() - self.fetched_utc
        return timedelta(0) <= age < timedelta(days=30 if self.state == "candidate" else 7)


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


def normal(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    return "".join(c for c in value if c.isalnum())


def query_title(title: str) -> str:
    # Only evidenced presentation decorations; do not strip arbitrary subtitles.
    title = re.sub(r"^\s*\(IMAX\)\s*", "", title, flags=re.I)
    return re.sub(
        r"\s*\(?\d+(?:st|nd|rd|th) Anniversary\)?(?:\s+4K Restoration)?\s*$",
        "",
        title,
        flags=re.I,
    ).strip()


def corroboration(row: Showing, candidate: Candidate) -> list[str]:
    if normal(query_title(row.title)) not in {
        normal(candidate.title),
        normal(candidate.original_title),
    }:
        return []
    proof = []
    director = row.identity_facts.get("director")
    if isinstance(director, str):
        names = {normal(n.strip()) for n in re.split(r",|\s+and\s+|\s*&\s*", director)}
        if names & {normal(n) for n in candidate.directors}:
            proof.append("director")
    original = row.identity_facts.get("originalTitle")
    if (
        isinstance(original, str)
        and normal(original) == normal(candidate.original_title)
        and normal(original) != normal(query_title(row.title))
    ):
        proof.append("distinct original title")
    # Runtime, poster or the repeated same title alone cannot establish identity.
    return proof


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


def validate_picks(
    snapshots: dict[str, Snapshot], records: list[Metadata], picks: list[MappingPick]
) -> dict[FilmKey, Metadata]:
    rows = selected_rows(snapshots)
    lookup = {(m.source, m.film_key): m for m in records}
    accepted = {}
    for pick in picks:
        key = (pick.source, pick.film_key)
        row, record = rows.get(key), lookup.get(key)
        if key in accepted or row is None or record is None or record.candidate is None:
            raise SourceError("Mapping pick missing, duplicate or not an observed candidate")
        if (
            not record.fresh()
            or record.fingerprint != fingerprint(row)
            or pick.tmdb_id != record.candidate.tmdb_id
            or not corroboration(row, record.candidate)
            or row.evidence.get("conflict")
            or row.evidence.get("combinedProgramme")
            or (row.tmdb_id and row.tmdb_id != pick.tmdb_id)
            or (row.imdb_id and row.imdb_id != record.candidate.imdb_id)
        ):
            raise SourceError("Mapping lacks current independent corroboration or conflicts")
        accepted[key] = record
    return accepted


async def enrich(
    snapshots: dict[str, Snapshot],
    fetch: Budget,
    token: str,
    cache: Mapping[FilmKey, Metadata],
) -> tuple[list[Metadata], dict[str, Any]]:
    rows = selected_rows(snapshots)
    records = []
    report: dict[str, Any] = {"requests": 0, "cached": 0, "pending": 0, "errors": []}
    for (source, key), row in rows.items():
        prior = cache.get((source, key))
        if prior and prior.fingerprint == fingerprint(row) and prior.fresh():
            records.append(prior)
            report["cached"] += 1
            continue
        if not token or fetch.metadata_requests >= 12 or "api.themoviedb.org" in fetch.refused:
            report["pending"] += 1
            continue
        try:
            base = "https://api.themoviedb.org/3/"
            candidate_id = row.tmdb_id
            ids: list[int] = []
            if candidate_id is None:
                query = query_title(row.title)
                url = (
                    base
                    + "search/movie?"
                    + urlencode(
                        {"query": query, "language": "en-GB", "include_adult": "false", "page": 1}
                    )
                )
                result = json.loads(await fetch.metadata(url, token))
                results = result["results"]
                if not isinstance(results, list) or len(results) > 20:
                    raise SourceError("Unexpected metadata search shape")
                ids = [m["id"] for m in results]
                exact = [
                    m
                    for m in results
                    if normal(query) in {normal(m["title"]), normal(m["original_title"])}
                ]
                if len(exact) == 1:
                    candidate_id = exact[0]["id"]
            candidate = None
            if candidate_id is not None:
                # Validate untrusted IDs before placing them in an authenticated URL.
                candidate_id = MappingPick(
                    source=source, film_key=key, tmdb_id=candidate_id
                ).tmdb_id
                detail = json.loads(
                    await fetch.metadata(
                        base + f"movie/{candidate_id}?language=en-GB&append_to_response=credits",
                        token,
                    )
                )
                releases = json.loads(
                    await fetch.metadata(base + f"movie/{candidate_id}/release_dates", token)
                )
                if detail["id"] != candidate_id or releases["id"] != candidate_id:
                    raise SourceError("Metadata response identity differs from requested ID")
                events = [
                    ReleaseEvent(
                        date=_date(e["release_date"]), type=e["type"], note=e.get("note", "")[:200]
                    )
                    for country in releases["results"]
                    if country["iso_3166_1"] == "GB"
                    for e in country["release_dates"]
                    if e["type"] in (2, 3)
                ]
                candidate = Candidate(
                    tmdb_id=candidate_id,
                    title=detail["title"],
                    original_title=detail["original_title"],
                    directors=[
                        p["name"] for p in detail["credits"]["crew"] if p["job"] == "Director"
                    ],
                    runtime=detail.get("runtime") or None,
                    imdb_id=detail.get("imdb_id") or None,
                    primary_release_date=_date(detail.get("release_date")),
                    gb_theatrical=events,
                )
            records.append(
                Metadata(
                    source=source,
                    film_key=key,
                    fingerprint=fingerprint(row),
                    fetched_utc=utcnow(),
                    state="candidate" if candidate else "ambiguous" if ids else "missing",
                    candidate=candidate,
                    search_candidates=ids,
                )
            )
        except (SourceError, ValueError, KeyError, TypeError, httpx.HTTPError, TimeoutError) as exc:
            report["pending"] += 1
            # No URLs, auth or provider bodies in diagnostics. HTTP failures aren't
            # negative identity evidence and must not get a seven-day negative cache.
            if len(report["errors"]) < 10:
                report["errors"].append(type(exc).__name__)
            if isinstance(exc, Refused):
                report["refused"] = True
    report["requests"] = fetch.metadata_requests
    report["successfulRequests"] = fetch.metadata_successes
    report["status"] = "noToken" if not token else "partial" if report["pending"] else "complete"
    report["records"] = len(records)
    return records, report


def category_evidence(row: Showing, record: Metadata | None) -> dict[str, Any]:
    evidence = dict(row.evidence)
    if (
        record
        and record.fresh()
        and record.fingerprint == fingerprint(row)
        and record.candidate
        and evidence.get("returningLabel") is True
        and any(
            e.date < (row.source_release or row.start.date())
            for e in record.candidate.gb_theatrical
        )
    ):
        evidence.update(run="returning", reissue=True)
    return evidence
