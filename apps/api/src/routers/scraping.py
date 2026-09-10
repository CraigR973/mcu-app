"""The scraper framework's endpoints — roadmap §5.3 and §5.4.

**Nothing here runs automatically.** §5.5's daily job is Batch 20, and a schedule is a
hosting change this project keeps explicit (`DECISIONS.md` #60). More importantly, §5.3's
acceptance — *"each built-in scraper runs against the **live** retailer"* — is a hard stop
under `group-start.md`: live third-party runs are performed by the owner, not by an agent.

So these endpoints exist, are tested against fixtures, and are invoked by a person.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Annotated, Literal
from urllib.parse import urljoin

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from src.auth import AdminUser
from src.models.price_history import RETENTION_DAYS, ScrapeRun
from src.models.wanted import Retailer
from src.routers.movies import Database
from src.routers.notifications import push_sender
from src.schemas.wanted import (
    AggregationResponse,
    BuiltInScraperListResponse,
    BuiltInScraperResponse,
    DailyRunResponse,
    ScrapeOutcomeResponse,
    ScraperTestRequest,
    ScraperTestResponse,
    ScrapeRunListResponse,
    ScrapeRunRecordResponse,
    ScrapeRunResponse,
)
from src.services.scraping.aggregate import aggregate_old_checks
from src.services.scraping.builtins import BUILT_IN_SCRAPERS, unverified_names
from src.services.scraping.daily import failure_records, run_daily_scrape
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
                substitutedFormat=outcome.substituted_format,
                editionMatched=outcome.edition_matched,
                skipped=outcome.skipped,
                notStocked=outcome.not_stocked,
                url=outcome.url,
                reasons=outcome.reasons,
                error=outcome.error,
            )
            for outcome in result.outcomes
        ],
        succeeded=result.succeeded,
        failed=result.failed,
        skipped=result.skipped,
        notStocked=result.not_stocked,
        noResults=result.no_results,
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


def _run_record(run: ScrapeRun) -> ScrapeRunRecordResponse:
    return ScrapeRunRecordResponse(
        id=run.id,
        startedAt=run.started_at_utc,
        finishedAt=run.finished_at_utc,
        trigger="cron" if run.trigger == "cron" else "manual",
        dryRun=run.dry_run,
        attempted=run.attempted,
        notStocked=run.not_stocked,
        noResults=run.no_results,
        skipped=run.skipped,
        succeeded=run.succeeded,
        failed=run.failed,
        written=run.written,
        alertsQueued=run.alerts_queued,
        failures=[{str(k): str(v) for k, v in item.items()} for item in run.failures],
        disabledRetailers=[str(name) for name in run.disabled_retailers],
        error=run.error,
    )


@router.post("/scrapers/daily", response_model=DailyRunResponse)
async def run_daily(
    _user: AdminUser,
    db: Database,
    dry_run: Annotated[bool, Query(alias="dryRun")] = False,
    trigger: Annotated[Literal["cron", "manual"], Query()] = "manual",
    retention_days: Annotated[int, Query(alias="retentionDays", ge=1, le=3650)] = RETENTION_DAYS,
) -> DailyRunResponse:
    """§5.5's nightly pass — **the endpoint a Railway cron calls.**

    Scrape, alert on anything that has just fallen to or below its `max_price`, deliver
    what is queued, then roll up whatever is now older than `retentionDays`.

    **`dryRun` defaults to `false` here, unlike `/scrapers/run`.** That endpoint is a tool
    a person points at live shops and its safe default is to write nothing; this one is a
    scheduled job whose entire purpose is to write, and a cron that quietly did nothing
    every night would be the worst possible failure — indistinguishable from working.

    There is no in-process schedule behind it (`DECISIONS.md` #60): one container's timer
    becomes two runs the moment the service scales, against real shops.
    """
    async with push_sender() as sender:
        summary = await run_daily_scrape(
            db,
            sender=sender,
            trigger=trigger,
            dry_run=dry_run,
            retention_days=retention_days,
        )
    await db.commit()

    result = summary.scrape
    return DailyRunResponse(
        runId=uuid.UUID(summary.run_id),
        written=result.written,
        attempted=sum(1 for o in result.outcomes if not o.skipped and not o.not_stocked),
        notStocked=result.not_stocked,
        noResults=result.no_results,
        skipped=result.skipped,
        succeeded=result.succeeded,
        failed=result.failed,
        alertsQueued=summary.alerts_queued,
        pushesSent=summary.pushes_sent,
        disabledRetailers=list(result.disabled),
        failures=failure_records(result),
        aggregation=(
            AggregationResponse(
                daysAggregated=summary.aggregation.days_aggregated,
                rowsWritten=summary.aggregation.rows_written,
                rowsMerged=summary.aggregation.rows_merged,
                rawRowsRemoved=summary.aggregation.raw_rows_removed,
            )
            if summary.aggregation is not None
            else None
        ),
        dryRun=dry_run,
    )


@router.get("/scrapers/runs", response_model=ScrapeRunListResponse)
async def list_scrape_runs(
    _user: AdminUser,
    db: Database,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ScrapeRunListResponse:
    """Recent runs, newest first — how §5.5 is checked the morning after.

    Readable rather than merely logged, because on 2026-09-09 a scraper "test" displayed
    results while saving nothing and there was no way to tell afterwards.
    """
    rows = list(
        (await db.execute(select(ScrapeRun).order_by(ScrapeRun.started_at_utc.desc()).limit(limit)))
        .scalars()
        .all()
    )
    total = (await db.execute(select(func.count()).select_from(ScrapeRun))).scalar_one()
    return ScrapeRunListResponse(items=[_run_record(row) for row in rows], total=total)


@router.post("/scrapers/aggregate", response_model=AggregationResponse)
async def aggregate_price_history(
    _user: AdminUser,
    db: Database,
    older_than_days: Annotated[int, Query(alias="olderThanDays", ge=1, le=3650)] = RETENTION_DAYS,
) -> AggregationResponse:
    """§5.8's roll-up on its own, without a scrape.

    `olderThanDays` is what makes the acceptance — *"after backdating test data, rows > 90
    days are aggregated and raw rows removed"* — checkable without waiting a quarter or
    trusting a fixture's idea of what four months ago was.
    """
    result = await aggregate_old_checks(db, older_than_days=older_than_days)
    await db.commit()
    return AggregationResponse(
        daysAggregated=result.days_aggregated,
        rowsWritten=result.rows_written,
        rowsMerged=result.rows_merged,
        rawRowsRemoved=result.raw_rows_removed,
    )
