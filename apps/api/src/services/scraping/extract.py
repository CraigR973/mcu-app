"""Turning a page into a price, and refusing to when it is not one — Batch 19.

**This module exists because of one sentence in the ledger's risk note:**

> "A layout change does not error — it selects the wrong node and persists a plausible
> wrong number, which then feeds price-drop alerts and aggregates. Build a per-scraper
> 'last known good shape' assertion, not just a success/fail counter."

A success/fail counter cannot see the failure being described. `.price` matching a
"you save £3.00" badge instead of the price returns a number, parses fine, inserts fine,
and is wrong. Nothing downstream can tell.

So extraction here has two halves, and the second is the point:

1. **Extract** — a CSS selector, a text node, a number.
2. **Assert the shape** — every check below is one way a wrong node has actually looked in
   practice. A result that fails any of them is discarded with a reason, and the reason is
   what a person reads when a scraper starts misbehaving.

The shape checks are deliberately about *this* result rather than about drift over time.
Drift needs history, which is Batch 20's `price_history_daily`; what can be known from a
single page is whether this number could be the price of this film at this shop, and that
turns out to catch most of it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

#: Symbols and codes a UK retailer might use. Used to *recognise* a price, not to convert
#: one — a scraper that silently converted currencies would be inventing data.
CURRENCY_SYMBOLS = {"£": "GBP", "$": "USD", "€": "EUR"}

#: A price with no currency marker anywhere near it is usually not a price. "12" in a
#: `.price` node is far more often a quantity, a rating or a running time.
PRICE_PATTERN = re.compile(
    r"(?P<symbol>[£$€])?\s*(?P<amount>\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"
)

#: A physical disc under this is almost always a fragment — a "£0.00" placeholder, a
#: postage line, or a discount amount picked up instead of the price.
MIN_PLAUSIBLE = Decimal("0.50")

#: Above this it is not a Blu-ray. A four-figure result is a selector that matched a TV,
#: a bundle, or a concatenation of two numbers.
MAX_PLAUSIBLE = Decimal("500.00")

#: Evidence that a listing is a **disc** rather than something else with the film's name on
#: it. Searching Zavvi for "Jaws" returns a beach towel, a Christmas jumper and nine
#: T-shirts before any disc — every one of which has "Jaws" in its title, a £ price in a
#: plausible range, and a zavvi.com URL. All five of the original shape rules pass, and the
#: price of a towel is written as the price of the film.
#:
#: An **allowlist**, not a blocklist of "towel", "t-shirt", "mug": merchandise is unbounded
#: and a blocklist would be one product category behind forever. A listing that names no
#: format is refused, which does mean the occasional real disc titled without one is
#: refused too — a stated failure rather than a wrong number, which is the trade this
#: module exists to make.
MEDIA_MARKERS = re.compile(
    r"\b(?:"
    r"4k|uhd|ultra[\s-]?hd"
    r"|blu[\s-]?ray|bluray|br|bd"
    r"|dvd"
    r"|steelbook"
    r")\b",
    re.IGNORECASE,
)

#: How each of `collection_item.FORMAT_RANK`'s codes is written on a shop's listing, so a
#: want for a specific format picks that disc out of a search that returned several.
#: ``download`` has no pattern: a digital copy is not something these shops list.
FORMAT_PATTERNS: dict[str, re.Pattern[str]] = {
    "4k_uhd": re.compile(r"\b(?:4k|uhd|ultra[\s-]?hd)\b", re.IGNORECASE),
    "blu_ray": re.compile(r"\b(?:blu[\s-]?ray|bluray|bd)\b", re.IGNORECASE),
    "dvd": re.compile(r"\bdvd\b", re.IGNORECASE),
}

#: Disc formats in descending precedence, mirroring `collection_item.FORMAT_RANK`. A combo
#: pack naming two formats **is** the higher one: "Jaws - 4K Ultra HD (Includes 2D Blu-ray)"
#: is a 4K disc that happens to bundle a Blu-ray, not a Blu-ray.
DISC_FORMATS: tuple[str, ...] = ("4k_uhd", "blu_ray", "dvd")


def primary_format(title: str | None, url: str | None = None) -> str | None:
    """Which format a listing actually **is**, rather than which ones it mentions.

    Matching on mention alone is not enough: every 4K combo pack also says "Blu-ray", so a
    want for a Blu-ray would be satisfied by a £25 4K disc whenever the combo happened to
    rank first. The highest format named wins, because that is what is in the box.
    """
    haystack = " ".join(part for part in (title, url) if part)
    if not haystack:
        return None
    for code in DISC_FORMATS:
        if FORMAT_PATTERNS[code].search(haystack):
            return code
    return None


#: How a retailer writes each format in a **search query**. THG's search returns a franchise
#: landing page full of merchandise for a bare title, and a disc grid when the query names a
#: format, so the format is part of finding the film at all rather than a nicety.
FORMAT_SEARCH_TERMS: dict[str, str] = {
    "4k_uhd": "4K",
    "blu_ray": "Blu-ray",
    "dvd": "DVD",
}

#: What to search for when a wanted item names no preferred format. "Blu-ray" is not a
#: guess at what the owner wants — it is the term that makes THG return its **disc**
#: categories, and its results include 4K editions as well.
DEFAULT_FORMAT_SEARCH_TERM = "Blu-ray"


#: Words a shop adds to a film's title that do **not** make it a different film: the format,
#: the edition, the packaging, and the articles that survive `_normalise`'s length filter.
#: A four-digit year is treated the same way by `_meaningful_extras` — "Bad Lieutenant
#: (1992)" is Bad Lieutenant.
TITLE_NOISE = frozenset(
    {
        # Format, spelled the many ways shops spell it.
        "4k",
        "uhd",
        "ultra",
        "hdr",
        "blu",
        "ray",
        "bluray",
        "dvd",
        "steelbook",
        # Edition and packaging.
        "edition",
        "editions",
        "limited",
        "standard",
        "special",
        "collector",
        "collectors",
        "collection",
        "deluxe",
        "anniversary",
        "remastered",
        "restored",
        "includes",
        "including",
        "include",
        "disc",
        "discs",
        "set",
        "boxset",
        "box",
        "slipcover",
        "digipak",
        "region",
        "version",
        "versions",
        "pack",
        "triple",
        "double",
        "dual",
        "exclusive",
        "numbered",
        "reissue",
        "release",
        "presents",
        # Articles and conjunctions long enough to survive `_normalise`.
        "the",
        "and",
        "with",
        "for",
    }
)

#: A standalone four-digit year, as shops append it: "Bad Lieutenant (1992)".
YEAR_PATTERN = re.compile(r"^(?:19|20)\d{2}$")


def edition_words(preferred_edition: str | None) -> set[str]:
    """The significant words of a wanted edition, as `_normalise` would see them."""
    return _normalise(preferred_edition) if preferred_edition else set()


def edition_matches(title: str | None, url: str | None, preferred_edition: str | None) -> bool:
    """Whether a listing is the edition asked for. **Every word has to be there.**

    A partial match is how the £35 disc and the £25 one get confused: "Arte Originale
    Slipcover" must not be satisfied by Arrow's plain "Deep Red Limited Edition 4K UHD",
    which is exactly the confusion this exists to prevent.
    """
    words = edition_words(preferred_edition)
    if not words:
        return True
    haystack = " ".join(part for part in (title, url) if part)
    return words <= _normalise(haystack)


def _meaningful_extras(
    found_title: str, expected_title: str, allowed: set[str] | None = None
) -> set[str]:
    """Words in a listing's title that name a *different film*.

    The generous one-word-in-common rule catches a page about something else entirely, but
    not the failure that actually happens: Zavvi does not stock Michael Mann's *Heat*, so a
    search for it returns *Heat and Dust*, *The Big Heat*, *Red Heat* and *Step Up 4: Miami
    Heat* — every one of which shares a significant word and would be priced as *Heat*.

    So the extra words are what matter, once the ones a shop legitimately adds are removed:
    format, edition, packaging and the release year. "Deep Red Blu-ray" adds nothing to
    "Deep Red"; "Heat and Dust" adds *dust*, and is a different film.

    ``allowed`` carries the words of a **wanted edition**. Without it the rule rejects the
    very listing the want names: "Deep Red | Arte Originale Slipcover | Limited Edition 4K
    UHD" reads *arte* and *originale* as another film (`DECISIONS.md` #104).
    """
    wanted = _normalise(expected_title)
    found = _normalise(found_title)
    permitted = TITLE_NOISE | (allowed or set())
    return {
        word for word in found - wanted if word not in permitted and not YEAR_PATTERN.match(word)
    }


def looks_like_physical_media(title: str | None, url: str | None) -> bool:
    """Whether a listing names a disc format anywhere in its title or its URL.

    Both are checked because shops split the evidence differently: Zavvi puts the category
    in the path (``/p/blu-ray/…`` against ``/p/clothing/…``), while the boutique labels put
    it in the title (``Bad Lieutenant (1992) (4K-UHD)``).
    """
    haystack = " ".join(part for part in (title, url) if part)
    return bool(haystack) and MEDIA_MARKERS.search(haystack) is not None


@dataclass(frozen=True)
class ScrapeCandidate:
    """One extracted listing, before it has been judged."""

    title: str | None
    price: Decimal | None
    currency: str | None
    url: str | None
    raw_price_text: str | None
    #: How many product cards on the page yielded a title at all, and how many of those
    #: named the film being looked for. Together they separate the two ways a search page
    #: produces no price: **the selectors broke** (nothing parsed, so `titled_cards` is 0)
    #: and **the shop does not stock the film** (listings parsed fine, none of them is it).
    #: `run_scrape` counts only the first towards auto-disable. Both stay 0 when the page
    #: is read whole rather than card by card, which is the conservative reading.
    titled_cards: int = 0
    matching_cards: int = 0


@dataclass
class ShapeVerdict:
    """Whether a candidate looks like the thing it claims to be, and why not."""

    ok: bool
    reasons: list[str] = field(default_factory=list)

    def fail(self, reason: str) -> None:
        self.ok = False
        self.reasons.append(reason)


def parse_price(text: str | None) -> tuple[Decimal | None, str | None]:
    """Pull a price and its currency out of a text node.

    Returns ``(None, None)`` rather than guessing. A node reading "Save £3.00" contains a
    perfectly parseable number that is **not the price**, so callers get the currency back
    too and the shape checks below use its presence as evidence.
    """
    if not text:
        return None, None
    cleaned = " ".join(text.split())
    match = PRICE_PATTERN.search(cleaned)
    if not match:
        return None, None
    try:
        amount = Decimal(match.group("amount").replace(",", ""))
    except InvalidOperation:
        return None, None
    symbol = match.group("symbol")
    currency = CURRENCY_SYMBOLS.get(symbol) if symbol else None
    if currency is None:
        # No symbol beside the number. Look for a three-letter code in the same node,
        # which is how some shops mark it up.
        code = re.search(r"\b(GBP|USD|EUR)\b", cleaned)
        currency = code.group(1) if code else None
    return amount, currency


def _text_of(node: Tag | None) -> str | None:
    if node is None:
        return None
    text = node.get_text(" ", strip=True)
    return text or None


def split_selectors(selector: str) -> list[str]:
    """A comma-separated selector, as a list — **in the order it was written**.

    Commas inside brackets, parentheses or quotes are not separators:
    ``[data-a="x,y"]`` and ``:is(a, b)`` stay whole.
    """
    parts: list[str] = []
    depth = 0
    quote: str | None = None
    current: list[str] = []
    for char in selector:
        if quote:
            if char == quote:
                quote = None
            current.append(char)
            continue
        if char in "\"'":
            quote = char
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            piece = "".join(current).strip()
            if piece:
                parts.append(piece)
            current = []
            continue
        current.append(char)
    piece = "".join(current).strip()
    if piece:
        parts.append(piece)
    return parts


def _select_one(scope: BeautifulSoup | Tag, selector: str) -> Tag | None:
    """``select_one``, except that a **card can be its own match**, and that a
    comma-separated selector is a **fallback list tried in order**.

    `select_one` searches descendants only. Powerhouse's product card *is* its link
    (``<a class="list-view-item">``), so scoping extraction to the card would otherwise
    make its own URL unreachable — the selector matches the scope, and nothing inside it.

    **Order matters, and CSS does not give it to us.** `select_one("a, b")` returns
    whichever comes first *in the document*, not whichever selector was written first — so
    Second Sight's `".price-item--sale, .price-item--regular"` returned the regular price
    whenever the markup happened to put it first, silently ignoring the sale it was written
    to prefer. Trying each in turn is what that configuration always meant.
    """
    try:
        for part in split_selectors(selector):
            if isinstance(scope, Tag) and scope.name != "[document]" and scope.css.match(part):
                return scope
            found = scope.select_one(part)
            if found is not None:
                return found
        return None
    except Exception:  # noqa: BLE001 - a bad selector is admin input, not a crash
        return None


def select_one_text(soup: BeautifulSoup | Tag, selector: str | None) -> str | None:
    if not selector:
        return None
    return _text_of(_select_one(soup, selector))


def select_one_attr(soup: BeautifulSoup | Tag, selector: str | None, attr: str) -> str | None:
    if not selector:
        return None
    node = _select_one(soup, selector)
    if node is None:
        return None
    value = node.get(attr)
    if isinstance(value, list):
        value = value[0] if value else None
    return str(value) if value else None


def _candidate_from(scope: BeautifulSoup | Tag, config: dict[str, object]) -> ScrapeCandidate:
    """Read one listing's fields from ``scope`` — a whole page, or a single product card."""
    title = select_one_text(scope, _string(config.get("title")))
    raw_price = select_one_text(scope, _string(config.get("price")))
    price, currency = parse_price(raw_price)
    url = select_one_attr(scope, _string(config.get("url")), "href")
    return ScrapeCandidate(
        title=title, price=price, currency=currency, url=url, raw_price_text=raw_price
    )


