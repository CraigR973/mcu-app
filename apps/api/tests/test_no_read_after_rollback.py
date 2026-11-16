"""No ORM attribute is read after a rollback inside an ``except`` (AG1, CR49-01).

A rollback expires every row the session holds, and under async SQLAlchemy reading an
expired attribute needs the database from a place that cannot await it: it raises
``MissingGreenlet``. The first error is lost, and whatever the handler meant to do next
(record the failure, carry on to the next person) never happens. Wave 1 found it at the
identify site (CR43-02, fixed in X9); wave 2 found it again in the weekly Letterboxd sync,
where it stopped the whole 08:00 job (CR49-01). This guard stops a third.

**The rule, read from the source of every module under ``src``:** in an ``except`` block,
after the statement that calls ``.rollback()``, an attribute may be read only from

- the session the rollback was called on, the caught exception, or an imported name;
- a name assigned again after the rollback (a row fetched afresh by id, as most runners do);
- a name in :data:`NOT_ORM`, each a plain object the rollback cannot expire, with the reason.

Anything else fails here. Take the value before the ``try``, or fetch the row again by id.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

#: Names read after a rollback that are not rows, by module. Each says what it is.
NOT_ORM: dict[str, dict[str, str]] = {
    "services/identify/apply.py": {"item": "a plan Item, a dataclass"},
    "services/identify/series_pass.py": {"proposal": "a series Proposal, a dataclass"},
    "services/reviews/batch.py": {
        "want": "a reviews Want, a dataclass",
        "searcher": "the Brave searcher, counting its own calls",
    },
    "services/calendar.py": {"result": "the calendar's IngestResult, a dataclass"},
    "services/bid_trial.py": {"client": "the eBay client, counting its own calls"},
    "services/ebay_watch/runs.py": {"client": "the eBay client, counting its own calls"},
    "services/specs/backfill.py": {"searcher": "the Brave searcher, counting its own calls"},
    "services/valuation.py": {"client": "the eBay client, counting its own calls"},
}

_ALWAYS = {"log", "logger", "self", "cls"}


def _imported(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.asname or alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names |= {alias.asname or alias.name for alias in node.names}
    return names


def _rollback_on(stmt: ast.stmt) -> str | None:
    for node in ast.walk(stmt):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "rollback"
        ):
            return ast.unparse(node.func.value)
    return None


def _bound(stmt: ast.stmt) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(stmt):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
    return names


def _reads(stmt: ast.stmt) -> list[ast.Attribute]:
    """Attribute reads on a bare name: loads, and the targets of ``+=`` and its kind.

    A method called on a name (``results.append``) is not a column read and is left out.
    """
    called = {
        id(node.func)
        for node in ast.walk(stmt)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    found: list[ast.Attribute] = []
    for node in ast.walk(stmt):
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Attribute):
            found.append(node.target)
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, ast.Load)
            and id(node) not in called
        ):
            found.append(node)
    return [node for node in found if isinstance(node.value, ast.Name)]


def offences(source: str, module: str, *, exempt: bool = True) -> list[str]:
    tree = ast.parse(source)
    imported = _imported(tree)
    allowed = NOT_ORM.get(module, {}) if exempt else {}
    found: list[str] = []
    for handler in ast.walk(tree):
        if not isinstance(handler, ast.ExceptHandler):
            continue
        session: str | None = None
        fresh: set[str] = set()
        for stmt in handler.body:
            if session is None:
                # Only the statements after the one holding the rollback count.
                session = _rollback_on(stmt)
                continue
            for read in _reads(stmt):
                assert isinstance(read.value, ast.Name)
                name = read.value.id
                if (
                    name in {session, handler.name}
                    or name in imported
                    or name in _ALWAYS
                    or name in fresh
                    or name in allowed
                ):
                    continue
                found.append(f"{module}:{read.lineno}: {ast.unparse(read)}")
            fresh |= _bound(stmt)
    return found


def test_no_orm_attribute_is_read_after_a_rollback_in_an_except() -> None:
    found: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        module = path.relative_to(SRC).as_posix()
        found += offences(path.read_text(), module)
    assert found == [], (
        "An attribute is read after a rollback inside an except (AG1, CR49-01). Take the "
        "value before the try, fetch the row again by id, or, if it is not a row, add it to "
        "NOT_ORM with what it is:\n" + "\n".join(found)
    )


def test_every_not_orm_entry_is_still_read_after_a_rollback() -> None:
    """A stale exemption is a hole: each entry must still be needed where it is listed."""
    for module, names in NOT_ORM.items():
        unexempt = offences((SRC / module).read_text(), module, exempt=False)
        read = {line.rsplit(": ", 1)[1].split(".")[0] for line in unexempt}
        assert set(names) <= read, f"{module}: {sorted(set(names) - read)} no longer needed"


def test_the_guard_catches_the_letterboxd_bug_it_was_written_for() -> None:
    """CR49-01's own shape, as it stood before AG1, is refused."""
    before = """
async def sync_due(db, people):
    for person in people:
        try:
            await sync(db, person)
        except Exception:
            await db.rollback()
            log.warning("failed", user=str(person.id))
"""
    assert offences(before, "services/letterboxd/sync.py") == [
        "services/letterboxd/sync.py:8: person.id"
    ]


def test_the_guard_allows_a_row_fetched_again_by_id() -> None:
    after = """
async def run_all(db, run_id, items):
    for item in items:
        try:
            await one(db, item)
        except Exception as exc:
            await db.rollback()
            run = await db.get(Run, run_id)
            run.failed += 1
            run.last_error = str(exc)
"""
    assert offences(after, "services/example.py") == []
