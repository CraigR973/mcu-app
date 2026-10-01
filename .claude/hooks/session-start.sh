#!/bin/bash
# Cloud sessions only: make the whole gate runnable without a manual preflight (DECISIONS.md #236).
#
# What it leaves ready, every time:
#   - apps/api/.venv on Python 3.12 with the locked dev dependencies (hashes checked);
#   - the pnpm workspace installed from the lockfile;
#   - a throwaway Postgres 16 on localhost:5433 with `mcu_test` migrated to head, and
#     DATABASE_URL plus CI's test JWT secrets exported for the session, so pytest runs
#     against it and never against production;
#   - the Railway CLI, pinned: `config plan` when a token is set; `apply` stays Craig's word.
# Then it says which of the cloud credentials it found, by name only.
#
# Idempotent. The container is cached after this runs, so later sessions mostly start
# services rather than install anything.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

R="${CLAUDE_PROJECT_DIR:-/home/user/mcu-app}"
LOG=/tmp/mcu-session-start.log
PG_BIN=/usr/lib/postgresql/16/bin
PG_ROOT=/tmp/mcu-pg
PG_DATA="$PG_ROOT/data"
TEST_DB_URL=postgresql://postgres@localhost:5433/mcu_test
RAILWAY_CLI_VERSION=5.63.1
notes=()

# Run a step quietly; on failure, show the end of its output and stop.
step() {
  local name="$1"
  shift
  if ! "$@" >"$LOG" 2>&1; then
    echo "Cloud setup failed at: $name. The end of its output:" >&2
    tail -20 "$LOG" >&2
    exit 1
  fi
}

# 1. The API's Python environment.
if [ ! -x "$R/apps/api/.venv/bin/python3.12" ]; then
  step "the Python venv" /usr/bin/python3.12 -m venv "$R/apps/api/.venv"
fi
step "the API's locked dependencies" "$R/apps/api/.venv/bin/pip" install --quiet \
  --disable-pip-version-check --require-hashes -r "$R/apps/api/requirements-dev.lock"

# 2. The web app and the shared package.
step "the pnpm workspace" pnpm -C "$R" install --frozen-lockfile

# 3. A throwaway Postgres for the API's tests and the migration round trip.
if [ ! -s "$PG_DATA/PG_VERSION" ]; then
  mkdir -p "$PG_ROOT"
  chown postgres:postgres "$PG_ROOT"
  step "initdb" su postgres -c "$PG_BIN/initdb -D $PG_DATA -U postgres --auth=trust"
fi
if ! su postgres -c "$PG_BIN/pg_ctl -D $PG_DATA status" >/dev/null 2>&1; then
  # A cached container can carry a lock file from a server that no longer runs.
  rm -f "$PG_DATA/postmaster.pid" "$PG_ROOT/.s.PGSQL.5433" "$PG_ROOT/.s.PGSQL.5433.lock"
  step "starting Postgres" su postgres -c "$PG_BIN/pg_ctl -D $PG_DATA -w -l $PG_ROOT/log \
    -o '-p 5433 -k $PG_ROOT -c listen_addresses=localhost' start"
fi
if [ -z "$(psql -h localhost -p 5433 -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname = 'mcu_test'")" ]; then
  step "creating mcu_test" psql -h localhost -p 5433 -U postgres -qc 'CREATE DATABASE mcu_test'
fi
step "migrating mcu_test" env DATABASE_URL="$TEST_DB_URL" \
  JWT_ACCESS_SECRET=ci-access-secret-with-at-least-32-characters \
  JWT_REFRESH_SECRET=ci-refresh-secret-with-at-least-32-characters \
  PYTHONPATH="$R/apps/api" \
  "$R/apps/api/.venv/bin/alembic" --config "$R/apps/api/alembic.ini" upgrade head

if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export DATABASE_URL=$TEST_DB_URL"
    echo "export JWT_ACCESS_SECRET=ci-access-secret-with-at-least-32-characters"
    echo "export JWT_REFRESH_SECRET=ci-refresh-secret-with-at-least-32-characters"
  } >>"$CLAUDE_ENV_FILE"
fi

# 4. The Railway CLI. Not needed for the gate, so a failed install is reported, not fatal.
if [ "$(railway --version 2>/dev/null || true)" != "railway $RAILWAY_CLI_VERSION" ]; then
  if ! npm install --global --no-audit --no-fund "@railway/cli@$RAILWAY_CLI_VERSION" >/dev/null 2>&1; then
    notes+=("the Railway CLI did not install, so no config plan this session")
  fi
fi

# 5. What this session can reach, by name only: never a value.
present=()
missing=()
for name in NEON_READONLY_URL RAILWAY_TOKEN RAILWAY_API_TOKEN RAILWAY_PROJECT_ID; do
  if [ -n "${!name:-}" ]; then present+=("$name"); else missing+=("$name"); fi
done

railway_state="Railway CLI $RAILWAY_CLI_VERSION"
[ "${#notes[@]}" -eq 0 ] || railway_state="no Railway CLI"
echo "Cloud setup ready: venv, pnpm workspace, Postgres 16 on 5433 with mcu_test at head" \
  "(DATABASE_URL points at it), $railway_state."
echo "Credentials present: ${present[*]:-none}. Absent: ${missing[*]:-none}" \
  "(docs/mac-cloud-setup.md makes them)."
for note in ${notes[@]+"${notes[@]}"}; do echo "Note: $note."; done