def _matches_title(
    title: str | None, expected_title: str | None, preferred_edition: str | None = None
) -> bool:
    """The same title test `check_shape` applies, so a card it would reject never wins."""
    if not expected_title:
        return True
    if not title:
        return False
    wanted_words = _normalise(expected_title)
    if not wanted_words:
        return True
    if not wanted_words & _normalise(title):
        return False
    return not _meaningful_extras(title, expected_title, edition_words(preferred_edition))


def extract(
    html: str,
    config: dict[str, object],
    *,
    expected_title: str | None = None,
    preferred_format: str | None = None,
    preferred_edition: str | None = None,
) -> ScrapeCandidate:
    """Run a retailer's configured selectors over a page and pick the best listing on it.

    ``config`` is §3.16's ``scraper_config``: ``{"item": "...", "title": "...",
    "price": "...", "url": "..."}``. Anything missing simply yields ``None`` — a
    half-configured retailer produces a candidate that fails the shape checks, which is the
    right outcome and a legible one.

    **``item`` is what makes this a search-results reader rather than a first-node reader.**
    Without it each selector runs over the whole page independently, so the title can come
    from one product and the price from another whenever a card is missing a field. With
    it, each card is read whole, and the *first card that is actually the film on disc*
    wins rather than simply the first card:

    - Searching Zavvi for "Jaws" returns a beach towel first and a T-shirt second. Reading
      card by card lets a disc further down the page win.
    - Searching 101 Films for "Bad Lieutenant" returns the 4K, the Blu-ray and a limited
      edition of both. ``preferred_format`` is the wanted item's own answer to which of
      those to price, and it was previously unused.

    ``preferred_edition`` picks between editions *within* a format. Arrow sells Deep Red on
    4K three times over — plain, Limited Edition, and an "Arte Originale Slipcover" at more
    than twice the price — and without it page order decided which one a `max_price` alert
    was about.

    When no card qualifies, the **first** card is returned rather than nothing, so
    `check_shape` reports why the page was rejected — "names no disc format" — instead of
    the misleading "no price found" an empty candidate would produce.
    """
    soup = BeautifulSoup(html, "html.parser")
    item_selector = _string(config.get("item"))
    if not item_selector:
        return _candidate_from(soup, config)

    cards: list[Tag] = []
    try:
        cards = list(soup.select(item_selector))
    except Exception:  # noqa: BLE001 - a bad selector is admin input, not a crash
        cards = []
    if not cards:
        return _candidate_from(soup, config)

    seen: set[str] = set()
    candidates: list[ScrapeCandidate] = []
    for card in cards:
        candidate = _candidate_from(card, config)
        # Shops render the same product twice for grid and list layouts; a duplicate is
        # not a second listing and must not out-rank a better one below it.
        key = candidate.url or candidate.title or ""
        if key and key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)

    # Counted before any price or media filtering, because this pair answers a different
    # question from "can we price it": did the page parse into real listings, and is the
    # film among them. A shop that answered properly and simply has not got it must not
    # accrue a strike towards auto-disable.
    titled = sum(1 for candidate in candidates if candidate.title)
    matching = sum(
        1
        for candidate in candidates
        if candidate.title and _matches_title(candidate.title, expected_title, preferred_edition)
    )

    def counted(candidate: ScrapeCandidate) -> ScrapeCandidate:
        return replace(candidate, titled_cards=titled, matching_cards=matching)

    qualifying = [
        candidate
        for candidate in candidates
        if candidate.price is not None
        and _matches_title(candidate.title, expected_title, preferred_edition)
        and looks_like_physical_media(candidate.title, candidate.url)
    ]
    if not qualifying:
        return counted(candidates[0])

    # Both constraints, then format, then edition, then the shop's own order. Format wins
    # over edition when only one can be had: a Steelbook is still a disc you cannot play
    # if it is the wrong format, whereas a plain edition of the right format is usable.
    wants_format = preferred_format in DISC_FORMATS
    wants_edition = bool(edition_words(preferred_edition))
    if wants_format or wants_edition:

        def ranked(candidate: ScrapeCandidate) -> tuple[bool, bool]:
            format_ok = (
                primary_format(candidate.title, candidate.url) == preferred_format
                if wants_format
                else False
            )
            edition_ok = (
                edition_matches(candidate.title, candidate.url, preferred_edition)
                if wants_edition
                else False
            )
            return (format_ok, edition_ok)

        for want in ((True, True), (True, False), (False, True)):
            if want[0] and not wants_format:
                continue
            if want[1] and not wants_edition:
                continue
            for candidate in qualifying:
                if ranked(candidate) == want:
                    return counted(candidate)
    return counted(qualifying[0])


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _normalise(text: str) -> set[str]:
    return {word for word in re.sub(r"[^a-z0-9 ]", " ", text.lower()).split() if len(word) > 2}


