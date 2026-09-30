"""Built-in retailer configurations — roadmap §5.3.

§5.3 originally named HMV, Amazon UK, Blu-ray.com, Zavvi, Arrow and CEX. Live checks found
that only Zavvi and Arrow offer usable server-rendered search pages; blocked or disallowed
sources remain visible and unverified, while permitted UK replacements are included and
marked verified only after a live check.

That flag is not decoration. The ledger's risk note for this batch is that a wrong selector
*"does not error — it selects the wrong node and persists a plausible wrong number"*, and
the honest state of a selector nobody has run is exactly "wrong until shown otherwise".
`extract.check_shape` is what stops an unverified guess reaching the database; this flag is
what stops a person believing it has been checked.

**§5.3 and §3.16 disagree about the sixth shop.** §5.3 lists **CEX**; §3.16's seeded
defaults list **Criterion**. Both are here: Criterion because Batch 18 seeded it, CEX
because §5.3 asks for it. Neither list is wrong, they were written for different purposes —
§3.16's is "shops to watch", §5.3's is "scrapers to write".

**Four of §5.3's six stay permanently unverified, and that is the finding, not a gap.**
HMV and CEX disallow the search routes this job needs; Amazon blocks automated access and
its official API is unsuitable for a private app of this size; Blu-ray.com is a catalogue
whose prices belong to third parties. They stay listed so the app can say why rather than
implying somebody merely has not got round to them. The three UK boutique labels below
carry the general-market role instead, pending eBay (`DECISIONS.md` #91).
"""

from __future__ import annotations

from typing import Any

