"""AA10c's comparison on the live database, read-only (`services/stand_in_check.py`, #394).

    NEON_READONLY_URL=… PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 \\
        -m src.scripts.stand_in_check [--min-sales 3] [--json]

It sends the service's own two selects, rendered with their values in place, to Neon over
HTTPS with the read-only role, exactly as ``src.scripts.live_sql`` does, then judges them with
the same functions the tests drive. It writes nothing and never prints the connection string.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import Select
from sqlalchemy.engine import make_url

from src.clock import utcnow
from src.scripts.live_sql import ENV_VAR, TIMEOUT, LiveSqlError, reads_only, run_query
from src.services.stand_in_check import (
    MIN_SALES,
    Comparison,
    DealCheck,
    Errors,
    check_deals,
    compare,
    deals_from_rows,
    deals_query,
    discs_from_rows,
    discs_query,
)

_DIALECT = make_url("postgresql://").get_dialect()()


def literal_sql(statement: Select[Any]) -> str:
    """One select with its values written in, for an endpoint that takes no parameters.

    The driver's style doubles every ``%`` for its own parameter pass, which Neon's HTTPS
    endpoint does not make, so they are put back: ``LIKE '% observed sales…'`` as written.
    """
    compiled = statement.compile(dialect=_DIALECT, compile_kwargs={"literal_binds": True})
    return str(compiled).replace("%%", "%")


def _percent(value: Decimal) -> str:
    return f"{value * 100:+.1f}%"


def _errors(name: str, found: Errors | None) -> list[str]:
    if found is None:
        return [f"{name}: nothing to compare"]
    return [
        f"{name}: typical miss {abs(found.median_absolute) * 100:.1f}%, bias "
        f"{_percent(found.median)} (middle half {_percent(found.p25)} to {_percent(found.p75)}), "
        f"summed figures / summed sales {found.total_ratio}"
    ]


def report(comparison: Comparison, deals: DealCheck, *, now: datetime) -> str:
    lines = [
        f"AA10c stand-in check, {now:%d %b %Y %H:%M} UTC, discs with {comparison.min_sales}+ sales",
        f"Discs with recorded sales: {comparison.discs_with_sales} "
        f"({comparison.sales_recorded} sales)",
        f"Compared: {comparison.compared} discs ({comparison.sales_used} sales)",
        *(f"  left out, {reason}: {count}" for reason, count in comparison.excluded.items()),
        *_errors("Lower quartile of used asks, postage in", comparison.lower_quartile),
        *_errors("Today's used median, postage out", comparison.used_median),
        f"Nearer on a disc: lower quartile {comparison.lower_quartile_closer}, "
        f"used median {comparison.used_median_closer}",
        f"Keep: {comparison.keep.replace('_', ' ')}",
        f"Live eBay deals: {deals.live}; with recorded sales {deals.checkable}, of which at or "
        f"above the sales median {deals.at_or_above}; with {comparison.min_sales}+ sales "
        f"{deals.checkable_min}, at or above {deals.at_or_above_min}",
    ]
    return "\n".join(lines)


def _default(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"not JSON: {value!r}")


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    transport: httpx.BaseTransport | None = None,
    now: datetime | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Compare the stand-in and today's used median against recorded sales, "
        "on the live database, read-only (NEON_READONLY_URL)."
    )
    parser.add_argument("--min-sales", type=int, default=MIN_SALES)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    url = (environ if environ is not None else os.environ).get(ENV_VAR, "")
    if not url:
        print(
            f"{ENV_VAR} is not set. docs/mac-cloud-setup.md makes it, once, on the Mac.",
            file=sys.stderr,
        )
        return 2
    now = now or utcnow()
    statements = [literal_sql(discs_query(now)), literal_sql(deals_query(now))]
    if not all(reads_only(sql) for sql in statements):  # pragma: no cover - a select always reads
        print("Refused before sending: one statement that only reads, please.", file=sys.stderr)
        return 2
    try:
        with httpx.Client(timeout=TIMEOUT, transport=transport) as client:
            disc_rows, deal_rows = (
                run_query(sql, url=url, client=client).get("rows") or [] for sql in statements
            )
    except LiveSqlError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    comparison = compare(discs_from_rows(disc_rows), min_sales=args.min_sales)
    deals = check_deals(deals_from_rows(deal_rows), min_sales=args.min_sales)
    if args.json:
        print(
            json.dumps({"comparison": asdict(comparison), "deals": asdict(deals)}, default=_default)
        )
    else:
        print(report(comparison, deals, now=now))
    return 0


if __name__ == "__main__":
    sys.exit(main())
