#!/bin/bash
# Serve the built bundle, not the dev server. `STATUS.md` records that CI builds the web
# app and never runs it, so a Dockerfile-style regression in the real artefact — a missing
# public asset, a manifest that does not parse — surfaces at deploy time. This is how a
# session checks the thing that actually ships.
export PATH="/Users/craigrobinson/.nvm/versions/node/v20.20.2/bin:$PATH"
exec pnpm --filter @mcu/web preview --port 4173 --strictPort
