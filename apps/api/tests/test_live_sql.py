"""The read-only live SQL tool for cloud sessions — `DECISIONS.md` #236.

**What this proves:** it refuses anything but one statement that only reads, before sending
it; it asks Neon's HTTPS endpoint with the connection string in a header, trying the
endpoint's own host and then the regional ``api.`` host; it prints a table, a plan or JSON;
it masks the password in Neon's errors; and it says what to do when the variable is unset.

**What it does not:** reach Neon. Every answer here comes from an ``httpx.MockTransport``
shaped like Neon's documented response. The first real call is the cloud session that
checks `docs/mac-cloud-setup.md`'s result.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from src.scripts.live_sql import endpoints, main, reads_only, render

URL = "postgresql://mcu_readonly:s3cret-pass@ep-quiet-lake-a1b2c3-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require"
ENV = {"NEON_READONLY_URL": URL}
COUNT = {
    "command": "SELECT",
    "rowCount": 1,
    "fields": [{"name": "films", "dataTypeID": 20}],
    "rows": [{"films": "1887"}],
}


def _neon(answers: list[tuple[int, Any]], seen: list[httpx.Request]) -> httpx.MockTransport:
    replies = iter(answers)

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        status, body = next(replies)
        return httpx.Response(status, json=body)

    return httpx.MockTransport(handle)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT count(*) FROM movies",
        "  select 1;",
        "WITH x AS (SELECT 1) SELECT * FROM x",
        "-- how many\nSELECT 1",
        "TABLE alembic_version",
        "SHOW server_version",
        "EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM movies",
        "explain analyze verbose select 1",
    ],
)
def test_a_statement_that_only_reads_is_sent(sql: str) -> None:
    assert reads_only(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE movies SET title = title WHERE false",
        "DELETE FROM watch_log",
        "INSERT INTO movies DEFAULT VALUES",
        "DROP TABLE movies",
        "SELECT 1; DROP TABLE movies",
        "EXPLAIN ANALYZE DELETE FROM watch_log",
        "/* select */ UPDATE movies SET title = 'x'",
        "",
        "-- nothing",
    ],
)
def test_anything_else_is_refused_before_sending(sql: str) -> None:
    assert not reads_only(sql)


def test_the_endpoint_host_first_then_the_regional_api_host() -> None:
    assert endpoints(URL) == [
        "https://ep-quiet-lake-a1b2c3-pooler.eu-west-2.aws.neon.tech/sql",
        "https://api.eu-west-2.aws.neon.tech/sql",
    ]


def test_it_asks_neon_over_https_with_the_url_in_a_header(
    capsys: pytest.CaptureFixture[str],
) -> None:
    seen: list[httpx.Request] = []

    code = main(
        ["SELECT count(*) AS films FROM movies"], environ=ENV, transport=_neon([(200, COUNT)], seen)
    )

    assert code == 0
    (request,) = seen
    assert str(request.url) == "https://ep-quiet-lake-a1b2c3-pooler.eu-west-2.aws.neon.tech/sql"
    assert request.headers["Neon-Connection-String"] == URL
    assert json.loads(request.content) == {
        "query": "SELECT count(*) AS films FROM movies",
        "params": [],
    }
    out = capsys.readouterr().out
    assert out.splitlines() == ["films", "-----", "1887", "(1 row)"]
    assert "s3cret-pass" not in out


def test_it_tries_the_regional_host_when_the_endpoints_own_answers_404() -> None:
    seen: list[httpx.Request] = []

    code = main(["SELECT 1"], environ=ENV, transport=_neon([(404, {}), (200, COUNT)], seen))

    assert code == 0
    assert [request.url.host for request in seen] == [
        "ep-quiet-lake-a1b2c3-pooler.eu-west-2.aws.neon.tech",
        "api.eu-west-2.aws.neon.tech",
    ]


def test_a_plan_prints_as_postgres_prints_it(capsys: pytest.CaptureFixture[str]) -> None:
    seen: list[httpx.Request] = []
    plan = {
        "command": "EXPLAIN",
        "fields": [{"name": "QUERY PLAN"}],
        "rows": [{"QUERY PLAN": "Seq Scan on movies"}, {"QUERY PLAN": "Execution Time: 0.4 ms"}],
    }

    code = main(
        ["--explain", "SELECT * FROM movies"], environ=ENV, transport=_neon([(200, plan)], seen)
    )

    assert code == 0
    assert json.loads(seen[0].content)["query"] == "EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM movies"
    assert capsys.readouterr().out.splitlines() == ["Seq Scan on movies", "Execution Time: 0.4 ms"]


def test_json_prints_the_rows(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--json", "SELECT 1"], environ=ENV, transport=_neon([(200, COUNT)], []))

    assert code == 0
    assert json.loads(capsys.readouterr().out) == [{"films": "1887"}]


def test_neons_refusal_is_shown_with_the_password_masked(
    capsys: pytest.CaptureFixture[str],
) -> None:
    refusal = {
        "message": "password authentication failed for mcu_readonly:s3cret-pass",
        "code": "28P01",
    }

    code = main(["SELECT 1"], environ=ENV, transport=_neon([(400, refusal)], []))

    assert code == 1
    err = capsys.readouterr().err
    assert "Neon refused it (HTTP 400)" in err
    assert "s3cret-pass" not in err and "***" in err


def test_without_the_variable_it_says_where_it_comes_from(
    capsys: pytest.CaptureFixture[str],
) -> None:
    seen: list[httpx.Request] = []

    code = main(["SELECT 1"], environ={}, transport=_neon([], seen))

    assert (code, seen) == (2, [])
    assert "docs/mac-cloud-setup.md" in capsys.readouterr().err


def test_a_write_is_refused_and_nothing_is_sent(capsys: pytest.CaptureFixture[str]) -> None:
    seen: list[httpx.Request] = []

    code = main(["DELETE FROM watch_log"], environ=ENV, transport=_neon([], seen))

    assert (code, seen) == (2, [])
    assert "Refused before sending" in capsys.readouterr().err


def test_an_answer_with_no_columns_says_what_ran() -> None:
    assert render({"command": "SHOW", "rowCount": 0, "fields": [], "rows": []}) == "SHOW 0"
