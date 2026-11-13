#!/usr/bin/env bash
# Build Postgres's pg_trgm and unaccent extensions into the API venv's pgserver (macOS, the Mac).
#
# Why: since migration 077 (AE7, search) the schema needs both extensions. pgserver's bundled
# PostgreSQL 16.2 ships neither, so without them a local throwaway database stops at migration
# 076, and the database tests and the end-to-end suite can run only in CI (DECISIONS.md #362,
# #370). pgserver does ship pg_config, the server headers and PGXS, so only the two contrib
# modules are compiled, from the official 16.2 source, checked against a pinned SHA-256.
#
# Undo: reinstall pgserver. A venv rebuild or a pgserver upgrade removes them too, so run this
# again afterwards. Cloud sessions do not need it: their Postgres 16 comes with both.
#
# Usage: scripts/pgserver-extensions.sh [--force]
#   --force                    rebuild and reinstall even if both are already there
#   PG_SOURCE_TARBALL=<path>   use an already-downloaded postgresql-16.2.tar.bz2 (still checked)
set -euo pipefail

REPO="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
PGINSTALL="$REPO/apps/api/.venv/lib/python3.12/site-packages/pgserver/pginstall"
PG_CONFIG="$PGINSTALL/bin/pg_config"
VERSION="16.2"
TARBALL="postgresql-$VERSION.tar.bz2"
URL="https://ftp.postgresql.org/pub/source/v$VERSION/$TARBALL"
SHA256="446e88294dbc2c9085ab4b7061a646fa604b4bec03521d5ea671c2e5ad9b2952"
MODULES=(pg_trgm unaccent)

if [[ ! -x "$PG_CONFIG" ]]; then
  echo "pgserver not found at $PGINSTALL (is the API venv installed?)" >&2
  exit 1
fi
have="$("$PG_CONFIG" --version)"
if [[ "$have" != "PostgreSQL $VERSION" ]]; then
  echo "pgserver ships $have, not $VERSION: pin that version's source and checksum here first" >&2
  exit 1
fi

pkglib="$("$PG_CONFIG" --pkglibdir)"
if [[ "${1:-}" != "--force" && -f "$pkglib/pg_trgm.dylib" && -f "$pkglib/unaccent.dylib" ]]; then
  echo "pg_trgm and unaccent are already in pgserver; --force rebuilds them."
  exit 0
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir "$work/download" "$work/build"
if [[ -n "${PG_SOURCE_TARBALL:-}" ]]; then
  cp "$PG_SOURCE_TARBALL" "$work/download/$TARBALL"
else
  curl -fsSL -o "$work/download/$TARBALL" "$URL"
fi
echo "$SHA256  $work/download/$TARBALL" | shasum -a 256 -c -

paths=()
for m in "${MODULES[@]}"; do paths+=("postgresql-$VERSION/contrib/$m"); done
tar -xjf "$work/download/$TARBALL" -C "$work/build" "${paths[@]}"

# pgserver's Makefile.global names the SDK of the CI machine that built it; use this Mac's.
sdk="$(xcrun --show-sdk-path)"
for m in "${MODULES[@]}"; do
  dir="$work/build/postgresql-$VERSION/contrib/$m"
  make -s -C "$dir" USE_PGXS=1 PG_CONFIG="$PG_CONFIG" PG_SYSROOT="$sdk"
  make -s -C "$dir" install USE_PGXS=1 PG_CONFIG="$PG_CONFIG" PG_SYSROOT="$sdk"
done

echo "Installed into pgserver:"
ls "$pkglib" | grep -E '^(pg_trgm|unaccent)\.dylib$'
