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

**Know what this proves.** CI runs pytest against a real Postgres 17 service, proves
`upgrade head` → `downgrade base`, and builds and boots the image Railway deploys (#248), so a
missing database or a broken image can no longer pass silently. `test_derived_field_triggers.py`
runs there with no skips. **On Craig's Mac, run pytest with `env -u DATABASE_URL`:** there is
no local Postgres (STATUS gotcha 15), and the only database URL on the Mac, in
`apps/api/.env.local`, is production's. Never point tests or migrations at it; the
database-backed tests and migration changes are proved by CI, and the report says so. A cloud
session has its own throwaway Postgres (`AGENTS.md`, "Cloud sessions"). The gate does **not**
run the web bundle it builds in a browser: a green web job is not evidence the app runs.

`pnpm -r test`, not `--filter @mcu/web test` — the filtered form never runs
`packages/shared`.

For frontend-visible batches, open the app and record what you actually looked at.

Report pass/fail **by acceptance criterion**, with the exact remaining gaps. If everything
is green, `phase-closeout` follows automatically (`DECISIONS.md` #24) — including the push
that deploys. If anything is red, or the batch touched hosting/credentials or performed a
destructive operation, stop here and report instead.
