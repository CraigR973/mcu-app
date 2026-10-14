"""Getting a disc onto eBay — Batch 28, Phase 4.3.

**Phase 4.3's preferred option does not exist, and this module is the fallback promoted to
primary.** The phase reads:

> Option A (preferred): eBay Sell API draft listing creation · Option B (fallback):
> pre-filled eBay listing URL · Admin publishes from eBay.

There is no eBay API that creates a Seller Hub *draft*. The Inventory API's offer is
invisible until it is **published**, and publishing produces a live listing with a buyer on
the other end — not a draft for review, which is the entire shape Option A describes.
Option A would additionally need a refreshing eBay **user** token for a real selling
account, opted into business policies: the class of stored third-party credential this
project deliberately sequences late (Batch 33) and has never yet held. `DECISIONS.md` #142
records the inversion.

**Option B was confirmed alive in a browser on 2026-09-12, and the parameter name is not
the obvious one.** `docs/phase-batches.md` flagged that nobody had checked, and that if
prefill were gone 4.3 would have no remaining path at all. It is not gone:

| Tried | Result |
|---|---|
| ``?keyword=`` | form renders, box **empty** |
| ``?q=`` | form renders, box **empty** |
| ``?sugKw=`` | form renders, box **empty** |
| ``?title=`` | form renders with the box **pre-filled** |

So :data:`PRELIST_URL` plus ``title`` is the whole mechanism, and the three names that look
right are the three that silently do nothing — which is why this is a module with a test
rather than a string built at a call site.

**What prefill can and cannot carry.** ``sl/prelist/suggest`` is step one of three ("share
item details" → "find a match" → "edit and list") and has exactly one field. Condition,
price and photos are set by the seller in the later steps, so the title is where all the
useful information has to go — hence :func:`suggested_title`, which packs the film, year,
format and condition into eBay's 80-character limit.
"""

from __future__ import annotations

from decimal import Decimal
from urllib.parse import urlencode

#: eBay UK's current "start your listing" entry point.
PRELIST_URL = "https://www.ebay.co.uk/sl/prelist/suggest"

#: eBay's listing-title limit. Longer titles are truncated by eBay itself, silently, so
#: :func:`suggested_title` drops whole components instead of cutting a word in half.
MAX_TITLE_LENGTH = 80

#: How each ``collection_item.FORMAT_RANK`` code is written on an eBay listing. The words
#: buyers actually search for, which is not always the code's own spelling.
FORMAT_WORDS: dict[str, str] = {
    "4k_uhd": "4K UHD Blu-ray",
    "blu_ray": "Blu-ray",
    "dvd": "DVD",
    "download": "Digital",
}

#: How each ``collection_item.CONDITIONS`` value reads in a listing title. ``damaged`` is
#: absent on purpose: a damaged disc needs a description, not a one-word euphemism.
CONDITION_WORDS: dict[str, str] = {
    "new": "New & Sealed",
    "like_new": "Like New",
    "good": "Very Good",
    "acceptable": "Acceptable",
}


def suggested_title(
    film_title: str,
    *,
    year: int | None = None,
    format_code: str | None = None,
    condition: str | None = None,
) -> str:
    """A listing title within eBay's 80 characters, most important part first.

    Components are dropped from the **right** when the whole will not fit, so a long film
    title keeps its year and format rather than losing the film's name to a truncation.
    """
    parts = [film_title.strip()]
    if year:
        parts.append(f"({year})")
    if format_code and format_code in FORMAT_WORDS:
        parts.append(FORMAT_WORDS[format_code])
    if condition and condition in CONDITION_WORDS:
        parts.append(CONDITION_WORDS[condition])

    while len(parts) > 1 and len(" ".join(parts)) > MAX_TITLE_LENGTH:
        parts.pop()
    return " ".join(parts)[:MAX_TITLE_LENGTH]


def prelist_url(
    film_title: str,
    *,
    year: int | None = None,
    format_code: str | None = None,
    condition: str | None = None,
) -> str:
    """The pre-filled eBay listing URL for a disc — Phase 4.3's remaining path.

    Nothing is created by calling this. It is a link the admin opens, signed in as
    themselves, which is what "Admin publishes from eBay" means once Option A is off the
    table: the app never holds a selling credential and never creates a live listing.
    """
    title = suggested_title(film_title, year=year, format_code=format_code, condition=condition)
    return f"{PRELIST_URL}?{urlencode({'title': title})}"


def suggested_price(median: Decimal | None) -> Decimal | None:
    """What to ask, given the disc's value as a used copy (Batch X6; before it, the largest
    group's median of current asking prices).

    **The value is returned unchanged**, and that is a deliberate refusal to be clever.
    Shading it — 5% under the median to sell faster, say — would turn a measured number
    into an invented one, and `DECISIONS.md` #129 is a standing account of what happens to
    eBay prices that get invented. The admin adjusts it, which is what Phase 4.2's "admin
    adjusts or accepts" asks for.

    It exists as a function so there is one documented place for that decision to be
    revisited, rather than the median being passed straight through at three call sites.
    """
    return median
