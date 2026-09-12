"""Deciding whether an eBay listing is *the disc you asked for* — Batch 28, Phase 4.1.

**This module is the batch.** `DECISIONS.md` #129 measured the alternative on 310 live GB
listings: a median taken straight off a keyword search for "Blade Runner 2049 Blu-ray"
reads **£30.45** against a real plain-Blu-ray median of **£12.21** — a 149% overstatement,
confident and plausible and wrong. The median function is four lines. Everything that makes
its answer mean something is here.

**What a keyword search actually returns**, measured again on 2026-09-11 against the two
fixtures in ``tests/fixtures/ebay_browse_*.json`` (200 live GB listings each):

- the film on the format asked for — the thing we want;
- the same film on **other formats** — 4K, DVD, 3D, and combo packs of several;
- **collector editions** — FilmArena, Relite Media, Blufans, KimchiDVD, Mondo, Cinemuseum,
  The Film Vault, one-click boxes, lenticular full slips — at £150–£925;
- **different films** — "Jaws 2", "Jaws 3", "Jaws: The Revenge", "Blade Runner: Final Cut";
- **bundles** — "Blade Runner 2049 / Alien Covenant", "Jaws, Jaws 2, Jaws 3, Jaws the
  Revenge", "Lot of 4 … Movie Discs";
- **accessories** — "Blu-ray Slipcases £1.00 each", "Blade Runner 2049 4K or Blu-ray Custom
  Slipcover";
- and things that are not discs at all — art prints, audio books, a DVD player.

Each of those is a named rejection reason below, and every rejection is **reported**
rather than dropped: a filter that silently discards 90% of its input is indistinguishable
from one that is broken, which is the failure `DECISIONS.md` #122 cost ten live requests to
find.

**Why the guards are structural rather than a pile of title regexes.** #129 ends by saying
the regexes used to take its own measurement are too fragile to ship — visible in the
£368.35 outlier that survived them. So the strongest gate here is eBay's own
``leafCategoryIds`` (185 of 200 Blade Runner listings are leaf ``617``, "DVDs & Blu-rays";
the other 15 are the art prints and the DVD player), and the title work is done by
position — a contiguous run, and what follows it — not by hoping a blocklist is complete.

**What category IDs cannot do.** Leaf ``617`` is every disc format at once: DVD, Blu-ray
and 4K all sit in it. Format therefore has to come from the title, and it is
:func:`src.services.scraping.extract.primary_format` that does it — the same function the
retailer scrapers use, including its rule that the *highest* format named wins. That rule
is load-bearing here for a reason it was not written for: eBay sellers append "- DVD" to
Blu-ray listings as a keyword, so ``Blade Runner 2049 [Blu-ray] [2017] - DVD`` is a
Blu-ray and a contains-"dvd" test would file it as a DVD.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from src.services.scraping.extract import TITLE_NOISE, YEAR_PATTERN, primary_format

#: eBay UK leaf categories that hold **discs**. ``617`` is "DVDs & Blu-rays" and covers
#: every disc format; ``2312`` is the "Other Formats" sibling a handful of listings use.
#:
#: An allowlist, deliberately — the same reasoning as ``extract.MEDIA_MARKERS``. What a
#: keyword search drags in is unbounded (art prints, audio books, memorabilia, a DVD
#: player), so a blocklist would be one category behind forever.
DISC_LEAF_CATEGORY_IDS = frozenset({"617", "2312"})

#: The numeric condition codes eBay uses, and what they mean. **The only stable key**:
#: ``condition`` is a localised display string and #129 found 16 distinct values for about
#: five real conditions across three languages in a single result set.
CONDITION_LABELS: dict[str, str] = {
    "1000": "New",
    "1500": "Open box",
    "2000": "Certified refurbished",
    "2500": "Seller refurbished",
    "2750": "Like new",
    "3000": "Used",
    "4000": "Very good",
    "5000": "Good",
    "6000": "Acceptable",
    "7000": "For parts or not working",
}

#: The bucket a listing with **no** ``conditionId`` falls into. #129: "A missing condition
#: is its own bucket, never a default." Three of the 200 Blade Runner listings have none.
UNKNOWN_CONDITION_ID = "unknown"

_TOKEN = re.compile(r"[a-z0-9]+")

#: A BBFC age rating, as sellers write it beside a title: ``[15]``, ``cert 15``,
#: ``BBFC 15``, ``CERT 15UK``. **Stripped before tokenising**, because otherwise the
#: sequel guard below reads the number as a sequel and rejects the disc: "Blade Runner
#: 2049 [15] 4K UHD" is the film, not a fifteenth instalment. Measured — two listings in
#: ``ebay_browse_blade_runner_2049.json`` are lost without this.
#:
#: Removing the rating rather than exempting the numbers 12/15/18 from the sequel guard is
#: the narrower fix: it cannot accidentally admit "Ocean's 12" as "Ocean's".
_CERTIFICATE = re.compile(
    r"\[\s*(?:u|pg|12a?|15|18|r18)\s*\]|\b(?:cert|bbfc|rated)\s*(?:u|pg|12a?|15|18)\b",
    re.IGNORECASE,
)

#: A bare 1- or 2-digit number, or a roman numeral, directly after the film's title is a
#: **sequel**, not the film. "Jaws 2", "Jaws 3", "Jaws 4 The Revenge".
#:
#: This is the gap that makes a general-purpose title matcher insufficient here.
#: ``extract._normalise`` drops tokens of two characters or fewer, so "Jaws 2" and "Jaws"
#: normalise to the same single word and the retailer scrapers' ``_meaningful_extras``
#: cannot see the difference. On a retailer's own search page that rarely matters; on eBay
#: it matters constantly — a search for "Jaws" returns Jaws 2, Jaws 3 and Jaws: The Revenge
#: in the first forty results, all of them at collector-steelbook prices.
_ROMAN_SEQUELS = frozenset({"ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"})
_SEQUEL_WORDS = frozenset({"part", "chapter", "vol", "volume", "episode"})

#: A number after the title is a **quantity**, not a sequel, when one of these follows it:
#: "Blade Runner 2049 3-Discs Steelbook Edition" is one film on three discs.
#:
#: **Format words are deliberately absent, and were briefly here.** With ``blu`` and ``dvd``
#: on this list, "Jaws 3 Blu-Ray (2016)" and "Jaws 2 - DVD" read as quantities and were
#: priced as *Jaws* — nine wrong listings across the two fixtures. A number followed by a
#: format is a sequel; only a counted noun makes it a quantity.
_QUANTITY_NOUNS = frozenset({"disc", "discs", "pack", "packs", "x"})

#: Phrases that say "this listing is several films". Matched against the whitespace-joined
#: token stream, so punctuation and case cannot hide them.
_BUNDLE_PHRASES: tuple[str, ...] = (
    "lot of",
    "job lot",
    "bundle",
    "multi buy",
    "multibuy",
    "select your own",
    "choose your",
    "your choice",
    "double feature",
    "triple feature",
    "double bill",
    "mixed lot",
    "joblot",
    "movie collection",
    "film collection",
    "complete collection",
    # Not a bundle but not the film either: "ZONE 414: City of Robots (2021) Blade Runner
    # / 2049 rip-off on Blu-ray" and "Monster Shark … Jaws Rip-off" both carry the target
    # title and are both a different film entirely.
    "rip off",
    "ripoff",
    "rip offs",
)

#: Phrases that say "this listing is not the film". Kept **short and specific**: packaging
#: words on their own are not evidence — a large share of perfectly ordinary listings say
#: "with slipcover" or "with o-card" — so only the *only*/custom constructions count.
#:
#: "Poster" is deliberately absent. "Jaws: Theatrical Poster Limited Edition 4K UHD
#: Steelbook" is a disc whose artwork is a poster, and the genuine art prints are already
#: gone at the category gate (they are leaf ``360``).
_ACCESSORY_PHRASES: tuple[str, ...] = (
    "custom slipcover",
    "custom slip cover",
    "slipcover only",
    "slipcase only",
    "sleeve only",
    "case only",
    "empty case",
    "replacement case",
)

#: Words that may legitimately sit between a film's title and the first format word:
#: edition and packaging language, boutique labels, shop names, region and condition
#: seller-speak. Anything *else* there is a **subtitle**, and a subtitle means a different
#: film — "Jaws: The Revenge", "Blade Runner 2049/Final Cut", "Jaws E.T. Extra-Terrestrial
#: Close Encounters of the Third Kind".
#:
#: **Built from measurement, not imagination.** Every member was observed in that position
#: across the two captured 200-listing fixtures. ``TITLE_NOISE`` supplies the general half
#: (edition, limited, collector, anniversary, disc, region, the, and…) and is reused rather
#: than restated so the two matchers cannot drift apart.
#:
#: **The hole in this is actors' names**, which are unbounded and cannot be listed. Three
#: captured listings put one here — "Blade Runner 2049 Ryan Gosling …", "Jaws 1975 Robert
#: Shaw UK …", "Jaws starring Richard Dreyfuss …" — and are refused. That is the trade this
#: file keeps making: a stated failure rather than a wrong number, and it buys the removal
#: of ten listings that were a **different film** being priced as this one.
_WINDOW_NOISE = frozenset(
    {
        # Boutique labels and their packaging vocabulary.
        "relite",
        "media",
        "blufans",
        "kimchidvd",
        "kimchi",
        "weet",
        "filmarena",
        "arena",
        "mondo",
        "cinemuseum",
        "cma",
        "vault",
        "titans",
        "cult",
        "lenticular",
        "lenti",
        "slip",
        # Slip-case shapes, which sit exactly where a subtitle would: "Relite Media Full
        # Slip", "Filmarena Quarter Slip", "KimchiDVD Type A Full Slip", "one click".
        "one",
        "full",
        "half",
        "quarter",
        "single",
        "type",
        "editor",
        "fullslip",
        "click",
        "digibook",
        "fac",
        "hdzeta",
        "manta",
        "lab",
        # Shops.
        "hmv",
        "zavvi",
        "bestbuy",
        "amazon",
        "asda",
        "tesco",
        "sainsburys",
        "waterstones",
        # Studios and labels. A studio name sits where a subtitle would — "Jaws Universal
        # 100th Anniversary Collector's Series" — so leaving these out costs real discs.
        "universal",
        "sony",
        "paramount",
        "warner",
        "disney",
        "fox",
        "lionsgate",
        "mgm",
        "columbia",
        "criterion",
        "arrow",
        "eureka",
        "indicator",
        "studiocanal",
        "powerhouse",
        "second",
        "sight",
        "vice",
        "press",
        "neca",
        "pictures",
        "entertainment",
        "iconic",
        "moments",
        # Packaging a seller names after the title.
        "booklet",
        "hardbox",
        "amaray",
        "obi",
        "spine",
        "stock",
        "box",
        "premium",
        # German, French and Italian sellers listing on EBAY_GB. eBay converts their price
        # into GBP, so they reach a UK search even though the title is not in English.
        "neu",
        "ovp",
        "teil",
        "ohne",
        "ton",
        "gut",
        "sehr",
        "nuovo",
        "sigillato",
        "versiegelt",
        "occasion",
        "francais",
        "deutsche",
        "untertitel",
        # Audio and video vocabulary, which is about the disc rather than the film.
        "audio",
        "subtitles",
        "subs",
        "dolby",
        "atmos",
        "dts",
        "widescreen",
        "remaster",
        "remastered",
        "restoration",
        "version",
        # Seller-speak about the object rather than the film.
        "new",
        "sealed",
        "brand",
        "rare",
        "oop",
        "mint",
        "vgc",
        "used",
        "pre",
        "owned",
        "free",
        "reg",
        "ntsc",
        "pal",
        "import",
        "uk",
        "usa",
        "japan",
        "japanese",
        "german",
        "french",
        "artwork",
        "poster",
        "theatrical",
        "range",
        "retro",
        "digitally",
        "digital",
        "copy",
        "code",
        "download",
        "low",
        "number",
        "sleeve",
        "slipcase",
        "case",
        "protector",
        "card",
        "cards",
        "art",
        "cover",
        "cert",
        "bbfc",
        "starring",
        "classic",
        "original",
        "genuine",
        "complete",
        "movie",
        "film",
        "films",
        "movies",
        "series",
        "part",
        "ltd",
        "inc",
        "includes",
        "plus",
        "bonus",
        "extras",
        "value",
        "shipping",
        "post",
        "postage",
        "fast",
        "cheap",
        "very",
        "good",
        "excellent",
        "condition",
        "unwatched",
        "unopened",
        "tested",
        "working",
        "non",
        "only",
        "with",
        "from",
        "all",
        "both",
        "sci",
        "horror",
        "thriller",
        "drama",
        "action",
    }
)

#: Format vocabulary, as tokens. Reaching one of these ends the subtitle window — from the
#: format word onwards a title is describing the disc, not naming the film.
FORMAT_TOKENS = frozenset(
    {"4k", "uhd", "ultra", "hd", "hdr", "blu", "ray", "bluray", "bd", "dvd", "3d", "2d", "vhs"}
)

#: What makes a listing a **collector** edition rather than the standard retail disc. These
#: are not rejected — they are a real market and Batch 29 may want them — but they are
#: segmented apart, because mixing them into one median is most of #129's 149%.
#:
#: The list is drawn from the two captured fixtures rather than imagined: boutique labels
#: (FilmArena, Relite Media, Blufans, KimchiDVD/Weet, Mondo, Cinemuseum, The Film Vault),
#: packaging (steelbook, digibook, lenticular, full/quarter slip, one-click), and the
#: retail-exclusive language (Zavvi/HMV exclusive, limited edition, collector's edition).
_COLLECTOR_PHRASES: tuple[str, ...] = (
    "steelbook",
    "steel book",
    "filmarena",
    "film arena",
    "fac",
    "relite",
    "blufans",
    "kimchidvd",
    "kimchi",
    "weet",
    "mondo",
    "cinemuseum",
    "film vault",
    "one click",
    "oneclick",
    "lenticular",
    "lenti",
    "full slip",
    "fullslip",
    "quarter slip",
    "half slip",
    "digibook",
    "digipak",
    "premium box",
    "box set",
    "boxset",
    "collector",
    "collectors",
    "collectible",
    "limited edition",
    "limited to",
    "numbered",
    "titans of cult",
    "zavvi exclusive",
    "hmv exclusive",
    "uk exclusive",
    "exclusive edition",
    "deluxe edition",
    "anniversary edition",
    "tumblers",
)


@dataclass(frozen=True)
class Listing:
    """One eBay item summary, reduced to the fields a match decision needs.

    Built by :func:`listing_from_summary` so the Browse payload's shape is read in exactly
    one place. ``price`` is a :class:`~decimal.Decimal` because it becomes a median and
    then a suggested sale price; floats have no business anywhere near either.
    """

    item_id: str
    title: str
    price: Decimal
    currency: str
    condition_id: str
    web_url: str
    leaf_category_ids: tuple[str, ...]
    country: str | None
    #: ``SELLER_DEFINED_VARIATIONS`` when the listing is a multi-variation one. Its
    #: ``price`` is then the **cheapest** variation, which is a "from" price and not
    #: comparable with a single-item one.
    item_group_type: str | None


@dataclass(frozen=True)
class MatchVerdict:
    """Whether a listing is the disc asked for, and — when it is not — why not."""

    ok: bool
    #: ``None`` when the listing was rejected. Otherwise the format code it *is*.
    format_code: str | None = None
    #: ``"standard"`` or ``"collector"``. Meaningless when ``ok`` is false.
    edition: str = "standard"
    reason: str | None = None


def tokens(text: str) -> list[str]:
    """Lower-case alphanumeric runs, in order.

    Unlike ``extract._normalise`` this keeps short tokens and preserves order, because both
    are load-bearing: "2" is what separates *Jaws* from *Jaws 2*, and *where* the title
    appears is what separates a film from a bundle that mentions it.

    Age ratings are removed first — see :data:`_CERTIFICATE`.
    """
    return _TOKEN.findall(_CERTIFICATE.sub(" ", text).lower())


def _run_starts(haystack: list[str], needle: list[str]) -> list[int]:
    """Every index at which ``needle`` appears contiguously inside ``haystack``."""
    if not needle or len(needle) > len(haystack):
        return []
    return [
        index
        for index in range(len(haystack) - len(needle) + 1)
        if haystack[index : index + len(needle)] == needle
    ]


def _is_sequel_marker(token: str, following: str | None) -> bool:
    """Does this token, sitting right after the film's title, name a *different* film?"""
    if token in _SEQUEL_WORDS or token in _ROMAN_SEQUELS:
        return True
    if token.isdigit() and len(token) <= 2:
        # "3 discs" is a quantity; "3" alone is Jaws 3.
        return following not in _QUANTITY_NOUNS
    return False


