"""eBay integration — Batch 28, phases 4.1 and 4.3.

A package of its own rather than a retailer inside Batch 19's scraper framework, per
`docs/phase-batches.md`: eBay is a fixed host with a typed API, ``check_shape`` exists for
HTML drift, and #16's accepted ToS exposure covers retailers rather than eBay.

Four modules, and the middle two carry the batch:

- :mod:`~src.ebay.client` — the Browse API, and the token cache ``src/tmdb/`` has no
  equivalent of.
- :mod:`~src.ebay.matching` — whether a listing is *the disc you asked for*.
- :mod:`~src.ebay.pricing` — medians per segment, with the sample size and the rejections.
- :mod:`~src.ebay.listing` — Phase 4.3's pre-filled listing URL.

Everything produced here is **current asking prices**. Sold comps are unobtainable
(`DECISIONS.md` #16, #126) and no surface may imply otherwise.
"""

from .client import EbayClient, EbayError, EbayNotConfigured
from .listing import prelist_url, suggested_price, suggested_title
from .matching import Listing, MatchVerdict, listing_from_summary, match
from .pricing import ASKING_PRICES, PriceEstimate, PriceSegment, summarise

__all__ = [
    "ASKING_PRICES",
    "EbayClient",
    "EbayError",
    "EbayNotConfigured",
    "Listing",
    "MatchVerdict",
    "PriceEstimate",
    "PriceSegment",
    "listing_from_summary",
    "match",
    "prelist_url",
    "suggested_price",
    "suggested_title",
    "summarise",
]
