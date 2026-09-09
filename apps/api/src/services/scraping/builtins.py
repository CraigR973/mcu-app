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
        "base": "https://www.zavvi.com",
        "search": "https://www.zavvi.com/search?q={query}",
        "config": {
            "title": "[data-testid='product-title']",
            "price": "[data-testid='product-price'] .product-variant-price",
            "url": "[data-testid='product-title']",
        },
        "verified": True,
        "note": "Verified against the live UK storefront on 2026-09-09.",
    },
    "Arrow Video": {
        # arrowvideo.com is the US storefront and correctly returns USD. Arrow's UK shop
        # is arrowfilms.com; using the US domain made the GBP shape guard reject every
        # otherwise-valid result.
        "base": "https://www.arrowfilms.com",
        "search": "https://www.arrowfilms.com/search?q={query}",
        "config": {
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
        "base": "https://101-films-store.com",
        "search": "https://101-films-store.com/search?q={query}&type=product",
        "config": {
            "title": ".prod-title",
            "price": ".product-info-inner .money",
            "url": ".product-info-inner a",
        },
        "verified": True,
        "note": "Verified against the live UK storefront on 2026-09-09.",
    },
    "Second Sight": {
        "base": "https://secondsightfilms.co.uk",
        "search": "https://secondsightfilms.co.uk/search?q={query}&type=product",
        "config": {
            "title": ".card__heading a",
            "price": ".price-item--sale, .price-item--regular",
            "url": ".card__heading a",
        },
        "verified": True,
        "note": "Verified against the live UK storefront on 2026-09-09.",
    },
    "Powerhouse Films": {
        "base": "https://www.powerhousefilms.co.uk",
        "search": "https://www.powerhousefilms.co.uk/search?q={query}&type=product",
        "config": {
            "title": ".list-view-item__title",
            "price": ".product-price__price",
            "url": "a.list-view-item",
        },
        "verified": True,
        "note": "Verified against the live UK storefront on 2026-09-09.",
    },
}


def config_for(name: str) -> dict[str, Any] | None:
    """The built-in configuration for a seeded retailer, if there is one."""
    return BUILT_IN_SCRAPERS.get(name)


def unverified_names() -> list[str]:
    """Every built-in whose selectors have not passed a permitted live check."""
    return [name for name, entry in BUILT_IN_SCRAPERS.items() if not entry.get("verified", False)]
