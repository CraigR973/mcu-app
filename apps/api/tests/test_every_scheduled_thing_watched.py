"""Every scheduled thing is watched by the daily check (AG2, DS50-01).

At wave 2's review the daily check read four of the eight things that run on a schedule: four
cinemas went dark for five days, and a dead 08:00 job or a failed backup would have reached no
one. The fix is one rule (``heartbeat.SCHEDULED``): each scheduled thing is listed once, writes a
heartbeat with a failure figure, and the check reads every heartbeat. This guard keeps the list
whole by reading where schedules actually live:

- every Railway service with a ``cronSchedule`` in ``.railway/railway.ts``;
- every GitHub Actions workflow with a ``schedule`` trigger;

and fails on one that ``heartbeat.SCHEDULED`` does not name, or that names nothing that writes
its heartbeat. A Postgres-backed test then runs the daily check and finds each thing's row.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
import yaml
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.services import health_checks, heartbeat

REPO = Path(__file__).resolve().parents[3]
API = REPO / "apps" / "api"
RAILWAY = REPO / ".railway" / "railway.ts"
WORKFLOWS = REPO / ".github" / "workflows"


def railway_crons() -> dict[str, str]:
    """Each Railway service with a cron schedule, and the module it starts."""
    text = RAILWAY.read_text()
    found: dict[str, str] = {}
    starts = [match.start() for match in re.finditer(r"service\('", text)] + [len(text)]
    for start, end in zip(starts, starts[1:], strict=False):
        block = text[start:end]
        name = re.match(r"service\('([^']+)'", block)
        assert name is not None
        if "cronSchedule" not in block:
            continue
        module = re.search(r"startCommand:\s*'python -m ([\w.]+)'", block)
        assert module is not None, f"{name.group(1)} has a schedule and no python module"
        found[name.group(1)] = module.group(1)
    return found


def scheduled_workflows() -> list[str]:
    found = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        triggers = yaml.safe_load(path.read_text()).get(True) or {}  # YAML reads `on` as True
        if isinstance(triggers, dict) and "schedule" in triggers:
            found.append(path.name)
    return found


def constant_for(job: str) -> str:
    names = [name for name in dir(heartbeat) if name.isupper() and getattr(heartbeat, name) == job]
    assert names, f"heartbeat has no constant for {job}"
    return names[0]


def test_the_schedules_are_found() -> None:
    """The guard reads real files: five Railway crons and the backup workflow on 17 Nov."""
    assert set(railway_crons()) >= {
        "cron-scrape",
        "cron-specs",
        "cron-ebay",
        "cron-values",
        "cron-reminders",
    }
    assert "backup.yml" in scheduled_workflows()


def test_every_railway_cron_is_listed_and_beats() -> None:
    listed = {thing.schedule for thing in heartbeat.SCHEDULED}
    for service, module in railway_crons().items():
        assert f"railway:{service}" in listed, (
            f"Railway runs {service} on a schedule, and heartbeat.SCHEDULED does not list it, so "
            "the daily check cannot see it stop (AG2)."
        )
        source = (API / Path(*module.split("."))).with_suffix(".py").read_text()
        constant = constant_for(service)
        assert f"heartbeat.{constant}" in source, f"{module} never beats {service}"


def test_every_scheduled_workflow_is_listed_and_beats() -> None:
    listed = {thing.schedule for thing in heartbeat.SCHEDULED}
    for workflow in scheduled_workflows():
        assert f"workflow:{workflow}" in listed, (
            f"{workflow} runs on a schedule, and heartbeat.SCHEDULED does not list it (AG2)."
        )
        assert "src.scripts.backup beat" in (WORKFLOWS / workflow).read_text(), (
            f"{workflow} never records its run as a heartbeat"
        )
        step = next(
            step
            for step in yaml.safe_load((WORKFLOWS / workflow).read_text())["jobs"]["backup"][
                "steps"
            ]
            if "backup beat" in str(step.get("run", ""))
        )
        assert step.get("if") == "always()", "a failed run must be recorded too"


def test_every_listed_thing_has_a_home_and_a_writer() -> None:
    crons = railway_crons()
    workflows = scheduled_workflows()
    sources = {
        path: path.read_text()
        for path in (API / "src").rglob("*.py")
        if "heartbeat" in path.name or "heartbeat" in path.read_text()
    }
    for thing in heartbeat.SCHEDULED:
        kind, _, where = thing.schedule.partition(":")
        assert kind in {"railway", "workflow", "inside"}, thing.schedule
        if kind == "workflow":
            assert where in workflows, thing.schedule
        else:
            assert where in crons, thing.schedule
        constant = constant_for(thing.job)
        writers = [
            path
            for path, text in sources.items()
            if re.search(rf"\bheartbeat\.{constant}\b", text) and path.name != "health_checks.py"
        ]
        assert writers, f"nothing writes {thing.job}'s heartbeat"


def test_nothing_is_listed_twice() -> None:
    jobs = [thing.job for thing in heartbeat.SCHEDULED]
    assert len(jobs) == len(set(jobs))
    assert len(jobs) == 8, "wave 2 counted eight scheduled things; a ninth is welcome, if listed"


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


async def test_the_daily_check_has_a_row_for_every_scheduled_thing(db: AsyncSession) -> None:
    """Postgres-backed: the check's own results name each of the eight."""
    now = datetime(2030, 1, 1, 8, 0)
    keys = {key for key, _ in await health_checks.evaluate(db, now)}
    missing = [thing.key for thing in heartbeat.SCHEDULED if thing.key not in keys]
    assert missing == [], f"the daily check has no row for {missing}"


@pytest.mark.parametrize("thing", heartbeat.SCHEDULED, ids=lambda thing: thing.job)
def test_each_cadence_is_its_schedule_plus_a_margin(thing: heartbeat.Scheduled) -> None:
    assert timedelta(hours=1) < thing.cadence <= timedelta(days=17)
