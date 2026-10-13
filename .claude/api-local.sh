#!/bin/bash
# The API on localhost:8000 against a throwaway Postgres, for a browser check that needs real
# endpoints (Batch X7's chat card, X8's cross-origin worker). Never against Neon or Railway.
#
# The database comes from scratchpad/local-api.env (gitignored):
#   DATABASE_URL=postgresql://postgres:@/<db>?host=<socket dir>
# pgserver 16.2 in the API venv makes one (STATUS.md, "Four things", 3).
set -euo pipefail
ENV_FILE="$PWD/scratchpad/local-api.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "No $ENV_FILE: give it a throwaway DATABASE_URL first." >&2
  exit 2
fi
DATABASE_URL="$(sed -n 's/^DATABASE_URL=//p' "$ENV_FILE")"
# Optional second line, FRONTEND_ORIGIN=http://localhost:4173, when the built bundle is
# served by `web-dist` and calls this API cross-origin (Batch X8's offline check).
FRONTEND_ORIGIN="$(sed -n 's/^FRONTEND_ORIGIN=//p' "$ENV_FILE")"
FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-http://localhost:5173}"
case "$DATABASE_URL" in
  ""|*neon*|*railway*) echo "Refusing: DATABASE_URL must be a throwaway database." >&2; exit 2 ;;
esac
# Signing keys made fresh for each run: sessions last as long as this server does.
JWT_ACCESS_SECRET="$(openssl rand -hex 32)"
JWT_REFRESH_SECRET="$(openssl rand -hex 32)"
export DATABASE_URL FRONTEND_ORIGIN JWT_ACCESS_SECRET JWT_REFRESH_SECRET APP_ENV=development
export PYTHONPATH="$PWD/apps/api"
exec "$PWD/apps/api/.venv/bin/python3.12" -m uvicorn src.main:app --host 127.0.0.1 --port 8000
