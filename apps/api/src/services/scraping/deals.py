"""Reading a retailer's sale page — Batch 22, Phase 5.9.

**The ledger's risk note is the whole design brief:**

> A deals page that changes layout does not error — it selects the wrong node and stores a
> plausible wrong discount, which then feeds the feed. Batch 19's `check_shape` is the
> pattern; extend it rather than adding a bare success counter.

So this module is `extract.check_shape`'s reasoning applied to a different shape, plus one
thing that module could not have: a **page-level** assertion.

**Why a per-result check is not enough here, and was enough for §5.3.** A wanted-item
scrape asks one question — "what does this shop charge for *this film*?" — and
`check_shape`'s strongest guard is that the title on the page matches the film asked for.
A deals page has no expected title. Whatever the shop has discounted is the answer, so the
single most powerful rule in the existing checker simply does not apply, and something has
to replace it.

What replaces it is **agreement across the page**. A sale page yields forty cards, and the
ways a selector goes wrong are visible in the population even when each individual result
looks fine:

- Every card carrying the **same** discount is one shared node being read forty times —
  a "Up to 70% off" banner matched by the `was` selector. Each row is plausible; the set
  is impossible.
- Every card yielding **no** `was` price is the sale-price selector having moved, which
  turns a sale page into a price list and makes every discount null.
- A page that yields **nothing at all** after previously yielding forty is drift, and is
  the one case a success counter does catch — which is why a success counter feels
  sufficient right up until it is not.

:func:`check_page_shape` is those three. :func:`check_deal_shape` is the per-card half.

**`discount_percent` is arithmetic, never a selector.** A shop's own "save 60%" badge is
exactly the kind of node a layout change hands to the wrong reader, and it is redundant:
two prices that have each passed a range and currency check already contain the answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from src.services.scraping.extract import (
    MAX_PLAUSIBLE,
    MIN_PLAUSIBLE,
    ShapeVerdict,
    _same_site,
    _select_one,
    _text_of,
    looks_like_physical_media,
    parse_price,
    primary_format,
)

#: Below this a "discount" is rounding or a penny difference in a variant price, not an
#: offer worth putting in a feed.
MIN_DISCOUNT_PERCENT = 3

#: At or above this the `was` price is almost certainly not this product's. A genuine 95%
#: off a disc means a £40 box set at £2, which shops do not do; a selector that caught a
#: bundle's total, or a "from £1" placeholder, does exactly this.
MAX_DISCOUNT_PERCENT = 95

#: How many cards a sale page has to yield before the population checks mean anything.
#: Below this, "every card has the same discount" is a coincidence rather than a signal.
MIN_CARDS_FOR_POPULATION_CHECKS = 5


@dataclass(frozen=True)
class DealCandidate:
    """One card on a sale page, before it has been judged."""

    title: str | None
    price: Decimal | None
    was_price: Decimal | None
    currency: str | None
    url: str | None
    image_url: str | None = None
    raw_price_text: str | None = None
    raw_was_text: str | None = None

    @property
    def discount_percent(self) -> int | None:
        """Arithmetic on the two prices. Never a number read off the page."""
        if self.price is None or self.was_price is None or self.was_price <= 0:
            return None
        if self.was_price <= self.price:
            return None
        return int(round((self.was_price - self.price) / self.was_price * 100))


@dataclass
class PageVerdict:
    """Whether a sale page as a whole looks like a sale page."""

    ok: bool = True
    reasons: list[str] = field(default_factory=list)

    def fail(self, reason: str) -> None:
        self.ok = False
        self.reasons.append(reason)


def extract_deals(html: str, config: dict[str, object], *, page_url: str) -> list[DealCandidate]:
    """Every product card on a sale page.

    ``config`` extends §3.16's ``scraper_config`` with one key: ``was`` — the selector for
    the struck-through original price. Everything else (``item``, ``title``, ``price``,
    ``url``, ``image``) is the same vocabulary the wanted-item scrapers already use, and
    the **same selectors work**: a Shopify collection page and a Shopify search page render
    the same product card. That reuse is why this batch ships selectors that were verified
    live in Batch 19 rather than selectors nobody has run.
    """
    item_selector = config.get("item")
    if not isinstance(item_selector, str) or not item_selector:
        # Without a card selector every selector runs over the whole page independently,
        # so the title comes from one product and the price from another. `extract` makes
        # the same point; here it would be worse, because there is no expected title to
        # catch the mismatch.
        return []

    soup = BeautifulSoup(html, "html.parser")
    candidates: list[DealCandidate] = []

    for card in soup.select(item_selector):
        if not isinstance(card, Tag):
            continue
        candidates.append(_card_to_candidate(card, config, page_url=page_url))
    return candidates


def _pick(card: Tag, selector: object) -> Tag | None:
    """``_select_one`` for a selector that came out of a JSONB config.

    A retailer's ``scraper_config`` is free-form JSON, so a missing or non-string key is
    an ordinary state rather than a bug — a half-configured retailer should yield a
    candidate that fails the shape checks, which is legible, not a ``TypeError``.
    """
    return _select_one(card, selector) if isinstance(selector, str) and selector else None


def _card_to_candidate(card: Tag, config: dict[str, object], *, page_url: str) -> DealCandidate:
    title = _text_of(_pick(card, config.get("title")))
    price_text = _text_of(_pick(card, config.get("price")))
    was_text = _text_of(_pick(card, config.get("was")))

    price, currency = parse_price(price_text)
    was_price, was_currency = parse_price(was_text)

    # A `was` in a different currency is not this product's previous price.
    if was_currency is not None and currency is not None and was_currency != currency:
        was_price = None

    link = _pick(card, config.get("url"))
    href = link.get("href") if isinstance(link, Tag) else None
    if not href:
        # **The configured `url` selector often points at the title, and a title is not
        # always a link.** Measured against the captured Zavvi cards: `product-title` is a
        # heading, so the configured selector yields no href and every deal from that shop
        # would have arrived with no URL — unclickable, and all colliding on `''` under the
        # `(retailer_id, url)` uniqueness key.
        #
        # A wanted-item scrape survives that (it has a price and a title, and the
        # same-site guard simply does not run), which is why it was never noticed. A deal
        # does not. So: the card's own href if it is an anchor, else the first anchor
        # inside it — the same "a card can be its own match" reasoning `_select_one`
        # already applies.
        anchor = card if card.name == "a" and card.get("href") else card.select_one("a[href]")
        href = anchor.get("href") if isinstance(anchor, Tag) else None
    # Retailer cards carry relative links. Resolving against the page makes the stored
    # link usable *and* lets the same-site guard see a hostname at all — an unresolved
    # relative URL has none, so the guard was skipped entirely (`DECISIONS.md` #94).
    url = urljoin(page_url, str(href)) if href else None

    image = _pick(card, config.get("image"))
    image_url = None
    if isinstance(image, Tag):
        raw = image.get("src") or image.get("data-src")
        image_url = urljoin(page_url, str(raw)) if raw else None

    return DealCandidate(
        title=title,
        price=price,
        was_price=was_price,
        currency=currency,
        url=url,
        image_url=image_url,
        raw_price_text=price_text,
        raw_was_text=was_text,
    )


def check_deal_shape(
    candidate: DealCandidate,
    *,
    expected_currency: str = "GBP",
    retailer_host: str | None = None,
) -> ShapeVerdict:
    """`extract.check_shape`'s per-result rules, restated for a card with two prices.

    Every rule is one way a sale-page selector has a plausible wrong answer:

    - **No sale price** — the card matched but the price node moved.
    - **A price outside the plausible range** — the same floor and ceiling the wanted-item
      checker uses, for the same reasons.
    - **No currency marker** — the single strongest signal that a number is not a price.
    - **A `was` that is not above the `now`** — the most likely layout failure of all, and
      the one unique to this page type: the *same node read twice*. Both figures parse,
      both are plausible, and the discount is zero or negative.
    - **An implausible discount** — a `was` belonging to a bundle, or a "from £1"
      placeholder read as the sale price.
    - **A link off the retailer's domain** — an advert in the grid.
    - **A title naming no disc format** — a sale page sells merchandise too, and Zavvi's
      in particular sells a great deal of it.

    There is deliberately **no title-match rule**. A deals page has no expected title;
    :func:`check_page_shape` is what covers the ground that rule covered.
    """
    verdict = ShapeVerdict(ok=True)

    if candidate.price is None:
        verdict.fail("no sale price found — the selector matched nothing usable")
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

    if candidate.was_price is not None:
        if candidate.was_price <= candidate.price:
            verdict.fail(
                f"'was' price {candidate.was_price} is not above the sale price "
                f"{candidate.price} — the two selectors are probably reading one node"
            )
        else:
            discount = candidate.discount_percent
            if discount is not None and discount < MIN_DISCOUNT_PERCENT:
                verdict.fail(f"a {discount}% discount is rounding, not an offer")
            if discount is not None and discount >= MAX_DISCOUNT_PERCENT:
                verdict.fail(
                    f"a {discount}% discount is implausible — the 'was' price "
                    f"{candidate.was_price} probably belongs to something else"
                )

    if candidate.url and retailer_host:
        host = urlparse(candidate.url).hostname
        if host and not _same_site(host, retailer_host):
            verdict.fail(f"listing URL is on {host}, not {retailer_host}")

    if not looks_like_physical_media(candidate.title, candidate.url):
        verdict.fail(
            "card names no disc format, so it is probably merchandise rather than a film "
            f"(title read: {candidate.title!r})"
        )

    return verdict


def check_page_shape(candidates: list[DealCandidate]) -> PageVerdict:
    """The assertion a per-result check cannot make — Batch 22's extension of #79.

    A wanted-item scrape can ask "is this the film I wanted?". A sale page cannot, so the
    evidence has to come from the population. Each of these is a real shape a broken
    selector produces, and each leaves every individual card looking entirely reasonable.
    """
    verdict = PageVerdict()

    if not candidates:
        verdict.fail("the page yielded no product cards at all")
        return verdict

    if len(candidates) < MIN_CARDS_FOR_POPULATION_CHECKS:
        # Too few to reason about. Not a failure — a small sale is a real thing — but the
        # population rules below would be superstition at this size.
        return verdict

    discounts = [candidate.discount_percent for candidate in candidates]
    present = [value for value in discounts if value is not None]

    if not present:
        verdict.fail(
            "no card on the page has a 'was' price — the sale-price selector has "
            "probably moved, which turns a sale page into a price list"
        )
    elif len(set(present)) == 1 and len(present) >= MIN_CARDS_FOR_POPULATION_CHECKS:
        verdict.fail(
            f"every one of {len(present)} cards shows the same {present[0]}% discount — "
            "the 'was' selector is reading one shared node, probably a banner"
        )

    prices = [candidate.price for candidate in candidates if candidate.price is not None]
    if len(set(prices)) == 1 and len(prices) >= MIN_CARDS_FOR_POPULATION_CHECKS:
        verdict.fail(
            f"every one of {len(prices)} cards shows the same price — the price selector "
            "is reading one shared node"
        )

    titled = [candidate for candidate in candidates if candidate.title]
    if not titled:
        verdict.fail("no card on the page yielded a title")

    return verdict


def deal_format(candidate: DealCandidate) -> str | None:
    """Which disc format a card is, by the same rule the wanted-item scrapers use."""
    return primary_format(candidate.title, candidate.url)
