"""One set of format names, on both sides of the wire — Batch Z1 (`DECISIONS.md` #287).

The web's ``FORMATS`` (``apps/web/src/lib/api.ts``) is what the Archive and every screen show.
The server keeps the same names for the sentences it writes itself, and this test reads the
web's list so the two cannot drift apart unnoticed.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.services.format_names import FORMAT_NAMES, format_label, formats_phrase

WEB_API = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "api.ts"


def _web_formats() -> dict[str, str]:
    source = WEB_API.read_text()
    block = re.search(r"export const FORMATS = \[(.*?)\] as const", source, re.S)
    assert block is not None, "the web's FORMATS list has moved; point this test at it"
    pairs = re.findall(r"\{\s*value:\s*'([^']+)',\s*label:\s*'([^']+)'\s*\}", block.group(1))
    assert pairs, "the web's FORMATS list could not be read"
    return dict(pairs)


def test_the_server_names_every_format_as_the_web_does() -> None:
    assert _web_formats() == FORMAT_NAMES
    assert list(_web_formats()) == list(FORMAT_NAMES)


def test_a_copy_reads_as_the_archive_lists_it() -> None:
    assert formats_phrase(["4k_uhd", "blu_ray"]) == "4K UHD + Blu-ray"
    assert formats_phrase(["download"]) == "Digital"
    assert formats_phrase([]) == ""


def test_an_unknown_code_reads_with_spaces_as_the_web_fallback_does() -> None:
    assert format_label("blu_ray_3d") == "blu ray 3d"
