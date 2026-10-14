"""A copy of the database outside Neon, and the restore that proves it — Batch X4 (DS44-03, #257).

Neon's free plan restores only within six hours and keeps no scheduled backups, so before X4
a mistake noticed the next morning could not be undone. A weekly GitHub Actions run now
reads every table through ``mcu_backup``, a role that can read no credential, and keeps the
copy encrypted outside Neon (``.github/workflows/backup.yml``). Once a month the same run
restores the copy into a throwaway Postgres and compares row counts. The runbook is
``docs/restore-runbook.md``.

**What a copy is.** One CSV per table and a manifest (the Alembic revision, and each table's
columns and row count), taken in one read-only snapshot. Data only: the schema is the code's,
rebuilt by ``alembic upgrade <revision>`` before the data is loaded. ``pg_dump`` cannot take a
table without its credential column, which is why the copy is not a ``pg_dump``.

**What a copy never holds.** The tables in :data:`CREDENTIAL_TABLES` and the columns in
:data:`CREDENTIAL_COLUMNS`. The role is not granted them (migration 053), and the dump would
refuse to run if it were: it checks the catalogue, never by selecting them. So a restore signs
both people out, asks each phone for push again, issues new calendar-feed and movie-night
links, needs eBay connected again, and needs each person's PIN set with ``set_pin``.

**A table nobody granted fails the run.** A new table's migration grants it to
``mcu_backup`` as it does to ``mcu_readonly`` (``AGENTS.md``); one it forgot is a table the
copy would silently lack, so the dump stops and names it instead.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

#: The role the weekly run reads through. Made once by hand with its password (14 Oct, #268).
BACKUP_ROLE = "mcu_backup"

#: Tables that hold nothing a restore could use without the credential in them. Never read.
#: The same set ``mcu_readonly`` was refused on 1 Oct (``docs/mac-cloud-setup.md``), and the
#: eBay sign-in tables T8b added since.
CREDENTIAL_TABLES = frozenset(
    {
        "calendar_feed_tokens",
        "ebay_accounts",
        "ebay_connect_states",
        "push_subscriptions",
        "rate_limit_counters",
        "refresh_tokens",
    }
)

#: Credential columns in otherwise ordinary tables: the row is copied without them.
CREDENTIAL_COLUMNS: Mapping[str, frozenset[str]] = {
    "profiles": frozenset({"pin_hash"}),
    "movie_night_sessions": frozenset({"invite_token"}),
}

#: What a restore puts in a withheld column that may not be empty. A movie night's invite
#: link is 256 random bits, new, so the old links stop working (#83's floor is 128).
RESTORE_FILLS: Mapping[tuple[str, str], str] = {
    ("movie_night_sessions", "invite_token"): (
        "replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '')"
    ),
}

#: Alembic's own table: the schema, not data. The manifest records its revision instead.
SCHEMA_TABLES = frozenset({"alembic_version"})

MANIFEST = "manifest.json"
FORMAT = 1


class BackupPolicyError(Exception):
    """The role reads something it must not, or misses something it must."""


class Cursor(Protocol):
    def execute(self, query: str, vars: Any = ...) -> Any: ...
    def fetchall(self) -> list[tuple[Any, ...]]: ...
    def fetchone(self) -> tuple[Any, ...] | None: ...
    def copy_expert(self, sql: str, file: Any) -> None: ...


@dataclass(frozen=True)
class Column:
    name: str
    readable: bool


@dataclass(frozen=True)
class TablePlan:
    """One table the copy takes, and the columns it takes."""

    name: str
    columns: tuple[str, ...]
    withheld: tuple[str, ...] = ()


@dataclass
class Manifest:
    revision: str
    taken_utc: str
    tables: dict[str, dict[str, Any]] = field(default_factory=dict)
    withheld_tables: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "format": FORMAT,
                "revision": self.revision,
                "takenUtc": self.taken_utc,
                "tables": self.tables,
                "withheldTables": self.withheld_tables,
            },
            indent=2,
            sort_keys=True,
        )

    @classmethod
    def read(cls, directory: Path) -> Manifest:
        raw = json.loads((directory / MANIFEST).read_text(encoding="utf-8"))
        if raw.get("format") != FORMAT:
            raise BackupPolicyError(f"manifest format {raw.get('format')!r}, expected {FORMAT}")
        return cls(
            revision=raw["revision"],
            taken_utc=raw["takenUtc"],
            tables=raw["tables"],
            withheld_tables=raw["withheldTables"],
        )

    def counts(self) -> dict[str, int]:
        return {name: int(table["rows"]) for name, table in self.tables.items()}


# ---------------------------------------------------------------------------
# What the role may read
# ---------------------------------------------------------------------------


def classify(catalogue: Mapping[str, Sequence[Column]]) -> list[TablePlan]:
    """The tables to copy, from what the role can read; or why the run must stop.

    Every problem is collected before raising, so one run names all of them. A credential the
    role *can* read is a problem even though the copy would skip it: the role is meant to be
    unable to, and the catalogue is how that is proved.
    """
    problems: list[str] = []
    plans: list[TablePlan] = []
    for name in sorted(catalogue):
        columns = catalogue[name]
        if name in SCHEMA_TABLES:
            continue
        if name in CREDENTIAL_TABLES:
            readable = [column.name for column in columns if column.readable]
            if readable:
                problems.append(f"{BACKUP_ROLE} can read credential table {name}; revoke it")
            continue
        secret = CREDENTIAL_COLUMNS.get(name, frozenset())
        taken: list[str] = []
        withheld: list[str] = []
        for column in columns:
            if column.name in secret:
                if column.readable:
                    problems.append(
                        f"{BACKUP_ROLE} can read credential column {name}.{column.name}; revoke it"
                    )
                withheld.append(column.name)
            elif column.readable:
                taken.append(column.name)
            else:
                problems.append(
                    f"{name}.{column.name} is not granted to {BACKUP_ROLE}: grant it in its "
                    "migration, or list it in CREDENTIAL_COLUMNS if it holds a credential"
                )
        plans.append(TablePlan(name, tuple(taken), tuple(withheld)))
    for name in sorted((set(CREDENTIAL_TABLES) | set(CREDENTIAL_COLUMNS)) - set(catalogue)):
        problems.append(f"the policy names {name}, which no longer exists; update it")
    for name, secret in CREDENTIAL_COLUMNS.items():
        present = {column.name for column in catalogue.get(name, ())}
        for missing in sorted(secret - present):
            if name in catalogue:
                problems.append(f"the policy names {name}.{missing}, which no longer exists")
    if problems:
        raise BackupPolicyError("; ".join(problems))
    return plans


def read_catalogue(cur: Cursor, role: str) -> dict[str, list[Column]]:
    """Each public table's ordinary columns, and whether ``role`` may read each one."""
    cur.execute(
        """
        SELECT c.relname, a.attname, has_column_privilege(%s, c.oid, a.attnum, 'SELECT')
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
          AND a.attnum > 0 AND NOT a.attisdropped AND a.attgenerated = ''
        ORDER BY c.relname, a.attnum
        """,
        (role,),
    )
    catalogue: dict[str, list[Column]] = {}
    for table, column, readable in cur.fetchall():
        catalogue.setdefault(table, []).append(Column(column, bool(readable)))
    return catalogue