#: Keyed by the retailer name Batch 18 seeds, so a config finds its row without a join.
#:
#: ``search`` is §3.16's ``search_url_template``; ``config`` is its ``scraper_config``.
#: `verified` distinguishes live-checked public markup from historical starting points.
BUILT_IN_SCRAPERS: dict[str, dict[str, Any]] = {
    "HMV": {
        "search": "https://store.hmv.com/search?q={query}",
        "config": {
            "title": "a.product-title, .product-name a, h3 a",
            "price": ".product-price, .price, [data-price]",
            "url": "a.product-title, .product-name a, h3 a",
        },
        "verified": False,
    },
    "Amazon UK": {
        "search": "https://www.amazon.co.uk/s?k={query}+blu-ray",
        "config": {
            "title": "[data-component-type='s-search-result'] h2 span",
            "price": "[data-component-type='s-search-result'] .a-price .a-offscreen",
            "url": "[data-component-type='s-search-result'] h2 a",
        },
        # Amazon serves different markup to different clients and blocks aggressively.
        # Expect this one to need the most work, and possibly not to be viable at all.
        "verified": False,
        "note": "Amazon varies its markup per client and blocks scrapers; may not be viable.",
    },
    "Blu-ray.com": {
        "search": "https://www.blu-ray.com/search/?quicksearch=1&quicksearch_keyword={query}",
        "config": {
            "title": "a.hoverlink, .searchresult a",
            "price": ".price, .pricecolumn",
            "url": "a.hoverlink, .searchresult a",
        },
        "verified": False,
        "note": "A database rather than a shop — prices are third-party and may be absent.",
    },
    "Zavvi": {
        # **Batch 22b, checked against the live page captured 28 Sep.** `/sale.list` 404s
        # (found 13 Sep); Zavvi's film offers live at the flash-deals address. That evening
        # it was a landing page of two product carousels, six discs, where 13 Sep had found
        # a long list: Zavvi rotates what the page holds, and the preview says how many.
        #
        # The cards are THG's own product card, as on the search page, so Batch 19's card
        # selectors read them unchanged. The RRP is a span of its own, tagged
        # `data-product-price="rrp"` ("RRP: £29.99"). Batch 22's `.product-price__rrp, .rrp`
        # matched nothing on any Zavvi page, so the right address would still have been
        # refused as "no card has a 'was' price".
        "deals": {
            "url": "https://www.zavvi.com/c/offers/flash-deals/film/",
            "was": "[data-product-price='rrp']",
            "image": "img",
            "verified": True,
        },
        "base": "https://www.zavvi.com",
        # `{format}` is not a refinement here. A bare title redirects to a franchise
        # landing page — towels, jumpers, T-shirts, a resin statue, no discs at all.
        "search": "https://www.zavvi.com/search?q={query}%20{format}",
        "config": {
            "item": "[data-testid='product-item']",
            "title": "[data-testid='product-title']",
            # **Two markups on the same page.** A multi-variant listing wraps the figure
            # in `.product-variant-price` under a "Current price:" label; a single-price
            # listing puts it straight into the `product-price` wrapper as
            # `<p class="text-md font-bold">`. Reading only the first silently discarded
            # the second — a real £16.99 on `Castle Freak` measured on 2026-09-10 — so the
            # wrapper is the fallback. Specific first: `_select_one` tries these in order.
            "price": (
                "[data-testid='product-price'] .product-variant-price, "
                "[data-testid='product-price']"
            ),
            "url": "[data-testid='product-title']",
        },
        "verified": True,
        "note": (
            "Verified against the live UK storefront on 2026-09-09; "
            "price selector widened 2026-09-10."
        ),
    },
    "Arrow Video": {
        "deals": {
            "url": "https://www.arrowfilms.com/collections/sale",
            "was": (
                "[data-testid='product-price'] .product-price__rrp, s .money, .price-item--regular"
            ),
            "image": "img",
            "verified": False,
        },
        # arrowvideo.com is the US storefront and correctly returns USD. Arrow's UK shop
        # is arrowfilms.com; using the US domain made the GBP shape guard reject every
        # otherwise-valid result.
        "base": "https://www.arrowfilms.com",
        "search": "https://www.arrowfilms.com/search?q={query}%20{format}",
        "config": {
            "item": "[data-testid='product-item']",
            "title": "[data-testid='product-title']",
            "price": "[data-testid='product-price'] .product-variant-price",
            "url": "[data-testid='product-title']",
        },
        "verified": True,
        "note": "Verified against the live UK storefront on 2026-09-09.",
    },
    "CEX": {
        "search": "https://uk.webuy.com/search?stext={query}",
        "config": {
            "title": ".card-title, .prodName",
            "price": ".product-main-price, .prodPrice",
            "url": ".card-title a, a.prodLink",
        },
        "verified": False,
        "note": "Named by §5.3 but not among §3.16's seeded defaults; sells used stock.",
    },
    "101 Films": {
        "deals": {
            "url": "https://101-films-store.com/collections/sale",
            "was": "s .money, .price--compare, .compare-at",
            "image": "img",
            "verified": False,
        },
        "base": "https://101-films-store.com",
        "search": "https://101-films-store.com/search?q={query}&type=product",
        "config": {
            "item": ".product-info-inner",
            "title": ".prod-title",
            "price": ".money",
            "url": "a",
        },
        "verified": True,
        "note": "Verified against the live UK storefront on 2026-09-09.",
    },
    "Second Sight": {
        # **Batch 22b, checked against the live page captured 28 Sep** (Shopify's Dawn
        # theme). Dawn prints `.price-item--regular` twice on every card: first the price
        # the card sells at, then, inside `<s>`, the compare-at price, which is empty unless
        # the product is discounted, and only then does the `.price` wrapper carry
        # `price--on-sale`. Batch 22's selector read the first, so every card's "was" was
        # its own price and the page was refused (13 Sep).
        "deals": {
            "url": "https://secondsightfilms.co.uk/collections/sale",
            "was": ".price--on-sale s.price-item--regular",
            "image": "img",
            "verified": True,
        },
        "base": "https://secondsightfilms.co.uk",
        "search": "https://secondsightfilms.co.uk/search?q={query}&type=product",
        "config": {
            "item": ".card-wrapper",
            "title": ".card__heading a",
            "price": ".price-item--sale, .price-item--regular",
            "url": ".card__heading a",
        },
        "verified": True,
        "note": "Verified against the live UK storefront on 2026-09-09.",
    },
    "Powerhouse Films": {
        "deals": {
            "url": "https://www.powerhousefilms.co.uk/collections/sale",
            "was": ".product-price__compare, s .money",
            "image": "img",
            "verified": False,
        },
        "base": "https://www.powerhousefilms.co.uk",
        "search": "https://www.powerhousefilms.co.uk/search?q={query}&type=product",
        "config": {
            "item": "a.list-view-item",
            "title": ".list-view-item__title",
            "price": ".product-price__price",
            "url": "a.list-view-item",
        },
        "verified": True,
        "note": "Verified against the live UK storefront on 2026-09-09.",
    },
}