def check_shape(
    candidate: ScrapeCandidate,
    *,
    expected_title: str | None = None,
    expected_currency: str = "GBP",
    retailer_host: str | None = None,
    preferred_edition: str | None = None,
) -> ShapeVerdict:
    """The "last known good shape" assertion the ledger's risk note asks for.

    Every check is one way a wrong node has looked in practice:

    - **No price at all** — the selector matched nothing, or matched something with no
      number in it. Common the day after a redesign.
    - **A price outside a plausible range** — under 50p is a postage line or a "£0.00"
      placeholder; over £500 is a television, a bundle, or two numbers run together.
    - **No currency marker anywhere in the node** — the single strongest signal that a
      number is not a price. A `.price` node that yields a bare "12" is usually a rating,
      a quantity or a running time.
    - **A currency that is not the one expected** — a shop switching to a US storefront
      would otherwise report dollar prices as pounds, and every alert would fire.
    - **A title with nothing in common with the film asked for** — the strongest guard
      against the *quiet* failure, where the selectors work perfectly on the wrong page.
    - **A title naming a different film** — the same failure one step subtler. A shop that
      does not stock the film still returns results: *Heat* at Zavvi yields *Heat and
      Dust*, *The Big Heat* and *Red Heat*, all of which share a word.
    - **A listing URL on a different domain** — an advert, or a "customers also bought".
    - **A listing that names no disc format** — the merchandise case. "Jaws" at Zavvi is a
      beach towel long before it is a Blu-ray, and every other rule passes on a towel.
    """
    verdict = ShapeVerdict(ok=True)

    if candidate.price is None:
        verdict.fail("no price found — the selector matched nothing usable")
        # Everything below is about the price, so there is nothing more to say.
        return verdict

    if candidate.price < MIN_PLAUSIBLE:
        verdict.fail(f"price {candidate.price} is below the plausible floor")
    if candidate.price > MAX_PLAUSIBLE:
        verdict.fail(f"price {candidate.price} is above the plausible ceiling")

    if candidate.currency is None:
        verdict.fail(
            "no currency marker beside the number — probably not a price "
            f"(node read: {candidate.raw_price_text!r})"
        )
    elif candidate.currency != expected_currency:
        verdict.fail(f"currency {candidate.currency} is not the expected {expected_currency}")

    if expected_title:
        if not candidate.title:
            verdict.fail("no title found, so the page cannot be matched to the film")
        else:
            wanted_words = _normalise(expected_title)
            found_words = _normalise(candidate.title)
            # One significant word in common. Deliberately generous — retailers append
            # "[Blu-ray]", "(4K UHD)", edition names and year suffixes — but enough to
            # catch a page about an entirely different film, which is the failure that
            # otherwise looks completely normal.
            if wanted_words and not wanted_words.intersection(found_words):
                verdict.fail(
                    f"page title {candidate.title!r} has nothing in common with {expected_title!r}"
                )
            else:
                extras = _meaningful_extras(
                    candidate.title, expected_title, edition_words(preferred_edition)
                )
                if extras:
                    verdict.fail(
                        f"page title {candidate.title!r} names a different film from "
                        f"{expected_title!r} ({', '.join(sorted(extras))})"
                    )

    if candidate.url and retailer_host:
        host = urlparse(candidate.url).hostname
        if host and not _same_site(host, retailer_host):
            verdict.fail(f"listing URL is on {host}, not {retailer_host}")

    if not looks_like_physical_media(candidate.title, candidate.url):
        verdict.fail(
            f"listing names no disc format, so it is probably merchandise rather than the "
            f"film (title read: {candidate.title!r})"
        )

    return verdict


