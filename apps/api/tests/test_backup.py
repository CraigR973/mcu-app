"""The weekly copy's rules, without a database — Batch X4 (DS44-03, #257).

**What this proves:** which tables and columns the copy takes and which it withholds; that it
stops, naming the problem, when the role can read a credential, misses a column it should
read, or the policy names something gone; the order a restore loads tables in; and how
restored counts are compared with the manifest. The copy and restore themselves, against
Postgres, are ``test_backup_restore.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.scripts.backup import run_restore
from src.services.backup import (
    CREDENTIAL_COLUMNS,
    CREDENTIAL_TABLES,
    BackupPolicyError,
    Column,
    Manifest,
    classify,
    compare,
    load_order,
)


def _catalogue(**overrides: list[Column]) -> dict[str, list[Column]]:
    """Every table the policy names, withheld as it should be, plus two ordinary ones."""
    catalogue: dict[str, list[Column]] = {
        name: [Column("id", False), Column("token_hash", False)] for name in CREDENTIAL_TABLES
    }
    catalogue["profiles"] = [
        Column("id", True),
        Column("display_name", True),
        Column("pin_hash", False),
    ]
    catalogue["movie_night_sessions"] = [Column("id", True), Column("invite_token", False)]
    catalogue["movies"] = [Column("id", True), Column("title", True)]
    catalogue["alembic_version"] = [Column("version_num", True)]
    catalogue.update(overrides)
    return catalogue


def test_ordinary_tables_are_taken_whole_and_credentials_withheld() -> None:
    plans = {plan.name: plan for plan in classify(_catalogue())}

    assert set(plans) == {"movie_night_sessions", "movies", "profiles"}
    assert plans["movies"].columns == ("id", "title")
    assert (plans["profiles"].columns, plans["profiles"].withheld) == (
        ("id", "display_name"),
        ("pin_hash",),
    )
    assert plans["movie_night_sessions"].withheld == ("invite_token",)
    assert not set(plans) & CREDENTIAL_TABLES
    assert "alembic_version" not in plans


def test_a_role_that_can_read_a_credential_table_stops_the_copy() -> None:
    with pytest.raises(BackupPolicyError, match="can read credential table refresh_tokens"):
        classify(_catalogue(refresh_tokens=[Column("id", True), Column("token_hash", False)]))


def test_a_role_that_can_read_a_pin_hash_stops_the_copy() -> None:
    profiles = [Column("id", True), Column("display_name", True), Column("pin_hash", True)]
    with pytest.raises(BackupPolicyError, match=r"credential column profiles\.pin_hash"):
        classify(_catalogue(profiles=profiles))


def test_a_column_nobody_granted_stops_the_copy_and_says_how_to_fix_it() -> None:
    """A later migration that forgets the backup role would otherwise leave data uncopied."""
    movies = [Column("id", True), Column("title", True), Column("new_thing", False)]
    with pytest.raises(BackupPolicyError) as raised:
        classify(_catalogue(movies=movies))
    assert "movies.new_thing is not granted to mcu_backup" in str(raised.value)
    assert "grant it in its migration" in str(raised.value)


def test_a_table_nobody_granted_stops_the_copy() -> None:
    with pytest.raises(BackupPolicyError, match="job_heartbeats.id is not granted"):
        classify(_catalogue(job_heartbeats=[Column("id", False)]))


def test_every_problem_is_named_at_once() -> None:
    catalogue = _catalogue(
        refresh_tokens=[Column("id", True)], movies=[Column("id", True), Column("x", False)]
    )
    with pytest.raises(BackupPolicyError) as raised:
        classify(catalogue)
    assert "refresh_tokens" in str(raised.value) and "movies.x" in str(raised.value)


def test_a_policy_naming_a_table_that_is_gone_stops_the_copy() -> None:
    catalogue = _catalogue()
    del catalogue["ebay_connect_states"]
    with pytest.raises(BackupPolicyError, match="names ebay_connect_states, which no longer"):
        classify(catalogue)


def test_the_policy_covers_what_mcu_readonly_was_refused() -> None:
    """The eight tables production's read-only role cannot fully read (14 Oct, live)."""
    assert CREDENTIAL_TABLES | set(CREDENTIAL_COLUMNS) == {
        "calendar_feed_tokens",
        "ebay_accounts",
        "ebay_connect_states",
        "movie_night_sessions",
        "profiles",
        "push_subscriptions",
        "rate_limit_counters",
        "refresh_tokens",
    }


def test_parents_load_before_children_and_a_self_link_is_fine() -> None:
    links = [
        ("collection_items", "movies"),
        ("loans", "collection_items"),
        ("loans", "profiles"),
        ("box_sets", "box_sets"),
    ]
    order = load_order(["loans", "collection_items", "movies", "profiles", "box_sets"], links)
    assert order.index("movies") < order.index("collection_items") < order.index("loans")
    assert order.index("profiles") < order.index("loans")
    assert "box_sets" in order


def test_a_link_to_a_table_outside_the_copy_is_ignored() -> None:
    """``refresh_tokens`` points at ``profiles``; it is never loaded, so it orders nothing."""
    assert load_order(["profiles"], [("refresh_tokens", "profiles")]) == ["profiles"]


def test_two_tables_that_refer_to_each_other_stop_the_restore() -> None:
    with pytest.raises(BackupPolicyError, match="cycle among a, b"):
        load_order(["a", "b"], [("a", "b"), ("b", "a")])


def test_restored_counts_are_compared_table_by_table() -> None:
    assert compare({"movies": 3, "profiles": 2}, {"movies": 3, "profiles": 2}) == []
    assert compare({"movies": 3, "loans": 1}, {"movies": 2, "extra": 0}) == [
        "extra: restored, not in the copy",
        "loans: in the copy, not restored",
        "movies: 3 in the copy, 2 restored",
    ]


def test_a_manifest_of_another_format_is_refused(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text('{"format": 99}', encoding="utf-8")
    with pytest.raises(BackupPolicyError, match="format 99"):
        Manifest.read(tmp_path)


def test_the_drill_refuses_a_copy_behind_the_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Production not migrated to the code it runs is what the drill's head check catches."""
    (tmp_path / "manifest.json").write_text(
        Manifest(revision="001", taken_utc="2026-10-14T03:30:00Z").to_json(), encoding="utf-8"
    )
    monkeypatch.setenv("RESTORE_DATABASE_URL", "postgresql://nowhere.invalid/never")
    assert run_restore(tmp_path, expect_head=True) == 1