def deals_config_for(name: str) -> dict[str, Any] | None:
    """The sale-page configuration for a seeded retailer — Batch 22, Phase 5.9.

    **The card selectors are verified; a sale page is verified only once someone has read
    it.** Each `item`/`title`/`price`/`url` selector is the one Batch 19 checked against
    that shop's live markup on 2026-09-09, and it applies unchanged here because a sale
    page renders the same product card as a search page. What is new is the `was` selector
    and the sale-page URL.

    Batch 22 shipped all five of those unverified, because live retailer requests are the
    owner's (`docs/agent-commands/group-start.md`). The owner's first dry run (13 Sep)
    found both halves wrong for Zavvi and the `was` selector wrong for Second Sight, as
    Batch 19's checkpoint had found defects before it (`DECISIONS.md` #91, #92, #94).
    **Batch 22b fixed those two against pages captured on 28 Sep at Craig's word**, and
    they are marked verified. Arrow, Powerhouse and 101 Films are as Batch 22 left them:
    the first two sell bundles rather than one disc at a lower price, and 101 Films had
    nothing on sale to check against.
    """
    entry = BUILT_IN_SCRAPERS.get(name)
    deals = entry.get("deals") if entry else None
    return dict(deals) if isinstance(deals, dict) else None


#: The sale-page keys `apply-built-ins` copies into a retailer's `scraper_config`. The rest
#: of a `deals` entry is about the page, not the card: `url` is the page's address, and
#: copied over the card's `url` selector it would match nothing.
DEALS_CARD_KEYS = frozenset({"was", "image"})


def applied_scraper_config(name: str) -> dict[str, Any] | None:
    """The `scraper_config` `apply-built-ins` writes for a seeded retailer.

    The search card's selectors, plus the sale page's `was` and `image`: a sale card and a
    search card are the same markup, so the deals extractor reads `item`/`title`/`price`/
    `url` from the selectors Batch 19 verified and only needs the struck-through price
    adding. **One definition, used by the endpoint and by the tests**, because a test
    helper that merged the whole sale-page entry once put the page's address where the
    card's `url` selector belongs (Batch 22b; `DECISIONS.md` #153 was drawn from it).
    """
    entry = BUILT_IN_SCRAPERS.get(name)
    if entry is None:
        return None
    config = dict(entry["config"])
    deals = deals_config_for(name)
    if deals:
        config.update({key: value for key, value in deals.items() if key in DEALS_CARD_KEYS})
    return config


def unverified_deals_names() -> list[str]:
    """Every built-in sale page whose selectors have not passed a live check."""
    return [
        name
        for name, entry in BUILT_IN_SCRAPERS.items()
        if isinstance(entry.get("deals"), dict) and not entry["deals"].get("verified", False)
    ]


def config_for(name: str) -> dict[str, Any] | None:
    """The built-in configuration for a seeded retailer, if there is one."""
    return BUILT_IN_SCRAPERS.get(name)


def unverified_names() -> list[str]:
    """Every built-in whose selectors have not passed a permitted live check."""
    return [name for name, entry in BUILT_IN_SCRAPERS.items() if not entry.get("verified", False)]
