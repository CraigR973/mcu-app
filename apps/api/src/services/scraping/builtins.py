"""The six built-in retailer configurations — roadmap §5.3.

**Every selector here is unverified, and the module says so in the data.** §5.3 names six
shops: "HMV, Amazon UK, Blu-ray.com, Zavvi, Arrow, CEX". Its acceptance is that each one
runs *against the live retailer* — which `group-start.md` makes a hard stop: the owner
performs live third-party runs, not the agent. So these are **starting points for that
run**, not working scrapers, and each carries ``verified: false`` until someone has seen it
work against a real page.

That flag is not decoration. The ledger's risk note for this batch is that a wrong selector
*"does not error — it selects the wrong node and persists a plausible wrong number"*, and
the honest state of a selector nobody has run is exactly "wrong until shown otherwise".
`extract.check_shape` is what stops an unverified guess reaching the database; this flag is
what stops a person believing it has been checked.

**§5.3 and §3.16 disagree about the sixth shop.** §5.3 lists **CEX**; §3.16's seeded
defaults list **Criterion**. Both are here: Criterion because Batch 18 seeded it, CEX
because §5.3 asks for it. Neither list is wrong, they were written for different purposes —
§3.16's is "shops to watch", §5.3's is "scrapers to write".
"""

from __future__ import annotations

from typing import Any

#: Keyed by the retailer name Batch 18 seeds, so a config finds its row without a join.
#:
#: ``search`` is §3.16's ``search_url_template``; ``config`` is its ``scraper_config``.
#: The selectors are best-effort readings of each site's public markup **as of writing**
#: and have not been run. `verified` says so.
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
        "search": "https://www.zavvi.com/search?q={query}",
        "config": {
            "title": "[data-testid='product-title']",
            "price": "[data-testid='product-price'] .product-variant-price",
            "url": "[data-testid='product-title']",
        },
        "verified": False,
    },
    "Arrow Video": {
        "search": "https://www.arrowvideo.com/search?q={query}",
        "config": {
            "title": ".product-item-meta__title, .product-title",
            "price": ".price, .price-list .price--highlight",
            "url": ".product-item-meta__title, .product-title",
        },
        "verified": False,
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
}


def config_for(name: str) -> dict[str, Any] | None:
    """The built-in configuration for a seeded retailer, if there is one."""
    return BUILT_IN_SCRAPERS.get(name)


def unverified_names() -> list[str]:
    """Every built-in whose selectors nobody has run against a live page.

    All six, today. Reported by the API so a settings page can say so rather than implying
    six working scrapers exist.
    """
    return [name for name, entry in BUILT_IN_SCRAPERS.items() if not entry.get("verified", False)]
