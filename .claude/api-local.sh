#!/bin/bash
# The API on localhost:8000 against a throwaway Postgres, for a browser check that needs real
# endpoints (Batch X7's chat card, X8's cross-origin worker). Never against Neon or Railway.
#
# The database comes from scratchpad/local-api.env (gitignored), one line:
#   DATABASE_URL=postgresql://postgres:@/<db>?host=<socket dir>
# pgserver 16.2 in the API venv makes one (STATUS.md, "Four things", 3).
set -euo pipefail
ENV_FILE="$PWD/scratchpad/local-api.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "No $ENV_FILE: give it a throwaway DATABASE_URL first." >&2
  exit 2
fi
DATABASE_URL="$(sed -n 's/^DATABASE_URL=//p' "$ENV_FILE")"
case "$DATABASE_URL" in
  ""|*neon*|*railway*) echo "Refusing: DATABASE_URL must be a throwaway database." >&2; exit 2 ;;
esac
# Signing keys made fresh for each run: sessions last as long as this server does.
JWT_ACCESS_SECRET="$(openssl rand -hex 32)"
JWT_REFRESH_SECRET="$(openssl rand -hex 32)"
export DATABASE_URL JWT_ACCESS_SECRET JWT_REFRESH_SECRET APP_ENV=development PYTHONPATH="$PWD/apps/api"
exec "$PWD/apps/api/.venv/bin/python3.12" -m uvicorn src.main:app --host 127.0.0.1 --port 8000
