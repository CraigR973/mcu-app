"""One eBay search, judged and summarised: the estimator, in one place.

The film page's "What is it worth?" (Phase 4.1) and Batch T6's valuation run ask the same
question, so they share this code and a stored value agrees with a live check of the same
disc. Before T6 this lived in ``routers/ebay.py``, where only a request could reach it.
"""

from __future__ import annotations

from typing import Any, Protocol
from urllib.parse import urlencode

from ..services.scraping.extract import FORMAT_SEARCH_TERMS
from .matching import listing_from_summary, match
from .pricing import PriceEstimate, summarise

#: Sellers in this country only, as Phase 4.1's criterion asks for a *UK* median. eBay GB
#: converts an overseas seller's price into pounds without saying what the import duty will
#: be, and 52 of the 200 Blade Runner listings ship from abroad.
UK = "GB"


class EbaySearch(Protocol):
    """What the estimator needs from a client. :class:`~src.ebay.client.EbayClient` is one."""

    @property
    def marketplace_id(self) -> str: ...

    async def search(
        self, query: str, *, limit: int = ..., category_ids: str | None = None
    ) -> dict[str, Any]: ...


def search_query(film_title: str, format_code: str | None) -> str:
    """The keyword string sent to Browse.

    The format word is part of *finding* the disc, not a nicety, which is the reason
    ``extract.FORMAT_SEARCH_TERMS`` exists on the retailer side. A bare film title returns
    the soundtrack, the novel and the poster before it returns a disc; adding "Blu-ray" puts
    discs at the top of a result set that is capped at 200.

    The match filter still does the judging. This only decides which 200 it judges.
    """
    term = FORMAT_SEARCH_TERMS.get(format_code or "", "Blu-ray")
    return f"{film_title} {term}"


#: eBay UK's own search page. With ``LH_Sold`` it lists what sold, which the app can never
#: read (#16, #126); a person signed in to eBay can, in their own browser (Batch V8).
EBAY_SEARCH_PAGE = "https://www.ebay.co.uk/sch/i.html"

#: "DVDs & Blu-rays", the leaf category nearly every disc listing sits in (`matching.py`).
DISC_CATEGORY = "617"


def sold_listings_url(query: str) -> str:
    """eBay's sold listings for the same words the estimator searches, so a person can see
    what discs actually went for beside the asking prices the app reads."""
    return f"{EBAY_SEARCH_PAGE}?" + urlencode(
        {"_nkw": query, "_sacat": DISC_CATEGORY, "LH_Sold": "1", "LH_Complete": "1"}
    )


async def estimate_price(
    client: EbaySearch,
    *,
    film_title: str,
    format_code: str | None,
    country: str | None = UK,
    film_year: int | None = None,
) -> PriceEstimate:
    """Search eBay once and judge every listing that comes back.

    Raises whatever the client raises: :class:`~src.ebay.client.EbayNotConfigured` before
    any request, :class:`~src.ebay.client.EbayError` when eBay refuses. Callers decide what
    a failure means to them; a request answers 502, a valuation run counts it and moves on.

    ``film_year`` turns on the matcher's year rule (Batch X1); the deal scan's usual price
    passes it, so "Halloween (2018)" listings stay out of the 1978 film's median.
    """
    raw = await client.search(search_query(film_title, format_code))
    judged = []
    unusable = 0
    for summary in raw.get("itemSummaries") or []:
        listing = listing_from_summary(summary)
        if listing is None:
            unusable += 1
            continue
        judged.append(
            (
                listing,
                match(
                    listing,
                    film_title=film_title,
                    format_code=format_code,
                    country=country,
                    film_year=film_year,
                ),
            )
        )

    return summarise(
        judged,
        film_title=film_title,
        format_code=format_code,
        marketplace_id=client.marketplace_id,
        unusable=unusable,
    )
