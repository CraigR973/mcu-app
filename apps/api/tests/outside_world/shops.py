"""The shops the app reads for prices (Zavvi, Arrow and the rest of the built-in list).

Every host in ``services/scraping/builtins.py`` is answered, so a scrape cannot reach a real
shop. A search page lists what the scenario says that shop has for what was asked, in the
markup the verified configs read::

    {"shops": {"www.zavvi.com": [{"match": "midnight ferry", "title": "Midnight Ferry Blu-ray",
                                   "price": "8.99"}]}}

A shop with nothing for the query answers a plain "no results" page, as a real one does.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

_BUILTINS = Path(__file__).resolve().parents[2] / "src" / "services" / "scraping" / "builtins.py"


def _shop_hosts() -> tuple[str, ...]:
    text = _BUILTINS.read_text()
    found = re.findall(r'"(?:search|url|base)":\s*"https?://([^/"]+)', text)
    # Blu-ray.com is a shop in this list and a page source elsewhere; it has its own module.
    return tuple(sorted({host for host in found if host != "www.blu-ray.com"}))


HOSTS = _shop_hosts()


def _card(title: str, price: str, path: str) -> str:
    return (
        '<div class="product-card" data-testid="product-item">'
        f'<a data-testid="product-title" href="{html.escape(path)}">{html.escape(title)}</a>'
        f'<div data-testid="product-price"><p class="text-md font-bold">£{html.escape(price)}</p></div>'
        "</div>"
    )


def handle(request: httpx.Request, world: Any) -> httpx.Response:
    host = request.url.host
    scenario = world.scenario().get("shops", {})
    query = " ".join(request.url.params.values()).lower()
    if not query and "search" in urlsplit(str(request.url)).path:
        query = request.url.path.lower()
    rules = [r for r in scenario.get(host, []) if r["match"].lower() in query]
    if not rules:
        body = "<html><body><main><p>No results found.</p></main></body></html>"
    else:
        cards = "".join(
            _card(r["title"], str(r["price"]), r.get("path", "/p/blu-ray/" + re.sub(r"\W+", "-", r["title"].lower()) + "/1/"))
            for r in rules
        )
        body = f"<html><body><main>{cards}</main></body></html>"
    return httpx.Response(200, text=body, headers={"content-type": "text/html; charset=utf-8"})
