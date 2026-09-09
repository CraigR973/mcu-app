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
from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class ScrapeCandidate:
    """One extracted listing, before it has been judged."""

    title: str | None
    price: Decimal | None
    currency: str | None
    url: str | None
    raw_price_text: str | None


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


def select_one_text(soup: BeautifulSoup, selector: str | None) -> str | None:
    if not selector:
        return None
    try:
        return _text_of(soup.select_one(selector))
    except Exception:  # noqa: BLE001 - a bad selector is admin input, not a crash
        return None


def select_one_attr(soup: BeautifulSoup, selector: str | None, attr: str) -> str | None:
    if not selector:
        return None
    try:
        node = soup.select_one(selector)
    except Exception:  # noqa: BLE001 - as above
        return None
    if node is None:
        return None
    value = node.get(attr)
    if isinstance(value, list):
        value = value[0] if value else None
    return str(value) if value else None


def extract(html: str, config: dict[str, object]) -> ScrapeCandidate:
    """Run a retailer's configured selectors over a page.

    ``config`` is §3.16's ``scraper_config``: ``{"title": "...", "price": "...",
    "url": "..."}``. Anything missing simply yields ``None`` — a half-configured retailer
    produces a candidate that fails the shape checks, which is the right outcome and a
    legible one.
    """
    soup = BeautifulSoup(html, "html.parser")
    title = select_one_text(soup, _string(config.get("title")))
    raw_price = select_one_text(soup, _string(config.get("price")))
    price, currency = parse_price(raw_price)
    url = select_one_attr(soup, _string(config.get("url")), "href")
    return ScrapeCandidate(
        title=title, price=price, currency=currency, url=url, raw_price_text=raw_price
    )


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
    - **A listing URL on a different domain** — an advert, or a "customers also bought".
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

    if candidate.url and retailer_host:
        host = urlparse(candidate.url).hostname
        if host and not _same_site(host, retailer_host):
            verdict.fail(f"listing URL is on {host}, not {retailer_host}")

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


def _same_site(host: str, expected: str) -> bool:
    """Same registrable domain. ``www.hmv.com`` and ``store.hmv.com`` are one shop.

    ``secondsightfilms.co.uk`` and ``someoneelse.co.uk`` are **not**, which is the whole
    point: a listing URL that leaves the retailer is how a plausible wrong number gets in.
    """
    return _registrable_domain(host) == _registrable_domain(expected)
