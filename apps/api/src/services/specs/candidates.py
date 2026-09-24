"""Which Blu-ray.com page is this disc? — Batch T7, `DECISIONS.md` #202.

The search engine proposes pages; this module decides whether one of them is **the** page.
A wrong edition is wrong data that looks right, so the bar is deliberately high:

1. **In bounds.** Only an exact release URL counts: #110's predicate,
   :func:`~src.services.specs.bluray_com.is_release_url`, applied to every candidate.
2. **Same film.** The page's film name, reduced as titles are for identification, equals
   the disc's.
3. **Same format.** "4K Blu-ray" for a 4K disc, plain "Blu-ray" for a Blu-ray; 3D and 4K/3D
   pages never stand in for either.
4. **UK edition.** Blu-ray.com ends a non-US release's title with its country, as in
   "Fight Club Blu-ray (MetalPak) (United Kingdom)". No country means the US.
5. **One of them.** A single page passing 1–4 is accepted. When several UK editions pass,
   the one plain release is accepted if there is exactly one, because no disc here records a
   special edition and a steelbook usually holds the same disc. Anything else waits for
   Craig.

**Never accepted automatically:** a film with no year, because the year is how a fetched
page is checked (a remake shares its title), and a disc in a box set, whose page is the
set's. The year itself is checked after the fetch, against the page's own year link.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from src.matching.engine import canonical_title
from src.services.specs.bluray_com import canonical_release_url, is_release_url
from src.services.specs.search import SearchHit

#: How a Blu-ray.com title names the product, longest first so "4K/3D Blu-ray" is never
#: read as "3D Blu-ray" or "Blu-ray".
FORMAT_LABELS = ("4K/3D Blu-ray", "4K Blu-ray", "3D Blu-ray", "Blu-ray", "DVD")

#: The label that matches each disc format. A 4K box with a Blu-ray inside is a 4K page.
LABEL_FOR_FORMAT = {"4k_uhd": "4K Blu-ray", "blu_ray": "Blu-ray"}

UK = "United Kingdom"

#: Countries Blu-ray.com appends to a release title. Anything else in the last bracket is
#: an edition, not a country.
COUNTRIES = frozenset(
    {
        "United Kingdom",
        "Germany",
        "France",
        "Italy",
        "Spain",
        "Netherlands",
        "Belgium",
        "Sweden",
        "Norway",
        "Denmark",
        "Finland",
        "Poland",
        "Czech Republic",
        "Austria",
        "Switzerland",
        "Ireland",
        "Portugal",
        "Hungary",
        "Greece",
        "Russia",
        "Turkey",
        "Canada",
        "Mexico",
        "Brazil",
        "Argentina",
        "Australia",
        "New Zealand",
        "Japan",
        "South Korea",
        "Korea",
        "China",
        "Hong Kong",
        "Taiwan",
        "Thailand",
        "India",
        "Singapore",
    }
)

#: Words that describe what is in the box rather than which edition it is:
#: "(4K Ultra HD + Blu-ray + Digital)". A bracket of only these is not an edition.
_FORMAT_WORDS = frozenset(
    {
        "4k",
        "ultra",
        "hd",
        "uhd",
        "blu",
        "ray",
        "dvd",
        "digital",
        "copy",
        "uv",
        "ultraviolet",
        "3d",
        "2d",
        "and",
        "code",
    }
)

_TRAILING_BRACKET = re.compile(r"\s*\(([^()]*)\)\s*$")
_SITE_SUFFIX = re.compile(r"\s*[-|–]\s*blu-ray\.com\s*$", re.IGNORECASE)
_WORD = re.compile(r"[a-z0-9]+")

#: Words in a disc's grouping that mean it came in a set: "The James Bond Collection Box
#: Set", "Universal Noir #2", "Hitchcock Classics Coll Vol 3".
_BOX_SET = re.compile(r"box\s*set|\bcollection\b|\bcoll\b|\bvol\b|#\s*\d", re.IGNORECASE)

Decision = Literal["accepted", "needs_you", "no_match"]


@dataclass(frozen=True)
class ReleaseTitle:
    """A Blu-ray.com page title, taken apart."""

    name: str
    format_label: str | None
    #: ``None`` when the title was cut short and the country cannot be known.
    country: str | None
    #: The edition brackets, such as "SteelBook" or "HMV Exclusive DigiPack". Empty for a
    #: plain release.
    editions: tuple[str, ...]


def _is_format_description(text: str) -> bool:
    words = _WORD.findall(text.lower())
    return bool(words) and all(word in _FORMAT_WORDS for word in words)


def parse_release_title(raw: str) -> ReleaseTitle:
    """ "Fight Club 4K Blu-ray (SteelBook) (United Kingdom)" → name, format, country, editions."""
    title = _SITE_SUFFIX.sub("", raw.strip())
    truncated = title.endswith(("...", "…"))
    title = title.rstrip(".… ")

    brackets: list[str] = []
    while True:
        match = _TRAILING_BRACKET.search(title)
        if not match:
            break
        brackets.insert(0, match.group(1).strip())
        title = title[: match.start()].rstrip()

    country: str | None = None
    if brackets and brackets[-1] in COUNTRIES:
        country = brackets.pop()
    elif not truncated:
        # Blu-ray.com's home market carries no country at all.
        country = "United States"

    format_label: str | None = None
    name = title
    lowered = title.lower()
    for label in FORMAT_LABELS:
        if lowered.endswith(" " + label.lower()) or lowered == label.lower():
            format_label = label
            name = title[: len(title) - len(label)].strip()
            break

    editions = tuple(bracket for bracket in brackets if not _is_format_description(bracket))
    return ReleaseTitle(name=name, format_label=format_label, country=country, editions=editions)


def same_film(page_name: str, film_title: str) -> bool:
    """Equal once both are reduced the way identification reduces titles."""
    page, _ = canonical_title(page_name)
    film, _ = canonical_title(film_title)
    return bool(page) and page == film


@dataclass(frozen=True)
class Disc:
    """What the matcher knows about one disc."""

    title: str
    year: int | None
    format_code: str
    grouping: str | None = None

    @property
    def in_box_set(self) -> bool:
        return bool(self.grouping and _BOX_SET.search(self.grouping))


@dataclass(frozen=True)
class Candidate:
    """One proposed page, judged."""

    url: str
    title: str
    snippet: str
    rank: int
    release: ReleaseTitle
    #: Same film, same format and a UK edition. Every candidate is in bounds already.
    matches: bool

    @property
    def plain(self) -> bool:
        return not self.release.editions


def judge(hits: list[SearchHit], disc: Disc) -> list[Candidate]:
    """Every hit that is a release page, with whether it matches the disc.

    A hit that fails #110's predicate is dropped here, before it can become anything: a
    search route, a forum thread or another site is never a candidate.
    """
    wanted_label = LABEL_FOR_FORMAT.get(disc.format_code)
    candidates: list[Candidate] = []
    seen: set[str] = set()
    for rank, hit in enumerate(hits):
        if not is_release_url(hit.url):
            continue
        url = canonical_release_url(hit.url)
        if url in seen:
            continue
        seen.add(url)
        release = parse_release_title(hit.title)
        matches = (
            release.format_label == wanted_label
            and release.country == UK
            and same_film(release.name, disc.title)
        )
        candidates.append(
            Candidate(
                url=url,
                title=hit.title,
                snippet=hit.description,
                rank=rank,
                release=release,
                matches=matches,
            )
        )
    return candidates


@dataclass(frozen=True)
class Verdict:
    decision: Decision
    url: str | None
    #: Why, in words Craig will read on the confirm screen.
    note: str


def decide(candidates: list[Candidate], disc: Disc) -> Verdict:
    """Accept one page, or say why a person has to choose."""
    if not candidates:
        return Verdict("no_match", None, "The search found no Blu-ray.com release page.")

    matching = [candidate for candidate in candidates if candidate.matches]
    if not matching:
        return Verdict(
            "needs_you",
            None,
            "No UK page for this film on this format was found. Pick one, paste a link, or skip.",
        )

    chosen: Candidate | None = None
    if len(matching) == 1:
        chosen = matching[0]
    else:
        plain = [candidate for candidate in matching if candidate.plain]
        if len(plain) == 1:
            chosen = plain[0]

    if chosen is None:
        return Verdict(
            "needs_you",
            None,
            f"{len(matching)} UK editions match. Pick the one on the shelf.",
        )
    if disc.year is None:
        return Verdict(
            "needs_you",
            None,
            "This film has no year, so the page cannot be checked. Confirm it's the right one.",
        )
    if disc.in_box_set:
        return Verdict(
            "needs_you",
            None,
            f"This disc is grouped under '{disc.grouping}', which may be a box set "
            "with a page of its own.",
        )
    return Verdict("accepted", chosen.url, "One UK page matched the film and format.")


def search_query(film_title: str, format_code: str) -> str:
    """What Brave is asked. The site filter and the country keep it to UK release pages."""
    label = LABEL_FOR_FORMAT.get(format_code, "Blu-ray")
    return f"site:blu-ray.com {film_title} {label} {UK}"
