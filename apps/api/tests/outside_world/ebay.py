"""api.ebay.com — Browse search, one listing by its number, and the OAuth token.

Built from the captured Browse fixtures (``tests/fixtures/ebay_*.json``): the shape is eBay's,
the titles and prices are the suite's. A case chooses what eBay says through the scenario file::

    {"ebay": {"searches": [{"contains": "Midnight Ferry",
                            "listings": [{"title": "...", "price": "9.99", "legacyItemId": "1"}]}],
              "items": {"168722516953": {"price": {"value": "4.50", "currency": "GBP"}}}}}

Without a scenario, a search answers a few plain disc listings for what was asked.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import httpx

HOSTS = ("api.ebay.com",)

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

#: Barcodes the suite scans, and the film each is printed on.
BARCODES = {
    "5051429700106": "Midnight Ferry",
}


def _template_summary() -> dict[str, Any]:
    payload = json.loads((_FIXTURES / "ebay_browse_jaws.json").read_text())
    summary: dict[str, Any] = payload["itemSummaries"][0]
    return summary


def _summary(listing: dict[str, Any], index: int) -> dict[str, Any]:
    item = copy.deepcopy(_template_summary())
    legacy = str(listing.get("legacyItemId") or 700000000000 + index)
    item["itemId"] = f"v1|{legacy}|0"
    item["legacyItemId"] = legacy
    item["title"] = listing["title"]
    item["price"] = {"value": str(listing.get("price", "9.99")), "currency": "GBP"}
    item["condition"] = listing.get("condition", "Very Good")
    item["conditionId"] = str(listing.get("conditionId", "4000"))
    item["buyingOptions"] = listing.get("buyingOptions", ["FIXED_PRICE"])
    item["itemWebUrl"] = f"https://www.ebay.co.uk/itm/{legacy}"
    item["itemHref"] = f"https://api.ebay.com/buy/browse/v1/item/v1%7C{legacy}%7C0"
    return item


def _listings_for(query: str, scenario: dict[str, Any]) -> list[dict[str, Any]]:
    for rule in scenario.get("ebay", {}).get("searches", []):
        if rule["contains"].lower() in query.lower():
            return list(rule["listings"])
    film = next((title for code, title in BARCODES.items() if code in query), None)
    if film:
        return [
            {"title": f"{film} Blu-ray (2009) {query} DVD Film", "price": "8.49", "legacyItemId": "610001"},
            {"title": f"{film} [Blu-ray] [2009] {query}", "price": "10.00", "legacyItemId": "610002"},
            {"title": f"{film} Blu-ray 2009 Region B {query}", "price": "7.25", "legacyItemId": "610003"},
        ]
    return [
        {"title": f"{query} Blu-ray (2010)", "price": "8.99", "legacyItemId": "620001"},
        {"title": f"{query} Blu-ray (2010) VGC", "price": "6.50", "legacyItemId": "620002"},
        {"title": f"{query} 4K UHD Blu-ray", "price": "14.00", "legacyItemId": "620003"},
    ]


def _item(legacy_id: str, scenario: dict[str, Any]) -> dict[str, Any]:
    item: dict[str, Any] = json.loads((_FIXTURES / "ebay_item_auction_with_buy_now.json").read_text())
    item.pop("note", None)
    item["legacyItemId"] = legacy_id
    item["itemId"] = f"v1|{legacy_id}|0"
    item["itemWebUrl"] = f"https://www.ebay.co.uk/itm/{legacy_id}"
    item.update(scenario.get("ebay", {}).get("items", {}).get(legacy_id, {}))
    return item


def handle(request: httpx.Request, world: Any) -> httpx.Response:
    path = request.url.path
    scenario = world.scenario()

    if path == "/identity/v1/oauth2/token":
        form = parse_qs(request.content.decode())
        grant = (form.get("grant_type") or [""])[0]
        if grant == "authorization_code":
            if (form.get("code") or [""])[0] == "declined":
                return httpx.Response(400, json={"error": "invalid_grant", "error_description": "code refused"})
            return httpx.Response(
                200,
                json={
                    "access_token": "e2e-fake-user-token",
                    "expires_in": 7200,
                    "refresh_token": "e2e-fake-refresh-token",
                    "refresh_token_expires_in": 47304000,
                    "token_type": "User Access Token",
                },
            )
        return httpx.Response(
            200,
            json={"access_token": "e2e-fake-ebay-token", "expires_in": 7200, "token_type": "Application Access Token"},
        )

    if path == "/ws/api.dll":
        call_name = request.headers.get("x-ebay-api-call-name", "")
        if call_name == "GetUser":
            body = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<GetUserResponse xmlns="urn:ebay:apis:eBLBaseComponents"><Ack>Success</Ack>'
                "<User><UserID>e2e_collector</UserID></User></GetUserResponse>"
            )
        elif call_name == "GetMyeBayBuying":
            body = (_FIXTURES / "ebay_trading_buying_doc_sample.xml").read_text()
        elif call_name == "GetMyeBaySelling":
            body = (_FIXTURES / "ebay_trading_selling_doc_sample.xml").read_text()
        else:
            world.log(kind="unknown", host=request.url.host, path=path, why=call_name)
            return httpx.Response(404)
        return httpx.Response(200, text=body, headers={"content-type": "text/xml"})

    if path == "/buy/browse/v1/item_summary/search":
        query = request.url.params.get("q", "")
        listings = _listings_for(query, scenario)
        summaries = [_summary(listing, index) for index, listing in enumerate(listings)]
        return httpx.Response(
            200,
            json={
                "href": str(request.url),
                "total": len(summaries),
                "limit": int(request.url.params.get("limit", 50)),
                "offset": 0,
                "itemSummaries": summaries,
            },
        )

    if path == "/buy/browse/v1/item/get_item_by_legacy_id":
        legacy = request.url.params.get("legacy_item_id", "")
        known = scenario.get("ebay", {}).get("items", {})
        if scenario.get("ebay", {}).get("onlyKnownItems") and legacy not in known:
            return httpx.Response(404, json={"errors": [{"errorId": 11001, "message": "not found"}]})
        return httpx.Response(200, json=_item(legacy, scenario))

    world.log(kind="unknown", host=request.url.host, path=path)
    return httpx.Response(404, json={"errors": [{"message": "not faked"}]})
