"""The two commands a Railway cron runs — `src/scripts/daily_scrape.py` and
`src/scripts/run_reminders.py`.

**Why these exist at all.** Both jobs were already reachable over HTTP, but both endpoints
are `AdminUser`-authed and an access token lives 24 hours, so no scheduler could call
either one. `DECISIONS.md` #119. That made §5.5's *"first overnight run completes"* an
owner action with nothing behind it to run.

What is worth asserting here is small and specific: **the exit code**, because it is the
only thing a scheduler reads, and **the defaults**, because the dangerous failure is a
cron that runs every night and quietly writes nothing. Neither needs a database.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from src.clock import utc_today
from src.scripts import daily_scrape, run_reminders
from src.services.reminders import ReminderSummary
from src.services.scraping.daily import DailyRunSummary
from src.services.scraping.runner import ScrapeOutcome, ScrapeRunResult

# ---------------------------------------------------------------------------
# daily_scrape — exit codes
# ---------------------------------------------------------------------------


def _summary(*outcomes: ScrapeOutcome) -> DailyRunSummary:
    result = ScrapeRunResult(outcomes=list(outcomes), written=sum(1 for o in outcomes if o.ok))
    return DailyRunSummary(run_id="run-1", scrape=result)


def test_a_clean_night_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code = daily_scrape.report(
        _summary(ScrapeOutcome(retailer="Zavvi", wanted_title="Cross of Iron", ok=True)),
        dry_run=False,
    )
    assert code == 0
    assert "failures:      0" in capsys.readouterr().out


def test_a_failed_retailer_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    """The property the whole file is for.

    A night where a shop broke must not look to the scheduler like a night that worked.
    """
    code = daily_scrape.report(
        _summary(
            ScrapeOutcome(retailer="Zavvi", wanted_title="Cross of Iron", ok=True),
            ScrapeOutcome(
                retailer="Arrow Video", wanted_title="Deep Red", ok=False, error="503 from origin"
            ),
        ),
        dry_run=False,
    )
    assert code == 1
    captured = capsys.readouterr()
    # Named, not just counted — §5.5 asks for "failures logged with retailer + reason".
    assert "Arrow Video" in captured.err
    assert "503 from origin" in captured.err


@pytest.mark.parametrize("flag", ["skipped", "not_stocked"])
def test_a_shop_that_does_not_carry_the_film_is_not_a_failure(flag: str) -> None:
    """Batch 20's distinction, restated where the exit code is decided.

    A boutique label not stocking a blockbuster has not broken, and a cron that exited 1
    every night because of it would train its reader to ignore the exit code.
    """
    outcome = ScrapeOutcome(retailer="101 Films", wanted_title="Sorcerer", ok=False, **{flag: True})
    assert daily_scrape.report(_summary(outcome), dry_run=False) == 0


# ---------------------------------------------------------------------------
# daily_scrape — what the cron actually asks for
# ---------------------------------------------------------------------------


def test_the_cron_writes_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """`--dry-run` is opt-in, unlike `/scrapers/run`.

    A scheduled job whose purpose is to write must not default to writing nothing: that
    failure is indistinguishable from working.
    """
    captured: dict[str, Any] = {}

    async def fake_run(**kwargs: Any) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(daily_scrape, "_run", fake_run)
    monkeypatch.setattr("sys.argv", ["daily_scrape"])

    assert daily_scrape.main() == 0
    assert captured["dry_run"] is False


def test_dry_run_is_passed_through(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_run(**kwargs: Any) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(daily_scrape, "_run", fake_run)
    monkeypatch.setattr("sys.argv", ["daily_scrape", "--dry-run"])

    assert daily_scrape.main() == 0
    assert captured["dry_run"] is True


def test_the_run_is_recorded_as_a_cron_run() -> None:
    """`trigger="cron"` is what tells the two run rows apart in `scrape_runs`.

    Asserted against the source rather than a mock, because the value is a literal in the
    one call this script makes and a mock of that call would only re-state itself.
    """
    import inspect

    source = inspect.getsource(daily_scrape._run)
    assert 'trigger="cron"' in source


def test_the_cron_waits_for_a_refusal_and_checks_its_connection() -> None:
    """Batch 20b, second half. The scheduled check takes the runner's default wait (90
    seconds), which only "Run now" in the app turns off, and checks a pooled connection
    before reusing it, because a refused night leaves it idle for minutes at a time.

    Asserted against the source, as the trigger is above: both are literals in the one
    call each, and a mock of the call would only re-state itself.
    """
    import inspect

    from src.services.scraping.daily import run_daily_scrape
    from src.services.scraping.fetcher import RETRY_AFTER_LIMIT_SECONDS

    source = inspect.getsource(daily_scrape._run)
    assert "pool_pre_ping=True" in source
    assert "retry_after_limit" not in source
    default = inspect.signature(run_daily_scrape).parameters["retry_after_limit"].default
    assert default == RETRY_AFTER_LIMIT_SECONDS == 90


def test_the_summary_says_how_many_retries_got_through(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from src.services.scraping.runner import RefusalRetry

    def refused(title: str, result: str) -> ScrapeOutcome:
        outcome = ScrapeOutcome(
            retailer="101 Films", wanted_title=title, ok=result == "got through"
        )
        outcome.refused = result == "refused again"
        outcome.retry = RefusalRetry(asked="60", waited=60.0, note="n", result=result)
        return outcome

    daily_scrape.report(
        _summary(refused("Castle Freak", "got through"), refused("Dead & Buried", "refused again")),
        dry_run=False,
    )

    out = capsys.readouterr().out
    assert "refused:       1" in out
    assert "retried:       2 after a wait, 1 got through" in out


def test_a_nonsense_retention_window_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mirrors the endpoint's `ge=1`. Zero days would roll up today's own checks."""
    monkeypatch.setattr("sys.argv", ["daily_scrape", "--retention-days", "0"])
    with pytest.raises(SystemExit) as excinfo:
        daily_scrape.main()
    assert excinfo.value.code == 2


