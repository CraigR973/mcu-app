"""Finding a film's review with Brave — Batch V9, `DECISIONS.md` #202, #228, #241.

**Finding sends neither site a request.** One Brave search per site proposes pages, and a
hit is kept only if it is that site's review of that film (its title names the film), and
for Blu-ray.com of that format (its address does). Measured on Brave's real answers for Dog
Soldiers, 3 Oct (`tests/fixtures/brave_*_dog_soldiers_4k.json`):

- **AVForums** answers with its review pages, titled "Dog Soldiers 4K Blu-ray Review |
  AVForums" at `/reviews/<slug>.<id>/`, beside forum threads about them, which are not
  reviews. Brave's line is a quote from the review.
- **Blu-ray.com** answers with release pages, "Dog Soldiers 4K Blu-ray (4K Ultra HD)
  (United Kingdom)", and nothing in a hit says which carries the review: that is read later,
  from the page (`batch.py`, #241). Brave's line is the site's boilerplate after the release
  date, so only the date is kept.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from src.services.reviews.bluray_com import format_of
from src.services.specs.bluray_com import canonical_release_url, is_release_url
from src.services.specs.search import SearchHit

#: Brave's line for every Blu-ray.com page ends with this, whatever the film.
_BLURAY_COM_BOILERPLATE = re.compile(
    r"\s*Blu-ray reviews, news, specs, ratings, screenshots\.\s*Cheap Blu-ray movies and "
    r"deals\.?\s*$",
    re.IGNORECASE,
)
_AVFORUMS_REVIEW_PATH = re.compile(r"^/reviews/([^/]+\.\d+)/?$")
_AVFORUMS_SUFFIX = re.compile(r"\s+Review\s*\|\s*AVForums\s*$", re.IGNORECASE)
#: The only words a review's title may carry after the film's: its kind. "Dog Soldiers 2 4K
#: Blu-ray Review" carries a "2", so it is not Dog Soldiers' review.
_KIND_WORDS = frozenset(
    {"4k", "uhd", "ultra", "hd", "blu", "ray", "bluray", "dvd", "movie", "film"}
)
_NOT_A_WORD = re.compile(r"[^a-z0-9]+")

#: The order a review is preferred in when the want's own format has none, best first.
_PREFERENCE = ("4k_uhd", "blu_ray", None, "dvd")


def normalise(title: str) -> str:
    """A title as words: lower case, apostrophes dropped, ``&`` read as "and"."""
    text = title.lower().replace("&", " and ").replace("'", "").replace("’", "")
    return " ".join(_NOT_A_WORD.sub(" ", text).split())


@dataclass(frozen=True)
class ReviewHit:
    """A page Brave proposed that is the site's review of the film."""

    url: str
    format_code: str | None
    title: str
    description: str


def bluray_com_query(title: str, year: int | None, format_code: str | None) -> str:
    words = "4K Blu-ray" if format_code == "4k_uhd" else "Blu-ray"
    return " ".join(
        part for part in ("site:blu-ray.com", title, str(year or ""), words, "review") if part
    )


def avforums_query(title: str, year: int | None, format_code: str | None) -> str:
    words = {"4k_uhd": "4K", "blu_ray": "Blu-ray"}.get(format_code or "", "")
    return " ".join(
        part for part in ("site:avforums.com", title, str(year or ""), words, "review") if part
    )


def _bluray_com_film(title: str) -> str | None:
    """The film a Blu-ray.com page title names: the words before " 4K Blu-ray" or " Blu-ray"."""
    head, found, _ = title.partition(" Blu-ray")
    if not found:
        return None
    return head.removesuffix(" 4K").strip() or None


def bluray_com_hits(hits: list[SearchHit], title: str) -> list[ReviewHit]:
    """Blu-ray.com release pages for this film, in Brave's order, each with its format."""
    wanted = normalise(title)
    kept: list[ReviewHit] = []
    seen: set[str] = set()
    for hit in hits:
        if not is_release_url(hit.url):
            continue
        format_code = format_of(hit.url)
        film = _bluray_com_film(hit.title)
        if format_code is None or film is None or normalise(film) != wanted:
            continue
        url = canonical_release_url(hit.url)
        if url in seen:
            continue
        seen.add(url)
        description = _BLURAY_COM_BOILERPLATE.sub("", hit.description).strip()
        kept.append(ReviewHit(url, format_code, hit.title, description))
    return kept


def _avforums_kind(words: list[str]) -> str | None | bool:
    """A review's format from the words after the film's: False when they are not a disc's
    or the film's kind, so the title names some other film."""
    if not set(words) <= _KIND_WORDS:
        return False
    if "4k" in words or "uhd" in words:
        return "4k_uhd"
    if "blu" in words or "bluray" in words:
        return "blu_ray"
    if "dvd" in words:
        return "dvd"
    return None


def avforums_hits(hits: list[SearchHit], title: str) -> list[ReviewHit]:
    """AVForums review pages for this film, in Brave's order, each with its format."""
    wanted = normalise(title).split()
    kept: list[ReviewHit] = []
    seen: set[str] = set()
    for hit in hits:
        parts = urlsplit(hit.url)
        host = (parts.hostname or "").lower().removeprefix("www.")
        path = _AVFORUMS_REVIEW_PATH.match(parts.path)
        suffix = _AVFORUMS_SUFFIX.search(hit.title)
        if (
            host != "avforums.com"
            or parts.scheme not in ("http", "https")
            or not path
            or not suffix
        ):
            continue
        words = normalise(hit.title[: suffix.start()]).split()
        if not wanted or words[: len(wanted)] != wanted:
            continue
        kind = _avforums_kind(words[len(wanted) :])
        if kind is False:
            continue
        url = f"https://www.avforums.com/reviews/{path.group(1)}/"
        if url in seen:
            continue
        seen.add(url)
        format_code = kind if isinstance(kind, str) else None
        kept.append(ReviewHit(url, format_code, hit.title, hit.description))
    return kept


def choose(hits: list[ReviewHit], format_code: str | None) -> ReviewHit | None:
    """The review for a want: its own format's first, then 4K, Blu-ray, the film, DVD."""
    order = ([format_code] if format_code else []) + [f for f in _PREFERENCE if f != format_code]
    for wanted in order:
        for hit in hits:
            if hit.format_code == wanted:
                return hit
    return None


def choose_bluray_com(hits: list[ReviewHit], format_code: str | None) -> ReviewHit | None:
    """Blu-ray.com's must be of the want's format; with none named, 4K first, then Blu-ray."""
    order = [format_code] if format_code else ["4k_uhd", "blu_ray"]
    for wanted in order:
        for hit in hits:
            if hit.format_code == wanted:
                return hit
    return None
