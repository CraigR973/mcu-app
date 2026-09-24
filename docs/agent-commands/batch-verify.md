# batch-verify

Turn the batch's acceptance criteria into a checklist, then prove each one.

Run all of these, from the repo root, with absolute paths:

```
apps/api/.venv/bin/ruff check apps/api
apps/api/.venv/bin/ruff format --check apps/api
PYTHONPATH=apps/api apps/api/.venv/bin/mypy --config-file apps/api/pyproject.toml apps/api/src
apps/api/.venv/bin/python3.12 -m pytest apps/api/tests
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm -r test
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm --filter @mcu/shared typecheck
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm --filter @mcu/shared build
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm --filter @mcu/web lint
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm --filter @mcu/web typecheck
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm --filter @mcu/web build
```

**Know what this proves.** CI runs pytest against a real Postgres 17 service and proves
`upgrade head` → `downgrade base`, so a missing database can no longer pass silently. The 13
tests in `test_derived_field_triggers.py` still skip, but now because Batch 4 has not created
`movies` and `collection_items` — they must **resume, not skip**, once it does. Locally,
export `DATABASE_URL` from `apps/api/.env.local` before trusting any migration change, and
say in the report that you did. The gate does **not** build the Docker image (Railway does)
and does **not** run the web bundle it builds — a green web job is not evidence the app runs.

`pnpm -r test`, not `--filter @mcu/web test` — the filtered form never runs
`packages/shared`.

For frontend-visible batches, open the app and record what you actually looked at.

Report pass/fail **by acceptance criterion**, with the exact remaining gaps. If everything
is green, `phase-closeout` follows automatically (`DECISIONS.md` #24) — including the push
that deploys. If anything is red, or the batch touched hosting/credentials or performed a
destructive operation, stop here and report instead.
