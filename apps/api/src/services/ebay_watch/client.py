"""What price targets and the deal scan need from eBay — Batch T8a.

:class:`~src.ebay.client.EbayClient` is one. Tests pass a scripted one.
"""

from __future__ import annotations

from typing import Any, Protocol


class WatchClient(Protocol):
    """Browse search, one listing by number, and a count of every call made."""

    search_calls: int

    @property
    def marketplace_id(self) -> str: ...

    @property
    def attempts_per_search(self) -> int: ...

    async def search(
        self,
        query: str,
        *,
        limit: int = ...,
        category_ids: str | None = None,
        sort: str | None = None,
        filter: str | None = None,  # noqa: A002 - Browse's own parameter name
        offset: int = 0,
    ) -> dict[str, Any]: ...

    async def get_item_by_legacy_id(self, legacy_item_id: str) -> dict[str, Any] | None: ...