# ---------------------------------------------------------------------------
# run_reminders
# ---------------------------------------------------------------------------


def test_a_delivered_pass_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code = run_reminders.report(
        ReminderSummary(as_of=date(2026, 9, 10), sale_events=1, queued=1),
        delivered=1,
        failed=0,
        deliver=True,
    )
    assert code == 0
    assert "delivered:       1" in capsys.readouterr().out


def test_a_failed_delivery_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    """A push that did not arrive must not hide behind the queued count above it."""
    code = run_reminders.report(
        ReminderSummary(as_of=date(2026, 9, 10), queued=3),
        delivered=1,
        failed=2,
        deliver=True,
    )
    assert code == 1
    assert "failed:          2" in capsys.readouterr().err


def test_no_deliver_says_so_rather_than_printing_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Same rule as #61's empty chart: "0 sent" and "sending was skipped" are different
    facts and must not render identically."""
    run_reminders.report(ReminderSummary(), delivered=0, failed=0, deliver=False)
    assert "(skipped)" in capsys.readouterr().out


def test_reminders_deliver_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_run(**kwargs: Any) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(run_reminders, "_run", fake_run)
    monkeypatch.setattr("sys.argv", ["run_reminders"])

    assert run_reminders.main() == 0
    assert captured["deliver"] is True
    assert captured["as_of"] is None


def test_a_future_as_of_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The endpoint's 422, as an exit code.

    Reminding somebody about a sale that has not been announced is not a feature.
    """
    tomorrow = (utc_today() + timedelta(days=1)).isoformat()
    monkeypatch.setattr("sys.argv", ["run_reminders", "--as-of", tomorrow])
    with pytest.raises(SystemExit) as excinfo:
        run_reminders.main()
    assert excinfo.value.code == 2


def test_a_past_as_of_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """How a missed night is caught up — the pass is idempotent, so re-running is safe."""
    captured: dict[str, Any] = {}

    async def fake_run(**kwargs: Any) -> int:
        captured.update(kwargs)
        return 0

    yesterday = utc_today() - timedelta(days=1)
    monkeypatch.setattr(run_reminders, "_run", fake_run)
    monkeypatch.setattr("sys.argv", ["run_reminders", "--as-of", yesterday.isoformat()])

    assert run_reminders.main() == 0
    assert captured["as_of"] == yesterday


# ---------------------------------------------------------------------------
# The seam that let the scripts exist
# ---------------------------------------------------------------------------


def test_the_router_still_exposes_the_push_transport() -> None:
    """`push_sender` moved to the service layer so a job need not import a router.

    The router re-exports it, and the tests that substitute a transport import it from
    there — so this asserts the two names are one object, not two.
    """
    from src.routers import notifications
    from src.services import push_transport

    assert notifications.push_sender is push_transport.push_sender
    assert notifications.set_push_sender is push_transport.set_push_sender


def test_neither_script_imports_a_router() -> None:
    """The point of the move. A scheduled job must not drag FastAPI and the whole route
    table into a process whose only job is to scrape some shops."""
    import inspect

    for module in (daily_scrape, run_reminders):
        source = inspect.getsource(module)
        assert "src.routers" not in source, f"{module.__name__} imports a router"
