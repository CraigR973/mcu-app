"""What a stored format code is called in a sentence — Batch Z1 (`DECISIONS.md` #287).

The database stores ``blu_ray``; a person reads "Blu-ray". The web app's ``formatLabel``
(``apps/web/src/lib/api.ts``, ``FORMATS``) is the one formatter the Archive and every screen
use. A sentence the server writes itself (the barcode screen's evidence, the Trash's
sublabel, a price-alert push) has no web step to pass through, so the same labels live here
too, and ``test_format_names.py`` reads the web's list and fails if the two ever differ.

Not for search terms or chart legends: eBay's "4K UHD Blu-ray", the Formats chart's
"Downloads" and the identify plan's short "4K" say something different on purpose.
"""

from __future__ import annotations

from collections.abc import Iterable

#: The web's ``FORMATS``, in the same order.
FORMAT_NAMES: dict[str, str] = {
    "4k_uhd": "4K UHD",
    "blu_ray": "Blu-ray",
    "dvd": "DVD",
    "download": "Digital",
}


def format_label(code: str) -> str:
    """One format's name; an unknown code reads with spaces, as the web's fallback does."""
    return FORMAT_NAMES.get(code, code.replace("_", " "))


def formats_phrase(codes: Iterable[str]) -> str:
    """A copy's formats as the Archive lists them: "4K UHD + Blu-ray". Empty for none."""
    return " + ".join(format_label(code) for code in codes)
