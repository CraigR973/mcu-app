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
        # Already seeded by Batch 18 and the only deals URL that existed before this
        # batch. The card selectors are Batch 19's, verified live.
        "deals": {
            "url": "https://www.zavvi.com/sale.list",
            "was": "[data-testid='product-price'] .product-price__rrp, .rrp",
            "image": "img",
            "verified": False,
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
        "deals": {
            "url": "https://secondsightfilms.co.uk/collections/sale",
            "was": ".price-item--regular, s .money",
            "image": "img",
            "verified": False,
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

    **The selectors are verified; the URLs are not, and the distinction matters.** Each
    `item`/`title`/`price`/`url` selector is the one Batch 19 checked against that shop's
    live markup on 2026-09-09, and it applies unchanged here because a Shopify collection
    page renders the same product card as a Shopify search page. What is new is the `was`
    selector and the sale-page URL, and **neither has been run against the live site** —
    `verified: False` on every one of them says so.

    That is deliberate rather than lazy. `docs/agent-commands/group-start.md` puts live
    retailer requests in the owner's hands, so the run that proves these is the same run
    that satisfies §5.9's acceptance. Batch 19 shipped on exactly this footing and its
    owner-run checkpoint found real defects (`DECISIONS.md` #91, #92, #94) — which is the
    argument for the arrangement, not against it.
    """
    entry = BUILT_IN_SCRAPERS.get(name)
    deals = entry.get("deals") if entry else None
    return dict(deals) if isinstance(deals, dict) else None


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
