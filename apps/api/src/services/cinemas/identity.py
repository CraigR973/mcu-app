"""Which film a programme title is, and whether a showing is a first run or a rerun — AC3 (#335).

Pure functions over a programme row and TMDB's answers; nothing here makes a request or writes.

**Identity.** A source's own TMDB or IMDb id links directly. Otherwise the cleaned title must
equal a TMDB candidate's title or original title, and at least one independent fact must agree:
the source's year or release date, an anniversary label's year, the source's director or
runtime, or a UK cinema release that matches the programme (in cinemas now). Exactly one
candidate may pass; two, or a candidate with no agreeing fact, go to Craig's review list and stay
unlinked. Live events, double bills and programmes of shorts never link to a film.

**Run.** From the film's first UK cinema release (TMDB, GB, theatrical): a first run when it is
within 16 weeks before the showing, or after it (a preview); a rerun when it is 12 months or
more before, or when the cinema labels the showing a reissue, an anniversary or a restoration;
otherwise Unclassified. Each label keeps its reason in words.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

FIRST_RUN = timedelta(weeks=16)
RERUN = timedelta(days=365)
#: How far a UK release may sit from the showing and still say "in cinemas now".
IN_CINEMAS = timedelta(weeks=16)

Category = Literal["newRelease", "olderFilm", "unclassified"]


def normal(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold().replace("&", "and")
    return "".join(c for c in value if c.isalnum())


def same_title(a: str, b: str) -> bool:
    """Equal titles, ignoring case, punctuation and a leading article a listing may drop."""

    def bare(value: str) -> str:
        return normal(re.sub(r"^\s*(?:the|a|an)\s+", "", value, flags=re.I))

    return normal(a) == normal(b) or bare(a) == bare(b)


#: Live and staged events, television and programmes of shorts: never one film (#335).
_EVENT = re.compile(
    r"\bnational theatre live\b|^nt live\b|\brbo\b|\broyal ballet\b|\bopera\b|\blive viewing\b"
    r"|\blive in [a-z]|\bworld tour\b|\bthe [a-z]+ tour\b|\bthe musical\b|\bseason \d+\s*[-–]\s*ep"
    r"|\bcinema experience\b|\bshorts\b|\bsecret screen|\bquiz\b|\bconcert\b|\bweekend pass\b"
    r"|\bfestival pass\b|\bmarathon\b",
    re.I,
)
#: Two films for one ticket.
_DOUBLE = re.compile(r"\s\+\s(?!(?:discussion|q\s*&\s*a|intro|introduction|panel)\b)", re.I)

_PREFIXES = re.compile(
    r"^\s*(?:\(imax\)\s*|throwback:\s*|toddler club:\s*|members'? preview:\s*|kids'? club:\s*"
    r"|parent (?:and|&) baby:\s*|autism friendly:\s*|silver screen:\s*)+",
    re.I,
)
#: Decorations a listing adds to a film's own title: a run label, a format, a language, a
#: membership screening or an after-show discussion. Stripped for the search, read for the run.
_SUFFIXES = re.compile(
    r"(?:\s*[-–:]?\s*(?:"
    r"\(?(?:\d+(?:st|nd|rd|th) anniversary(?: \d+k restoration)?|\d+k restoration|4k"
    r"|restored|re-?release|reissue)\)?"
    r"|imax(?: 2d| 3d)?(?: \(\w+\))?"
    r"|\((?:hindi|tamil|telugu|japanese|korean|mandarin|english dubbed|subtitled|dubbed)\)"
    r"|unlimited screening"
    r"|\+ (?:discussion|q\s*&\s*a|intro|introduction|panel)"
    r")\s*)+$",
    re.I,
)
_ANNIVERSARY = re.compile(r"(\d+)(?:st|nd|rd|th) anniversary", re.I)
_RERUN_LABEL = re.compile(
    r"anniversary|restoration|reissue|re-?release|throwback|\b4k\b|restored", re.I
)
_PREVIEW = re.compile(r"preview|unlimited screening", re.I)


@dataclass(frozen=True)
class Title:
    """A programme title, cleaned for the search, with what its decoration says."""

    query: str
    event: str | None = None
    double_bill: bool = False
    rerun_label: str | None = None
    anniversary_year: int | None = None
    preview: bool = False


def read_title(title: str, shown: date) -> Title:
    raw = " ".join(title.split())
    if _EVENT.search(raw):
        return Title(query=raw, event="a live or staged event, not a film")
    if _DOUBLE.search(raw):
        return Title(query=raw, double_bill=True, event="a double bill, not one film")
    # Labels are read only from what the listing adds around the title, never from the
    # film's own name: "The Restoration" is a film, "(4K Restoration)" is a reissue.
    prefix = _PREFIXES.match(raw)
    rest = raw[prefix.end() :] if prefix else raw
    suffix = _SUFFIXES.search(rest)
    query = (rest[: suffix.start()] if suffix else rest).strip(" -–:")
    decoration = f"{prefix.group(0) if prefix else ''} {suffix.group(0) if suffix else ''}"
    label_match = _RERUN_LABEL.search(decoration)
    anniversary = _ANNIVERSARY.search(decoration)
    return Title(
        query=query or raw,
        rerun_label=label_match.group(0).lower() if label_match else None,
        anniversary_year=shown.year - int(anniversary.group(1)) if anniversary else None,
        preview=bool(_PREVIEW.search(decoration)),
    )


@dataclass(frozen=True)
class Candidate:
    tmdb_id: int
    title: str
    original_title: str
    release_date: date | None
    #: TMDB's GB theatrical dates (types 2 and 3), earliest first.
    uk_cinema: tuple[date, ...] = ()
    directors: tuple[str, ...] = ()
    runtime: int | None = None
    imdb_id: str | None = None
    poster_path: str | None = None

    @property
    def first_uk_release(self) -> date | None:
        return min(self.uk_cinema) if self.uk_cinema else None


@dataclass(frozen=True)
class Facts:
    """What the source itself says about the film, beyond its title."""

    year: int | None = None
    release: date | None = None
    director: str | None = None
    runtime: int | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None


@dataclass(frozen=True)
class Decision:
    #: "conflict" is the source's own flag that its listing contradicts itself (AB6).
    outcome: Literal["linked", "review", "unlinked", "event", "conflict"]
    candidate: Candidate | None = None
    corroboration: tuple[str, ...] = ()
    reason: str = ""
    others: tuple[int, ...] = field(default_factory=tuple)


#: A film with no UK cinema date on TMDB still matches the programme if it is this recent.
RECENT = timedelta(days=365)


def _agreeing(
    candidate: Candidate, title: Title, facts: Facts, shown: date, *, sole: bool = False
) -> list[str]:
    proof: list[str] = []
    years = {d.year for d in (candidate.release_date, candidate.first_uk_release) if d}
    source_year = facts.year or (facts.release.year if facts.release else None)
    if source_year is not None and source_year in years:
        proof.append(f"the cinema's year {source_year}")
    if (
        facts.release
        and candidate.uk_cinema
        and any(abs((d - facts.release).days) <= 7 for d in candidate.uk_cinema)
    ):
        proof.append(f"the cinema's release date {facts.release.isoformat()}")
    if (
        title.anniversary_year
        and candidate.release_date
        and abs(candidate.release_date.year - title.anniversary_year) <= 1
    ):
        proof.append(f"the anniversary's year {title.anniversary_year}")
    if facts.director:
        named = {normal(n) for n in re.split(r",|\s+and\s+|\s*&\s*", facts.director) if n.strip()}
        if named & {normal(d) for d in candidate.directors}:
            proof.append("the director")
    if facts.runtime and candidate.runtime and abs(facts.runtime - candidate.runtime) <= 5:
        proof.append("the running time")
    first = candidate.first_uk_release
    if first and abs(first - shown) <= IN_CINEMAS and not title.rerun_label:
        proof.append(f"a UK cinema release on {first.isoformat()}, matching the programme")
    released = candidate.release_date
    if (
        sole
        and not first
        and released
        and shown - RECENT <= released <= shown + IN_CINEMAS
        and not title.rerun_label
    ):
        proof.append(
            f"a release on {released.isoformat()} with no UK cinema date, matching the programme"
        )
    return proof


def identify(title: Title, facts: Facts, candidates: list[Candidate], shown: date) -> Decision:
    """One clear, corroborated winner, or the review list, or nothing to link."""
    if title.event:
        return Decision("event", reason=title.event)
    if facts.tmdb_id or facts.imdb_id:
        named = [
            c
            for c in candidates
            if (facts.tmdb_id and c.tmdb_id == facts.tmdb_id)
            or (facts.imdb_id and c.imdb_id == facts.imdb_id)
        ]
        if len(named) == 1:
            if not (
                same_title(title.query, named[0].title)
                or same_title(title.query, named[0].original_title)
            ):
                return Decision(
                    "review", named[0], reason="the cinema's own id names a film with another title"
                )
            return Decision("linked", named[0], ("the cinema's own id",))
        return Decision("review", reason="the cinema's own id was not found")
    exact = [
        c
        for c in candidates
        if same_title(title.query, c.title) or same_title(title.query, c.original_title)
    ]
    if not exact:
        return Decision(
            "unlinked",
            reason="no film with this title",
            others=tuple(c.tmdb_id for c in candidates),
        )
    passing = [(c, _agreeing(c, title, facts, shown, sole=len(exact) == 1)) for c in exact]
    passing = [(c, proof) for c, proof in passing if proof]
    if len(passing) == 1:
        candidate, proof = passing[0]
        return Decision(
            "linked",
            candidate,
            tuple(proof),
            others=tuple(c.tmdb_id for c in exact if c is not candidate),
        )
    if not passing:
        return Decision(
            "review",
            reason="the title matches, but nothing else agrees",
            others=tuple(c.tmdb_id for c in exact),
        )
    return Decision(
        "review", reason="more than one film matches", others=tuple(c.tmdb_id for c, _ in passing)
    )


_LABEL_WORDS = {
    "anniversary": "an anniversary showing",
    "restoration": "a restoration",
    "restored": "a restoration",
    "4k": "a 4K restoration",
    "reissue": "a reissue",
    "re-release": "a reissue",
    "rerelease": "a reissue",
    "throwback": "a throwback screening",
}


def classify(first_uk_release: date | None, shown: date, title: Title) -> tuple[Category, str]:
    """The run, with its reason in words, for a linked film's showing."""
    if title.rerun_label:
        label = (
            "an anniversary showing"
            if title.anniversary_year
            else _LABEL_WORDS.get(title.rerun_label, "a reissue")
        )
        year = f"UK release {first_uk_release.year} · " if first_uk_release else ""
        return "olderFilm", f"{year}the cinema calls it {label} · rerun"
    if first_uk_release is None:
        return "unclassified", "no UK cinema release on record"
    day = first_uk_release
    when = f"UK release {day.day} {day.strftime('%b')} {day.year}"
    if first_uk_release >= shown - FIRST_RUN:
        return "newRelease", f"{when} · {'preview' if first_uk_release > shown else 'first run'}"
    if first_uk_release <= shown - RERUN:
        return "olderFilm", f"UK release {first_uk_release.year} · rerun"
    return "unclassified", f"{when} · between first run and rerun"
