"""The listing number in an eBay web address — Batch T8a.

A price target on one listing starts from whatever address the person copied: the app's
share sheet, a browser bar, an old ``ViewItem`` link. They all carry the listing number,
which is what Browse's ``get_item_by_legacy_id`` takes. A short link (``ebay.us/…``) does
not, and resolving it would mean following a redirect to wherever it points, so it is
refused with a message saying which address to copy instead.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

#: eBay's own sites. A listing on another country's site is still one listing number.
_EBAY_HOST = re.compile(r"(^|\.)ebay\.(co\.uk|com|ie|com\.au|ca|de|fr|it|es|nl|at|ch|be)$")
#: ``/itm/<number>`` or ``/itm/<title-slug>/<number>``.
_ITEM_PATH = re.compile(r"/itm/(?:[^/]+/)?(\d{9,15})/?$")
_NUMBER = re.compile(r"^\d{9,15}$")

NOT_A_LISTING = (
    "That is not an eBay listing address. Open the listing, copy the address from the "
    "browser's bar (it has /itm/ and a number in it), and paste that."
)


def legacy_item_id(address: str) -> str | None:
    """The listing number in an eBay listing address, or in a bare number; else ``None``."""
    text = address.strip()
    if not text:
        return None
    if _NUMBER.match(text):
        return text
    if "://" not in text:
        text = f"https://{text}"
    parts = urlsplit(text)
    host = (parts.hostname or "").lower()
    if not _EBAY_HOST.search(host):
        return None
    found = _ITEM_PATH.search(parts.path)
    if found:
        return found.group(1)
    query = parse_qs(parts.query)
    for key in ("item", "itemId", "itm"):
        for value in query.get(key, []):
            if _NUMBER.match(value):
                return value
    return None


def listing_url(legacy_id: str) -> str:
    """The listing's plain address on eBay UK, without a search's tracking fragment."""
    return f"https://www.ebay.co.uk/itm/{legacy_id}"