def _subtitle_after(listing_tokens: list[str], start: int) -> str | None:
    """The first word of a **subtitle** sitting after the title, or ``None``.

    A sequel is not always a number. "Jaws: The Revenge" and "Blade Runner 2049/Final Cut"
    are different films from "Jaws" and "Blade Runner 2049", and nothing numeric or
    structural distinguishes them — only the fact that a *content word* stands between the
    title and the first word about the disc.

    So this walks the window between them, skipping years, single- and double-character
    tokens, and everything in :data:`_WINDOW_NOISE` or ``extract.TITLE_NOISE``. The first
    survivor is the subtitle. Reaching a format word first means there is no subtitle and
    the listing is the film.
    """
    for token in listing_tokens[start:]:
        if token in FORMAT_TOKENS:
            return None
        if len(token) <= 2 or YEAR_PATTERN.match(token) or token.isdigit():
            continue
        if token in _WINDOW_NOISE or token in TITLE_NOISE:
            continue
        # An ordinal — "50th", "45th" — is anniversary language, not a subtitle.
        if token[:-2].isdigit() and token[-2:] in {"st", "nd", "rd", "th"}:
            continue
        return token
    return None


def _phrase_present(joined: str, phrases: tuple[str, ...]) -> str | None:
    for phrase in phrases:
        if re.search(rf"\b{re.escape(phrase)}\b", joined):
            return phrase
    return None


