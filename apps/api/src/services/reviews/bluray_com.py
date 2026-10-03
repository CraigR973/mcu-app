"""Reading a review's scores from a Blu-ray.com release page — Batch V9, #228 within #110.

**#228 widened #110 by exactly one thing:** Blu-ray.com's own review scores for a release,
read from an exact page address. So this module reads one block, ``div#review_rating``
("Blu-ray review"), and the links in ``div#movie_review_other`` to the editions that carry
the review. Nothing else on the page is read here: not the review's words, not the disc's
"Blu-ray rating", and never the members' "Blu-ray user rating" beside it, which is member
content #110 still forbids. The specs parser (`specs/bluray_com.py`) keeps refusing all of
it, so the two never overlap.

**Measured on two real pages, 3 Oct** (`tests/fixtures/bluray_com_review_page_4k.html`,
`…_release_page_no_review.html`):

1. **A release without a review still prints the block**, every score ``0.0`` and every
   image "n/a". A review is an Overall above nought, and a nought is no score.
2. **The review lives on one edition's page per format**, usually the US release; the
   others say "No review exists for this particular release" and link the editions that
   have one, each titled with its format and year: "Dog Soldiers 4K (2002)".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag

from src.services.specs.bluray_com import canonical_release_url, is_release_url

#: Blu-ray.com scores out of five, in halves.
OUT_OF = 5

_SCORE = re.compile(r"^\d(?:\.\d)?$")
_EDITION_YEAR = re.compile(r"\((\d{4})\)\s*$")


@dataclass(frozen=True)
class ReviewScores:
    """A review's scores under the site's own headings, in its order."""

    scores: tuple[tuple[str, Decimal], ...]
    overall: Decimal


@dataclass(frozen=True)
class Edition:
    """An edition the page names as having the review."""

    url: str
    title: str
    format_code: str | None
    year: int | None


def _score(text: str) -> Decimal | None:
    value = text.strip()
    if not _SCORE.match(value):
        return None
    try:
        score = Decimal(value)
    except InvalidOperation:  # pragma: no cover - the pattern rules it out
        return None
    return score if Decimal("0") < score <= OUT_OF else None


def review_scores(html: str) -> ReviewScores | None:
    """The review's scores, or ``None`` when the page carries no review.

    Reads the rows of ``div#review_rating`` only: a heading cell, an image, and the number
    in the last cell. A row scored ``0.0`` is left out (the site's "n/a"), and without an
    Overall above nought there is no review.
    """
    soup = BeautifulSoup(html, "html.parser")
    block = soup.find("div", id="review_rating")
    if not isinstance(block, Tag):
        return None
    scores: list[tuple[str, Decimal]] = []
    overall: Decimal | None = None
    for row in block.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        heading = cells[0].get_text(" ", strip=True)
        score = _score(cells[-1].get_text(" ", strip=True))
        if not heading or score is None:
            continue
        scores.append((heading, score))
        if heading.lower() == "overall":
            overall = score
    if overall is None:
        return None
    return ReviewScores(scores=tuple(scores), overall=overall)


def format_of(url: str) -> str | None:
    """The format a release page is for, from its address: `…-4K-Blu-ray/<id>/` or
    `…-Blu-ray/<id>/`. DVDs live under `/dvd/`, which #110's predicate does not allow."""
    slug = urlsplit(url).path.rstrip("/").split("/")[-2] if is_release_url(url) else ""
    lowered = slug.lower()
    if lowered.endswith("-4k-blu-ray"):
        return "4k_uhd"
    if lowered.endswith("-blu-ray"):
        return "blu_ray"
    return None


def reviewed_editions(html: str) -> list[Edition]:
    """The editions a release page names as having the review, in its order.

    Only links inside ``div#movie_review_other`` that pass #110's release-page predicate:
    an exact page address, never a search route.
    """
    soup = BeautifulSoup(html, "html.parser")
    block = soup.find("div", id="movie_review_other")
    if not isinstance(block, Tag):
        return []
    editions: list[Edition] = []
    seen: set[str] = set()
    for link in block.find_all("a", href=True):
        href = str(link.get("href") or "")
        if not is_release_url(href):
            continue
        url = canonical_release_url(href)
        if url in seen:
            continue
        seen.add(url)
        title = str(link.get("title") or "").strip()
        year = _EDITION_YEAR.search(title)
        editions.append(
            Edition(
                url=url,
                title=title,
                format_code=format_of(url),
                year=int(year.group(1)) if year else None,
            )
        )
    return editions