# ---------------------------------------------------------------------------
# The copy
# ---------------------------------------------------------------------------


def _ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _columns(names: Iterable[str]) -> str:
    return ", ".join(_ident(name) for name in names)


def dump(cur: Cursor, directory: Path, *, role: str, now: datetime | None = None) -> Manifest:
    """Copy every table the policy allows into ``directory``, in the cursor's transaction.

    The caller opens it read-only at REPEATABLE READ, so every table and count is the same
    moment's.
    """
    plans = classify(read_catalogue(cur, role))
    cur.execute("SELECT version_num FROM alembic_version")
    row = cur.fetchone()
    if row is None:
        raise BackupPolicyError("alembic_version is empty; the database has no revision")
    manifest = Manifest(
        revision=str(row[0]),
        taken_utc=(now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        withheld_tables=sorted(CREDENTIAL_TABLES),
    )
    data = directory / "data"
    data.mkdir(parents=True, exist_ok=True)
    for plan in plans:
        cur.execute(f"SELECT count(*) FROM {_ident(plan.name)}")
        counted = cur.fetchone()
        rows = int(counted[0]) if counted else 0
        with (data / f"{plan.name}.csv").open("w", encoding="utf-8", newline="") as out:
            cur.copy_expert(
                f"COPY (SELECT {_columns(plan.columns)} FROM {_ident(plan.name)}) "
                "TO STDOUT WITH (FORMAT csv, HEADER true)",
                out,
            )
        manifest.tables[plan.name] = {
            "rows": rows,
            "columns": list(plan.columns),
            "withheld": list(plan.withheld),
        }
    (directory / MANIFEST).write_text(manifest.to_json() + "\n", encoding="utf-8")
    return manifest


# ---------------------------------------------------------------------------
# The restore
# ---------------------------------------------------------------------------


def load_order(tables: Iterable[str], links: Iterable[tuple[str, str]]) -> list[str]:
    """Parents before children, by foreign key; alphabetical where it does not matter.

    ``links`` are ``(child, parent)`` pairs. A table that refers to itself is fine (a COPY
    checks its foreign keys when the statement ends); two that refer to each other cannot be
    loaded one at a time and stop the restore.
    """
    names = sorted(set(tables))
    parents: dict[str, set[str]] = {name: set() for name in names}
    for child, parent in links:
        if child in parents and parent in parents and child != parent:
            parents[child].add(parent)
    ordered: list[str] = []
    done: set[str] = set()
    while len(ordered) < len(names):
        ready = [name for name in names if name not in done and parents[name] <= done]
        if not ready:
            stuck = sorted(name for name in names if name not in done)
            raise BackupPolicyError(f"foreign keys form a cycle among {', '.join(stuck)}")
        for name in ready:
            ordered.append(name)
            done.add(name)
    return ordered


def foreign_keys(cur: Cursor) -> list[tuple[str, str]]:
    cur.execute(
        """
        SELECT child.relname, parent.relname
        FROM pg_constraint k
        JOIN pg_class child ON child.oid = k.conrelid
        JOIN pg_class parent ON parent.oid = k.confrelid
        JOIN pg_namespace n ON n.oid = child.relnamespace
        WHERE k.contype = 'f' AND n.nspname = 'public'
        """
    )
    return [(str(child), str(parent)) for child, parent in cur.fetchall()]


def compare(expected: Mapping[str, int], found: Mapping[str, int]) -> list[str]:
    """Every table whose restored rows differ from the manifest's, and any missing."""
    differences = []
    for name in sorted(set(expected) | set(found)):
        if name not in found:
            differences.append(f"{name}: in the copy, not restored")
        elif name not in expected:
            differences.append(f"{name}: restored, not in the copy")
        elif expected[name] != found[name]:
            differences.append(f"{name}: {expected[name]} in the copy, {found[name]} restored")
    return differences


def restore(cur: Cursor, directory: Path) -> list[str]:
    """Load a copy into a database already migrated to its revision; the differences.

    Rows a migration seeded are cleared first, so what is loaded is exactly the copy. Each
    table's own triggers are off while it loads (the derived fields are in the copy already),
    and its foreign keys are still checked. Sequences resume after the highest id loaded.
    """
    manifest = Manifest.read(directory)
    cur.execute("SELECT version_num FROM alembic_version")
    row = cur.fetchone()
    if row is None or row[0] != manifest.revision:
        found = row[0] if row else None
        raise BackupPolicyError(f"target is at {found!r}; migrate it to {manifest.revision} first")
    order = load_order(manifest.tables, foreign_keys(cur))
    everything = sorted(
        set(manifest.tables) | {name for name in CREDENTIAL_TABLES if _exists(cur, name)}
    )
    cur.execute(f"TRUNCATE {_columns(everything)} RESTART IDENTITY CASCADE")
    for name in order:
        table = manifest.tables[name]
        fills = [(column, expr) for (t, column), expr in RESTORE_FILLS.items() if t == name]
        for column, expr in fills:
            cur.execute(
                f"ALTER TABLE {_ident(name)} ALTER COLUMN {_ident(column)} SET DEFAULT {expr}"
            )
        cur.execute(f"ALTER TABLE {_ident(name)} DISABLE TRIGGER USER")
        with (directory / "data" / f"{name}.csv").open(encoding="utf-8", newline="") as source:
            cur.copy_expert(
                f"COPY {_ident(name)} ({_columns(table['columns'])}) "
                "FROM STDIN WITH (FORMAT csv, HEADER true)",
                source,
            )
        cur.execute(f"ALTER TABLE {_ident(name)} ENABLE TRIGGER USER")
        for column, _expr in fills:
            cur.execute(f"ALTER TABLE {_ident(name)} ALTER COLUMN {_ident(column)} DROP DEFAULT")
    _resume_sequences(cur)
    found = {}
    for name in manifest.tables:
        cur.execute(f"SELECT count(*) FROM {_ident(name)}")
        counted = cur.fetchone()
        found[name] = int(counted[0]) if counted else 0
    return compare(manifest.counts(), found)


def _exists(cur: Cursor, name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{name}",))
    row = cur.fetchone()
    return bool(row and row[0])


def _resume_sequences(cur: Cursor) -> None:
    cur.execute(
        """
        SELECT s.relname, t.relname, a.attname
        FROM pg_class s
        JOIN pg_namespace n ON n.oid = s.relnamespace
        JOIN pg_depend d ON d.objid = s.oid AND d.deptype = 'a'
        JOIN pg_class t ON t.oid = d.refobjid
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
        WHERE s.relkind = 'S' AND n.nspname = 'public'
        """
    )
    for sequence, table, column in cur.fetchall():
        cur.execute(
            f"SELECT setval(%s, COALESCE((SELECT max({_ident(column)}) "
            f"FROM {_ident(table)}), 0) + 1, false)",
            (f"public.{sequence}",),
        )


def summary(manifest: Manifest) -> str:
    rows = sum(int(table["rows"]) for table in manifest.tables.values())
    withheld = sorted(
        f"{name}.{column}"
        for name, table in manifest.tables.items()
        for column in table["withheld"]
    )
    return (
        f"revision {manifest.revision}: {len(manifest.tables)} tables, {rows} rows; "
        f"withheld {len(manifest.withheld_tables)} tables and {', '.join(withheld) or 'no columns'}"
    )