def classify_edition(title: str) -> str:
    """``"collector"`` when the title carries boutique-edition language, else ``"standard"``."""
    found = _phrase_present(" ".join(tokens(title)), _COLLECTOR_PHRASES)
    return "collector" if found else "standard"


def listing_from_summary(summary: dict[str, object]) -> Listing | None:
    """Reduce one Browse ``itemSummaries`` entry, or ``None`` if it is unusable.

    ``None`` means the payload itself was not what the API documents — no title, no price,
    an unparseable amount. That is a different thing from "not the disc we want" and is
    counted separately, because a sudden rise in it is eBay changing its response rather
    than a keyword search being noisy.
    """
    title = summary.get("title")
    price = summary.get("price")
    item_id = summary.get("itemId")
    if not isinstance(title, str) or not isinstance(item_id, str) or not isinstance(price, dict):
        return None
    value = price.get("value")
    currency = price.get("currency")
    if not isinstance(value, str) or not isinstance(currency, str):
        return None
    try:
        amount = Decimal(value)
    except (ArithmeticError, ValueError):
        return None

    leaf_ids = summary.get("leafCategoryIds")
    location = summary.get("itemLocation")
    condition_id = summary.get("conditionId")
    web_url = summary.get("itemWebUrl")
    group_type = summary.get("itemGroupType")

    return Listing(
        item_id=item_id,
        title=title,
        price=amount,
        currency=currency,
        condition_id=condition_id if isinstance(condition_id, str) else UNKNOWN_CONDITION_ID,
        web_url=web_url if isinstance(web_url, str) else "",
        leaf_category_ids=(
            tuple(str(value) for value in leaf_ids) if isinstance(leaf_ids, list) else ()
        ),
        country=location.get("country") if isinstance(location, dict) else None,
        item_group_type=group_type if isinstance(group_type, str) else None,
    )


