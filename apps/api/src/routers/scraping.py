"""The scraper framework's endpoints — roadmap §5.3 and §5.4.

**Nothing here runs automatically.** §5.5's daily job is Batch 20, and a schedule is a
hosting change this project keeps explicit (`DECISIONS.md` #60). More importantly, §5.3's
acceptance — *"each built-in scraper runs against the **live** retailer"* — is a hard stop
under `group-start.md`: live third-party runs are performed by the owner, not by an agent.

So these endpoints exist, are tested against fixtures, and are invoked by a person.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Annotated
from urllib.parse import urljoin

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from src.auth import AdminUser
from src.models.wanted import Retailer
from src.routers.movies import Database
from src.schemas.wanted import (
    BuiltInScraperListResponse,
    BuiltInScraperResponse,
    ScrapeOutcomeResponse,
    ScraperTestRequest,
    ScraperTestResponse,
    ScrapeRunResponse,
)
from src.services.scraping.builtins import BUILT_IN_SCRAPERS, unverified_names
from src.services.scraping.extract import check_shape, extract
from src.services.scraping.fetcher import FetchError, UnsafeUrlError, fetch_page
from src.services.scraping.runner import apply_search_template, run_scrape

router = APIRouter(prefix="/api/v1", tags=["scraping"])


@router.get("/scrapers/built-in", response_model=BuiltInScraperListResponse)
async def list_built_in_scrapers(_user: AdminUser) -> BuiltInScraperListResponse:
    """Every built-in configuration, and which of them anybody has actually run.

    ``unverified`` is the four sources that cannot be scraped from here — HMV and CEX
    disallow the search routes, Amazon blocks automated access, Blu-ray.com lists
    third-party prices — reported so the settings page says so rather than implying they
    work. The ledger's risk note for this batch is that a wrong selector does not error,
    it persists a plausible wrong number.
    """
    return BuiltInScraperListResponse(
        items=[
            BuiltInScraperResponse(
                name=name,
                searchUrlTemplate=str(entry["search"]),
                scraperConfig=dict(entry["config"]),
                verified=bool(entry.get("verified", False)),
                note=entry.get("note"),
            )
            for name, entry in BUILT_IN_SCRAPERS.items()
        ],
        unverified=unverified_names(),
    )


@router.post("/scrapers/test", response_model=ScraperTestResponse)
async def test_scraper(payload: ScraperTestRequest, _user: AdminUser) -> ScraperTestResponse:
    """§5.4 — run selectors against a page and show what they matched.

    **`ok` means "this looks like a price for this film", not "the request worked".** A
    page that fetched perfectly and yielded a plausible wrong number reports `ok: false`
    with the reason, which is the whole reason §5.4 exists before a retailer is enabled.

    This is the one endpoint in the app that fetches a URL a person typed. See
    `services/scraping/fetcher.py` for why that is checked per redirect hop.
    """
    # Placeholders are filled here, never in the browser: the test tool has to build its
    # request exactly the way the runner does or it is not testing the runner.
    url = apply_search_template(payload.url, payload.expectedTitle or "", payload.preferredFormat)
    try:
        page = await fetch_page(url)
    except UnsafeUrlError as exc:
        return ScraperTestResponse(
            fetched=False,
            finalUrl=None,
            title=None,
            rawPriceText=None,
            price=None,
            currency=None,
            listingUrl=None,
            ok=False,
            reasons=[],
            error=str(exc),
        )
    except FetchError as exc:
        return ScraperTestResponse(
            fetched=False,
            finalUrl=None,
            title=None,
            rawPriceText=None,
            price=None,
            currency=None,
            listingUrl=None,
            ok=False,
            reasons=[],
            error=str(exc),
        )

    candidate = extract(
        page.html,
        payload.scraperConfig,
        expected_title=payload.expectedTitle,
        preferred_format=payload.preferredFormat,
    )
    if candidate.url:
        candidate = replace(candidate, url=urljoin(page.final_url, candidate.url))
    verdict = check_shape(
        candidate,
        expected_title=payload.expectedTitle,
        expected_currency=payload.expectedCurrency,
        retailer_host=payload.expectedHost,
    )
    return ScraperTestResponse(
        fetched=True,
        finalUrl=page.final_url,
        title=candidate.title,
        rawPriceText=candidate.raw_price_text,
        price=str(candidate.price) if candidate.price is not None else None,
        currency=candidate.currency,
        listingUrl=candidate.url,
        ok=verdict.ok,
        reasons=verdict.reasons,
        error=None,
    )


@router.post("/scrapers/run", response_model=ScrapeRunResponse, status_code=status.HTTP_200_OK)
async def run_scrapers(
    _user: AdminUser,
    db: Database,
    dry_run: Annotated[bool, Query(alias="dryRun")] = True,
) -> ScrapeRunResponse:
    """Every enabled retailer × every active wanted item. **Makes live requests.**

    ``dryRun`` defaults to **true**: this endpoint hits real shops, and the version that
    writes should be the one you ask for rather than the one you get by forgetting a
    parameter. Running it for real is §5.3's acceptance and therefore an owner action.
    """
    result = await run_scrape(db, dry_run=dry_run)
    return ScrapeRunResponse(
        outcomes=[
            ScrapeOutcomeResponse(
                retailer=outcome.retailer,
                wantedTitle=outcome.wanted_title,
                ok=outcome.ok,
                price=str(outcome.price) if outcome.price is not None else None,
                currency=outcome.currency,
                url=outcome.url,
                reasons=outcome.reasons,
                error=outcome.error,
            )
            for outcome in result.outcomes
        ],
        succeeded=result.succeeded,
        failed=result.failed,
        written=result.written,
        disabled=result.disabled,
        dryRun=dry_run,
    )


@router.post("/scrapers/apply-built-ins", response_model=BuiltInScraperListResponse)
async def apply_built_in_configs(user: AdminUser, db: Database) -> BuiltInScraperListResponse:
    """Copy the built-in selectors onto the matching seeded retailers.

    Separate from Batch 18's seeding on purpose. A seeded retailer is a name and a URL — a
    fact. Selectors are a **guess** until someone runs them, so putting them on requires a
    deliberate second action, and the response still reports every one as unverified.
    """
    rows = (await db.execute(select(Retailer).where(Retailer.deleted_at.is_(None)))).scalars().all()
    for retailer in rows:
        entry = BUILT_IN_SCRAPERS.get(retailer.name)
        if entry is None:
            continue
        # A built-in may correct an old seed URL (Arrow originally pointed at its US
        # storefront) or supply the canonical host for a supported replacement.
        if entry.get("base"):
            retailer.base_url = str(entry["base"])
        retailer.search_url_template = str(entry["search"])
        retailer.scraper_config = dict(entry["config"])
    await db.commit()
    return await list_built_in_scrapers(user)
