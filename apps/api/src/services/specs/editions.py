"""Which edition a disc is, from its Blu-ray.com page — Batch U2, `DECISIONS.md` #220.

**Only where the page is certainly the copy.** A disc's settled page is its copy when Craig
chose it from the list or pasted it, or when it was the one UK edition of the film on that
format the search found. The matcher's other way of settling, the plain release among
several UK editions (#212), is a good bet for specs and no evidence of which box is on the
shelf, so it gives no edition. Nothing is guessed: an edition left blank is Craig's to type.

**The name is the page's title as the search saw it**, since that is what is stored. A page
that moved since (Batch U1) was renamed, so its old name is not used. Blu-ray.com puts
everything that is not the film's name in brackets: the country, what is in the box, a
studio's brand, an alternative title and the edition. Only the parts that name an edition
are kept, which drops "(MIB)", "(Twelve Angry Men)", "(Triple Play)" and "(PIXAR)".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.specs_backfill import SpecCandidate, SpecLookup
from src.services.specs.bluray_com import canonical_release_url, release_number
from src.services.specs.candidates import Disc, judge, parse_release_title
from src.services.specs.search import SearchHit

#: How the page came to be certainly the copy: Craig chose it from the list, Craig pasted
#: it, or the search found no other UK edition of the film on that format.
EditionKind = Literal["chosen", "pasted", "only_uk_edition"]

#: The column's length, and the Wanted list's ``preferred_edition``'s.
MAX_EDITION = 100

#: Words that name an edition, a cut, a special package or a publisher's line. A bracket
#: part without one is something else: an alternative title, a pack of formats, a brand.
_EDITION_WORDS = re.compile(
    r"\b(?:edition|cut|version|steelbook|metalpak|digipack|digibook|mediabook|exclusive"
    r"|re-?mastered|restored|anniversary|limited|collector['’]?s|special|deluxe|ultimate"
    r"|uncut|unrated|extended|theatrical|director['’]?s|collection|series|classics|academy"
    r"|masters of cinema|criterion|indicator|arrow|eureka|bfi|second sight|powerhouse)\b",
    re.IGNORECASE,
)

#: What the matcher calls a plain release: "standard" is no edition to show.
_PLAIN = frozenset({"standard edition", "standard"})

#: Blu-ray.com separates the parts of one bracket with " / " or " | ". Spaces are required,
#: so "F/X 2" stays one part.
_PARTS = re.compile(r"\s+[/|]\s+")


def edition_from_title(title: str) -> str | None:
    """The edition a Blu-ray.com page title names, or ``None`` for a plain release.

    "Kill Bill Vol. 1 Blu-ray (Zavvi Exclusive SteelBook) (United Kingdom)" gives "Zavvi
    Exclusive SteelBook"; "Ace in the Hole Blu-ray (The Big Carnival / Masters of Cinema)
    (United Kingdom)" gives "Masters of Cinema"; "Men in Black Blu-ray (MIB) (United
    Kingdom)" gives nothing. Several parts are joined with " · ", as the Disc specs page
    joins brackets. Longer than the column holds is ``None``, not cut short.
    """
    kept: list[str] = []
    for bracket in parse_release_title(title).editions:
        for part in _PARTS.split(bracket):
            words = part.strip()
            if words and words.lower() not in _PLAIN and _EDITION_WORDS.search(words):
                kept.append(words)
    label = " · ".join(dict.fromkeys(kept))
    if not label or len(label) > MAX_EDITION:
        return None
    return label


@dataclass(frozen=True)
class SettledEdition:
    """A disc whose settled page is certainly the copy, and the edition that page names.

    ``edition`` is ``None`` for a plain release, and for a page whose name is not known: one
    Craig pasted that the search never offered, or one that has moved since.
    """

    kind: EditionKind
    edition: str | None


async def _search_candidates(db: AsyncSession, lookup: SpecLookup) -> list[SpecCandidate]:
    return list(
        (
            await db.scalars(
                select(SpecCandidate)
                .where(SpecCandidate.lookup_id == lookup.id, SpecCandidate.origin == "search")
                .order_by(SpecCandidate.rank)
            )
        ).all()
    )


def _named_by_search(lookup: SpecLookup, candidates: list[SpecCandidate]) -> SpecCandidate | None:
    """The search result for the settled page, when the page still has the name it had.

    Matched by address. A page renamed on the site since (Batch U1) keeps its release number
    but not its address, and its old title may name an edition it no longer has.
    """
    if lookup.accepted_url is None:
        return None
    settled = canonical_release_url(lookup.accepted_url)
    return next((c for c in candidates if canonical_release_url(c.url) == settled), None)


async def page_edition(db: AsyncSession, lookup: SpecLookup) -> str | None:
    """The edition a disc's settled page names, whether or not the page is its copy.

    What Blu-ray.com says, so it is also what "forget everything from Blu-ray.com" removes.
    """
    named = _named_by_search(lookup, await _search_candidates(db, lookup))
    return edition_from_title(named.title) if named is not None else None


async def settled_edition(
    db: AsyncSession, lookup: SpecLookup, disc: Disc
) -> SettledEdition | None:
    """Whether a disc's settled page is certainly the copy, and which edition it names.

    ``None`` when it is not certainly the copy. For a page the matcher chose, that takes the
    search finding exactly one UK edition of the film on that format, by the verdicts stored
    at the time and by today's matcher alike, and no result whose title was cut short
    before its country: that one could be another UK edition.
    """
    if lookup.status != "done" or lookup.accepted_url is None:
        return None
    candidates = await _search_candidates(db, lookup)
    named = _named_by_search(lookup, candidates)
    edition = edition_from_title(named.title) if named is not None else None
    if lookup.how == "confirmed":
        return SettledEdition("chosen", edition)
    if lookup.how == "pasted":
        return SettledEdition("pasted", edition)

    number = release_number(lookup.accepted_url)
    stored = [c for c in candidates if c.matches]
    judged = judge([SearchHit(c.url, c.title, c.snippet or "") for c in candidates], disc)
    today = [c for c in judged if c.matches]
    if len(stored) != 1 or len(today) != 1:
        return None
    if release_number(stored[0].url) != number or release_number(today[0].url) != number:
        return None
    if any(c.release.country is None for c in judged):
        return None
    return SettledEdition("only_uk_edition", edition)