def match(
    listing: Listing,
    *,
    film_title: str,
    format_code: str | None = None,
    country: str | None = "GB",
) -> MatchVerdict:
    """Is this listing the disc we asked for?

    The gates run in two groups, and the **first** failure is the reason reported — so a
    rejection names the thing a person would have said first, not the last rule that
    happened to fire. First **is this the right product**: category, accessory, bundle,
    title, sequel, format. Then **is its price comparable**: a multi-variation "from" price,
    and an overseas seller. That order matters for exactly the listings where both are
    true — "Blade Runner 2049 4K or Blu-ray Custom Slipcover" is a multi-variation listing
    *and* a slipcover, and being a slipcover is the useful half of that.

    ``format_code`` is one of ``collection_item.FORMAT_RANK``; ``None`` accepts any disc
    format and lets the caller segment on what comes back. ``country`` defaults to ``GB``:
    the criterion asks for a *UK* median, eBay GB converts an overseas seller's price into
    GBP without saying what the import duty will be, and 52 of the 200 Blade Runner
    listings are shipping from Japan, Canada, the US, Germany or Australia.
    """
    if not listing.leaf_category_ids:
        return MatchVerdict(ok=False, reason="no category on the listing")
    if not set(listing.leaf_category_ids) & DISC_LEAF_CATEGORY_IDS:
        return MatchVerdict(
            ok=False,
            reason=f"category {'/'.join(listing.leaf_category_ids)} is not a disc category",
        )

    listing_tokens = tokens(listing.title)
    joined = " ".join(listing_tokens)

    accessory = _phrase_present(joined, _ACCESSORY_PHRASES)
    if accessory:
        return MatchVerdict(ok=False, reason=f"accessory, not the film ({accessory!r})")

    bundle = _phrase_present(joined, _BUNDLE_PHRASES)
    if bundle:
        return MatchVerdict(ok=False, reason=f"bundle of several films ({bundle!r})")

    wanted = tokens(film_title)
    if not wanted:
        return MatchVerdict(ok=False, reason="no film title to match against")
    starts = _run_starts(listing_tokens, wanted)
    if not starts:
        return MatchVerdict(ok=False, reason=f"title does not contain {film_title!r}")

    # A title that names the film more than once is naming several of them: "Jaws, Jaws 2,
    # Jaws 3, Jaws the Revenge". So is one that repeats the series name before the number:
    # "Blade Runner: Final Cut (1982) Blade Runner 2049 (2017)".
    series = wanted[:-1] if len(wanted) > 1 and wanted[-1].isdigit() else wanted
    if len(_run_starts(listing_tokens, series)) > 1:
        return MatchVerdict(ok=False, reason="title names the film more than once; a bundle")

    for start in starts:
        after = start + len(wanted)
        next_token = listing_tokens[after] if after < len(listing_tokens) else None
        following = listing_tokens[after + 1] if after + 1 < len(listing_tokens) else None
        if next_token is not None and _is_sequel_marker(next_token, following):
            return MatchVerdict(
                ok=False, reason=f"{film_title!r} followed by {next_token!r} is a different film"
            )
        subtitle = _subtitle_after(listing_tokens, after)
        if subtitle is not None:
            return MatchVerdict(
                ok=False,
                reason=f"{film_title!r} followed by the subtitle {subtitle!r} is a different film",
            )

    found_format = primary_format(listing.title)
    if found_format is None:
        return MatchVerdict(ok=False, reason="the title names no disc format")
    if format_code and found_format != format_code:
        return MatchVerdict(ok=False, reason=f"is {found_format}, not {format_code}")

    # It is the right product. Is its price comparable with the others?
    if listing.item_group_type == "SELLER_DEFINED_VARIATIONS":
        # The price shown for a multi-variation listing is its cheapest variation — a
        # "from" price. Averaging it with single-item prices understates the median for
        # exactly the reason collector editions overstate it.
        return MatchVerdict(ok=False, reason="multi-variation listing; price is a 'from' price")

    if country and listing.country and listing.country != country:
        return MatchVerdict(ok=False, reason=f"ships from {listing.country}, not {country}")

    return MatchVerdict(ok=True, format_code=found_format, edition=classify_edition(listing.title))