#: Public suffixes made of more than one label, where the last two labels of a hostname are
#: a *suffix* rather than a domain. Without these, ``secondsightfilms.co.uk`` and any other
#: ``.co.uk`` host compare equal and the listing-URL guard passes anything on the whole TLD.
#:
#: This is a pragmatic list, not the Public Suffix List: it covers the UK — where every
#: retailer this app scrapes lives — plus the country suffixes a film shop plausibly uses.
#: An unlisted multi-part suffix falls back to the last two labels, so the guard is never
#: weaker than it was before this list existed, only stronger for what it knows.
MULTI_LABEL_SUFFIXES = frozenset(
    {
        "ac.uk",
        "co.uk",
        "gov.uk",
        "ltd.uk",
        "me.uk",
        "net.uk",
        "org.uk",
        "plc.uk",
        "sch.uk",
        "com.au",
        "net.au",
        "org.au",
        "co.nz",
        "co.jp",
        "co.za",
        "co.in",
        "co.kr",
        "co.il",
        "com.br",
        "com.hk",
        "com.mx",
        "com.sg",
        "com.tr",
    }
)


def _registrable_domain(host: str) -> str:
    """The shop-identifying part of a hostname: one label plus its public suffix.

    ``store.hmv.com`` and ``www.hmv.com`` both reduce to ``hmv.com``; ``evil.co.uk`` and
    ``secondsightfilms.co.uk`` reduce to themselves and so are correctly different shops.
    """
    parts = host.lower().strip(".").split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in MULTI_LABEL_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _host_of(value: str) -> str:
    """A hostname, whether it arrives as one or as a whole URL.

    Callers disagree. The price runner passes ``urlparse(base_url).hostname``; the deals
    runner and §5.4's test tool passed the retailer's ``base_url`` itself. Read as a
    hostname, ``https://secondsightfilms.co.uk`` keeps its scheme glued to its first label,
    so it matched none of that shop's own listings, and nor did ``https://101-films-store.com``.
    ``https://www.zavvi.com`` hid the fault only because its last two labels survive
    (Batch 22b).
    """
    if "://" in value:
        return urlparse(value).hostname or value
    return value


def _same_site(host: str, expected: str) -> bool:
    """Same registrable domain. ``www.hmv.com`` and ``store.hmv.com`` are one shop.

    ``secondsightfilms.co.uk`` and ``someoneelse.co.uk`` are **not**, which is the whole
    point: a listing URL that leaves the retailer is how a plausible wrong number gets in.
    Either side may be a hostname or a URL (:func:`_host_of`).
    """
    return _registrable_domain(_host_of(host)) == _registrable_domain(_host_of(expected))
